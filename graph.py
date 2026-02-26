import warnings
warnings.filterwarnings('ignore')

import duckdb
import numpy as np
import pandas as pd
import os
import io
import base64
import json
import matplotlib.pyplot as plt
from decimal import Decimal
from typing import List
from IPython.display import Image, display, HTML
from dotenv import load_dotenv
from langchain_openai.chat_models import ChatOpenAI
from langgraph.graph import StateGraph, END, START
from langchain_core.messages import SystemMessage, HumanMessage

from schemas import AgentState
from prompts import (
    VALIDADOR_PROMPT,
    PERGUNTAS_PROMPT,
    GERADOR_QUERY_PROMPT,
    VALIDADOR_QUERY_PROMPT,
    REVISOR_PROMPT,
    INTERPRETE_PROMPT
)


load_dotenv()

# especifique o modelo: gpt4, claude, gemini , etc
model = ChatOpenAI(model_name="<modelo>", temperature=0)



def get_database_schema(db_path):
    conn = duckdb.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='main'")
    tables = cursor.fetchall()
    schema = ''
    for table_name in tables:
        table_name = table_name[0]
        cursor.execute(f"DESCRIBE {table_name}")
        columns = cursor.fetchall()
        schema += f"Tabela: {table_name}\n"
        schema += "Colunas:\n"
        for column in columns:
            schema += f" - {column[0]} ({column[1]})\n"
        schema += '\n'
    conn.close()
    return schema

#NÓS 

def validador_node(state: AgentState):
    
    instruction = f"Analise a seguinte entrada do usuário: '{state.pergunta}'"

    messages = [
        SystemMessage(content=VALIDADOR_PROMPT),
        HumanMessage(content=instruction)
    ]
    
    response = model.invoke(messages)
    
    try:
        content = response.content.replace("```json", "").replace("```", "").strip()
        decision = json.loads(content)
    except:
        decision = {"status": "REPROVADO", "reason": "Erro de formatação na validação."}

    updates = {
        "status_validacao": decision['status'],
        "motivo_validacao": decision['reason']
    }
    
    if decision['status'] == 'REPROVADO':
        updates.update({
            "resposta_text": "Infelizmente não posso responder isso, tente novamente",
            "interpretacao": None,
            "sql": "",
            "resultados": [],
            "plot_needed": False,
            "plot_html": ""
        })
    
    return updates

def perguntas_node(state: AgentState):
    instruction = f"Pergunta do usuário: {state.pergunta}"
    
    messages = [
        SystemMessage(content=PERGUNTAS_PROMPT),
        HumanMessage(content=instruction)
    ]
    
    response = model.invoke(messages)
    
    return {
        "resposta_text": response.content,
        "interpretacao": None,
        "sql": "",
        "resultados": [],
        "plot_needed": False,
        "plot_html": ""
    }

def mapeador_node(state: AgentState):
    current_db = state.database if state.database else "clientes_novo.duckdb"
        
    db_schema = get_database_schema(current_db)
    return {"table_schemas": db_schema, "database": current_db}

def gerador_query_node(state: AgentState):
    instruction = f"Esquema do banco: {state.table_schemas}\n"
    if state.reflexao:
        instruction += f"Feedbacks anteriores: {state.reflexao[-1]}\n"
    instruction += f"Pergunta: {state.pergunta}"
    
    messages = [
        SystemMessage(content=GERADOR_QUERY_PROMPT),
        HumanMessage(content=instruction)
    ]
    response = model.invoke(messages)
    
    return {
        "sql": response.content.strip(),
        "revisao": state.revisao + 1
    }

def validador_query_node(state: AgentState):
    instruction = f"Com base no seguinte esquema de banco de dados:\n{state.table_schemas}\n"
    instruction += f"E na seguinte consulta SQL:\n{state.sql}\n"
    instruction += f"Verifique se a consulta SQL pode completar a tarefa: {state.pergunta}\n"
    instruction += "Responda 'ACEITO' se estiver correta ou 'REJEITADO' se não estiver.\n"
    messages = [
        SystemMessage(content=VALIDADOR_QUERY_PROMPT),
        HumanMessage(content=instruction)
    ]
    response = model.invoke(messages)
    
    return {"aceito": 'ACEITO' in response.content.upper()}

