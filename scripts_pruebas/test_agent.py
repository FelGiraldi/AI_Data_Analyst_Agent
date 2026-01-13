# scripts_pruebas/test_agent.py
import asyncio
import os
from langchain_core.messages import HumanMessage
from infrastructure.persistence.duckdb_adapter import DuckDBAdapter
from application.graph import build_analyst_graph
from dotenv import load_dotenv

# Cargar API KEY
load_dotenv()

async def main():
    print("--- 🤖 Iniciando Test del Agente Completo ---")
    
    # 1. Setup Infra
    db = DuckDBAdapter()
    
    # Creamos datos dummy de ventas
    with open("ventas_2026.csv", "w") as f:
        f.write("mes,ventas,costos\nEnero,1000,800\nFebrero,1200,850\nMarzo,1100,900")
    
    print("📂 Cargando dataset...")
    schema = await db.load_csv("ventas_2026.csv", "tabla_ventas")
    schema_str = schema.get_context_for_llm()
    print(f"📝 Contexto: {schema_str}")

    # 2. Construir el Cerebro
    app = build_analyst_graph(db)
    
    # 3. Pregunta del Usuario
    pregunta = "Calcula el margen de ganancia (ventas - costos) por mes y dime cuál fue el mejor mes."
    print(f"\n👤 Usuario: {pregunta}\n")
    
    # 4. Estado Inicial
    initial_state = {
        "messages": [HumanMessage(content=pregunta)],
        "schema_info": schema_str,
        "retry_count": 0,
        "error": None
    }
    
    # 5. Ejecutar Stream (Veremos el "pensamiento" en tiempo real)
    print("--- 🧠 Pensando (Stream) ---")
    async for event in app.astream(initial_state):
        for node_name, state_update in event.items():
            print(f"\n📍 Nodo: {node_name}")
            
            if "sql_query" in state_update:
                print(f"   💻 SQL Generado: {state_update['sql_query']}")
            
            if "error" in state_update and state_update["error"]:
                print(f"   ❌ Error detectado: {state_update['error']}")
                print("   🔄 Reintentando corrección...")
            
            if "messages" in state_update and node_name == "analyze_results":
                print(f"\n✨ Respuesta Final:\n{state_update['messages'][-1].content}")

    # Limpieza
    if os.path.exists("ventas_2026.csv"):
        os.remove("ventas_2026.csv")

if __name__ == "__main__":
    asyncio.run(main())