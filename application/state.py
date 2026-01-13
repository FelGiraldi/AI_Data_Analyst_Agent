# application/state.py
from typing import TypedDict, Annotated, List, Dict, Any, Optional
from langgraph.graph.message import add_messages

class AnalystState(TypedDict):
    """
    Representa la memoria de corto plazo del agente durante una ejecución.
    """
    # Historial de chat (LangChain standard)
    messages: Annotated[List, add_messages]
    
    # Contexto de datos
    schema_info: str  # El esquema de la tabla en texto
    
    # Estado interno del proceso
    sql_query: str    # La query generada
    is_safe: bool     # Resultado de validación
    execution_result: List[Dict[str, Any]] # Datos crudos de DuckDB
    
    # Visualización
    viz_config: Dict[str, Any]  # Configuración para generar gráficos
    
    # Control de flujo y errores
    error: Optional[str]
    retry_count: int  # Para evitar bucles infinitos de corrección

    # Memoria de largo plazo
    last_successful_sql: Optional[str]