def revisor_node(state: AgentState):
    instruction = f"Com base no seguinte esquema de banco de dados:\n{state.table_schemas}\n"
    instruction += f"E na seguinte consulta SQL:\n{state.sql}\n"
    instruction += f"Por favor, forneça recomendações úteis e detalhadas para ajudar a melhorar a consulta SQL para a tarefa: {state.pergunta}\n"
    messages = [
        SystemMessage(content=REVISOR_PROMPT),
        HumanMessage(content=instruction)
    ]
    response = model.invoke(messages)
    
    return {"reflexao": [response.content]}

def executor_node(state: AgentState):
    conn = duckdb.connect(state.database)
    cursor = conn.cursor()
    resultados = []
    try:
        cursor.execute(state.sql)
        resultados = cursor.fetchall()
    except Exception as e:
        resultados = []
    finally:
        cursor.close()
        conn.close()
    
    return {"resultados": resultados}

def interprete_node(state: AgentState):
    instruction = f"Pergunta: {state.pergunta}\nSQL: {state.sql}\nResultados: {state.resultados}"
    
    messages = [
        SystemMessage(content=INTERPRETE_PROMPT),
        HumanMessage(content=instruction)
    ]
    response = model.invoke(messages)
    
    try:
        content = response.content.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(content)
        resposta_text = parsed.get("resposta_text", "Resposta não gerada.")
        interpretacao = parsed.get("interpretacao", "Análise técnica indisponível.")
        grafico_tag = parsed.get("grafico_tag", "[SEM_GRAFICO]")
    except Exception:
        resposta_text = "Houve um erro ao processar sua solicitação."
        interpretacao = response.content
        grafico_tag = "[SEM_GRAFICO]"

    tags = ["[GRAFICO_BARRA]", "[GRAFICO_PIZZA]", "[GRAFICO_LINHA]"]
    plot_needed = any(tag in grafico_tag for tag in tags)
    
    interpretacao_com_tag = f"{interpretacao} {grafico_tag}"
    
    return {
        "resposta_text": resposta_text,
        "interpretacao": interpretacao_com_tag,
        "plot_needed": plot_needed
    }

def gerador_grafico_node(state: AgentState):
    if not state.plot_needed:
        return {"plot_html": ""}
    
    results = state.resultados
    if not results or len(results) == 0:
        return {"plot_html": ""}

    labels = [str(row[0]) for row in results]
    values = [float(row[-1]) if isinstance(row[-1], (int, float, Decimal)) else 0 for row in results]

    plt.figure(figsize=(10, 6))
    
    interp = state.interpretacao
    if "[GRAFICO_PIZZA]" in interp:
        plt.pie(values, labels=labels, autopct='%1.1f%%')
    elif "[GRAFICO_LINHA]" in interp:
        plt.plot(labels, values, marker='o')
    else:
        plt.bar(labels, values)

    plt.title(state.pergunta)
    plt.ylabel('Valores')
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close()
    img_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
    
    return {"plot_html": f'<img src="data:image/png;base64,{img_base64}">'}

# Construcao do GRAFO

builder = StateGraph(AgentState)

builder.add_node('validador', validador_node)
builder.add_node('perguntas', perguntas_node)
builder.add_node('mapeador', mapeador_node)
builder.add_node('gerador_query', gerador_query_node)
builder.add_node('validador_query', validador_query_node)
builder.add_node('revisor', revisor_node)
builder.add_node('executor', executor_node)
builder.add_node('interprete', interprete_node)
builder.add_node('gerador_grafico', gerador_grafico_node)

builder.set_entry_point('validador')

def validation_router(state: AgentState):
    status = getattr(state, 'status_validacao', 'REPROVADO')
    
    if status == 'APROVADO':
        return 'mapeador'
    elif status == 'DEFINICAO':
        return 'perguntas'
    else:
        return END

builder.add_conditional_edges(
    'validador',
    validation_router,
    {
        'mapeador': 'mapeador', 
        'perguntas': 'perguntas',
        END: END
    }
)

builder.add_edge('perguntas', END)

builder.add_edge('mapeador', 'gerador_query')
builder.add_edge('gerador_query', 'validador_query')

builder.add_conditional_edges(
    'validador_query',
    lambda state: 'executor' if state.aceito or state.revisao >= state.max_revisao else 'revisor',
    {'executor': 'executor', 'revisor': 'revisor'}
)

builder.add_edge('revisor', 'gerador_query')
builder.add_edge('executor', 'interprete')
builder.add_edge('interprete', 'gerador_grafico')
builder.add_edge('gerador_grafico', END)

graph = builder.compile()