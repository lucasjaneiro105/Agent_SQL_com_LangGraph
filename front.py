import streamlit as st
import time
import base64
import duckdb
import os
from graph import graph


# criando BD estatico para exemplo caso queira usar outro banco basta mudar a logica no codigo do agente

db_name = "clientes_novo.duckdb"
if not os.path.exists(db_name):
    conn = duckdb.connect(db_name)
    conn.execute('''
    CREATE TABLE clientes (
    cliente_id INTEGER PRIMARY KEY,
    nome TEXT NOT NULL,
    sobrenome TEXT NOT NULL,
    email TEXT NOT NULL,
    tipo_plano TEXT NOT NULL,
    pacote TEXT NOT NULL,
    valor_pago DECIMAL(10, 2) NOT NULL
)
''')
    clientes_data = [
    (1, 'João', 'Santos', 'joao.santos@email.com', 'Plano Plus', 'Anual', 159.20),
    (2, 'Maria', 'Souza', 'maria.souza@email.com', 'Plano Pro', 'Mensal', 399.00),
    (3, 'Pedro', 'Ferreira', 'pedro.ferreira@email.com', 'Plano Business', 'Mensal', 149.90),
    (4, 'Carla', 'Mendes', 'carla.mendes@email.com', 'Plano Elite', 'Anual', 472.00),
    (5, 'Marcos', 'Rocha', 'marcos.rocha@email.com', 'Plano Colaborador', 'Mensal', 69.90),
    (6, 'Luana', 'Dias', 'luana.dias@email.com', 'Plano Plus', 'Mensal', 199.00),
    (7, 'Ricardo', 'Nunes', 'ricardo.nunes@email.com', 'Plano Pro', 'Anual', 319.20),
    (8, 'Beatriz', 'Lima', 'beatriz.lima@email.com', 'Plano Business', 'Mensal', 149.90),
    (9, 'Fernanda', 'Costa', 'fernanda.costa@email.com', 'Plano Plus', 'Mensal', 199.00),
    (10, 'Lucas', 'Oliveira', 'lucas.oliveira@email.com', 'Plano Colaborador', 'Mensal', 69.90),
    (11, 'André', 'Silva', 'andre.silva@email.com', 'Plano Plus', 'Anual', 159.20),
    (12, 'Juliana', 'Pereira', 'juliana.pereira@email.com', 'Plano Pro', 'Mensal', 399.00),
    (13, 'Roberto', 'Alves', 'roberto.alves@email.com', 'Plano Business', 'Mensal', 149.90),
    (14, 'Camila', 'Souza', 'camila.souza@email.com', 'Plano Elite', 'Anual', 472.00),
    (15, 'Gabriel', 'Lima', 'gabriel.lima@email.com', 'Plano Pro', 'Mensal', 399.00),
    (16, 'Letícia', 'Costa', 'leticia.costa@email.com', 'Plano Plus', 'Mensal', 199.00),
    (17, 'Tiago', 'Rocha', 'tiago.rocha@email.com', 'Plano Pro', 'Anual', 319.20),
    (18, 'Vanessa', 'Dias', 'vanessa.dias@email.com', 'Plano Plus', 'Mensal', 199.00),
    (19, 'Rafael', 'Nunes', 'rafael.nunes@email.com', 'Plano Plus', 'Mensal', 199.00),
    (20, 'Patrícia', 'Silva', 'patricia.silva@email.com', 'Plano Plus', 'Anual', 159.20)
]
    conn.executemany('INSERT INTO clientes VALUES (?, ?, ?, ?, ?, ?, ?)', clientes_data)
    conn.close()


st.set_page_config(page_title="SQL AGENT", page_icon="🔎")
st.title("SQL AGENT 🔎")

def stream_data(text):
    for word in text.split(" "):
        yield word + " "
        time.sleep(0.02)

def extract_image_bytes(html_string):
    if not html_string or "base64," not in html_string:
        return None
    try:
        base64_str = html_string.split("base64,")[1].split('"')[0]
        return base64.b64decode(base64_str)
    except Exception:
        return None

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        
        if "image_bytes" in message and message["image_bytes"]:
             st.image(message["image_bytes"])
        
        if "sql" in message and message["sql"]:
            with st.expander("Query Gerada"):
                st.code(message["sql"], language="sql")
        
        if "interpretacao_tecnica" in message and message["interpretacao_tecnica"]:
            with st.expander("Análise Técnica"):
                st.markdown(message["interpretacao_tecnica"])

if prompt := st.chat_input("Escreva aqui"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        inputs = {"pergunta": prompt}
        final_state = graph.invoke(inputs)

        response_text = final_state.get("resposta_text") or final_state.get("interpretacao") or "Sem resposta gerada."
        
        interpretacao_tecnica = final_state.get("interpretacao")
        
        plot_html = final_state.get("plot_html")
        generated_sql = final_state.get("sql", "")

        st.write_stream(stream_data(response_text))

        image_bytes = None
        if plot_html:
            image_bytes = extract_image_bytes(plot_html)
            if image_bytes:
                st.image(image_bytes)

        if interpretacao_tecnica and generated_sql:
            with st.expander("Análise Técnica"):
                clean_interp = interpretacao_tecnica.replace("[GRAFICO_BARRA]", "").replace("[GRAFICO_PIZZA]", "").replace("[GRAFICO_LINHA]", "").replace("[SEM_GRAFICO]", "")
                st.markdown(clean_interp)

        if generated_sql:
            with st.expander("Query Gerada"):
                st.code(generated_sql, language="sql")

        message_data = {
            "role": "assistant", 
            "content": response_text,
            "sql": generated_sql
        }
        
        if interpretacao_tecnica and generated_sql:
             message_data["interpretacao_tecnica"] = interpretacao_tecnica.replace("[GRAFICO_BARRA]", "").replace("[GRAFICO_PIZZA]", "").replace("[GRAFICO_LINHA]", "").replace("[SEM_GRAFICO]", "")

        if image_bytes:
             message_data["image_bytes"] = image_bytes
             
        st.session_state.messages.append(message_data)