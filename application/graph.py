# application/graph.py
from langgraph.graph import StateGraph, END, START
from application.state import AnalystState
from application.nodes import AgentNodes
from infrastructure.persistence.duckdb_adapter import DuckDBAdapter

def build_analyst_graph(db_adapter: DuckDBAdapter):
    """
    Construye y compila el grafo de LangGraph.
    """
    # 1. Inicializar lógica de nodos
    nodes = AgentNodes(db_adapter)
    
    # 2. Definir el Grafo
    workflow = StateGraph(AnalystState)
    
    # 3. Agregar Nodos
    workflow.add_node("generate_sql", nodes.generate_sql)
    workflow.add_node("validate_sql", nodes.validate_sql)
    workflow.add_node("execute_query", nodes.execute_query)
    workflow.add_node("analyze_results", nodes.analyze_results)
    
    # --- Se agrega el nodo de visualización ---
    workflow.add_node("generate_viz", nodes.generate_viz_config)
    
    # 4. Definir Flujo Normal (Edges)
    workflow.add_edge(START, "generate_sql")
    workflow.add_edge("generate_sql", "validate_sql")
    
    # 5. Lógica Condicional: Validación
    def check_validation(state: AnalystState):
        if state["is_safe"]:
            return "execute"
        if state.get("retry_count", 0) > 3:
            return "abort"
        return "retry"

    workflow.add_conditional_edges(
        "validate_sql",
        check_validation,
        {
            "execute": "execute_query",
            "retry": "generate_sql",
            "abort": END
        }
    )
    
    # 6. Lógica Condicional: Ejecución
    def check_execution(state: AnalystState):
        if not state.get("error"):
            return "analyze"
        if state.get("retry_count", 0) > 3:
            return "abort"
        return "retry"

    workflow.add_conditional_edges(
        "execute_query",
        check_execution,
        {
            "analyze": "analyze_results",
            "retry": "generate_sql",
            "abort": END
        }
    )
    
    # 7. Finalización
    workflow.add_edge("analyze_results", "generate_viz")
    workflow.add_edge("generate_viz", END)
    
    return workflow.compile()