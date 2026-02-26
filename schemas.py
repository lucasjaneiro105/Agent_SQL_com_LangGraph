from typing import List, Annotated, Optional, Any
from pydantic import BaseModel, Field
from operator import add

class AgentState(BaseModel):
    pergunta: str
    table_schemas: Optional[str] = None
    database: str = "clientes_novo.duckdb"
    sql: Optional[str] = None
    reflexao: Annotated[List[str], add] = Field(default_factory=list)
    aceito: bool = False
    revisao: int = 0
    max_revisao: int = 2
    resultados: List[Any] = Field(default_factory=list)
    interpretacao: Optional[str] = None
    resposta_text: Optional[str] = None
    plot_needed: bool = False
    plot_html: Optional[str] = None
    status_validacao: Optional[str] = None
    motivo_validacao: Optional[str] = None