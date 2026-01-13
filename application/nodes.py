import json
import re
from typing import Dict, Any, List
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from application.state import AnalystState
from application.prompts import (
    SQL_GENERATION_SYSTEM, 
    ANALYSIS_SYSTEM, 
    VIZ_SYSTEM, 
    SUGGESTION_SYSTEM
)
from infrastructure.llm.hybrid_factory import HybridLLMFactory
from infrastructure.security.sql_sanitizer import SQLSanitizer
from infrastructure.persistence.duckdb_adapter import DuckDBAdapter
from domain.value_objects.sql_query import SQLQuery

class AgentNodes:
    def __init__(self, db_adapter: DuckDBAdapter):
        self.db = db_adapter
        # Se inicializa de fábrica sin modelo específico, se pide bajo demanda
        
    async def generate_sql(self, state: AnalystState) -> Dict[str, Any]:
        """
        Nodo 1: Generar SQL con Memoria Conversacional.
        """
        print("--- 🤖 GENERATING SQL ---")
        llm = HybridLLMFactory.get_model(temperature=0)
        
        # 1. Recuperar contexto de memoria
        last_sql = state.get("last_successful_sql")
        last_sql_context = last_sql if last_sql else "Ninguna (Nueva conversación)"
        
        # 2. Preparar Prompt
        try:
            prompt = SQL_GENERATION_SYSTEM.format(
                schema=state.get("schema_info", ""),
                last_sql=last_sql_context
            )
        except KeyError:
            # Fallback seguro
            prompt = f"Genera SQL para: {state.get('schema_info', '')}"

        # 3. Contexto del usuario o error previo
        user_msg = state["messages"][-1]
        
        if state.get("error"):
            failed_query = state.get("sql_query", "query desconocida")
            content = (
                f"La query anterior falló.\n"
                f"Query fallida: {failed_query}\n"
                f"Error: {state['error']}\n"
                f"Instrucción original: {state['messages'][-1].content}\n"
                "Genera una versión corregida."
            )
            user_msg = HumanMessage(content=content)

        messages = [SystemMessage(content=prompt), user_msg]
        
        try:
            response = await llm.ainvoke(messages)
            content = response.content or ""
            
            # Limpieza básica
            clean_sql = content.replace("```sql", "").replace("```", "").strip()
            # Para limpiar texto introductorio
            if "select" in clean_sql.lower():
                idx = clean_sql.lower().find("select")
                clean_sql = clean_sql[idx:]
            
            # Validación de nulidad
            if not clean_sql:
                clean_sql = "SELECT * FROM dataset_usuario LIMIT 5"
            
            return {
                "sql_query": clean_sql, 
                "error": None, 
                "retry_count": state.get("retry_count", 0) + 1
            }
            
        except Exception as e:
            return {
                "sql_query": "SELECT 1", 
                "error": f"LLM Error: {str(e)}", 
                "retry_count": state.get("retry_count", 0) + 1
            }

    def validate_sql(self, state: AnalystState) -> Dict[str, Any]:
        """Nodo 2: Validación de Seguridad"""
        print("--- 🛡️ VALIDATING SQL ---")
        try:
            sql_query = state.get("sql_query")
            if not sql_query:
                return {"is_safe": False, "error": "SQL query está vacío"}
            
            query_obj = SQLQuery(sql_query)
            validated = SQLSanitizer.validate_query(query_obj)
            return {"is_safe": validated.is_safe, "error": validated.validation_error}
        except Exception as e:
            return {"is_safe": False, "error": str(e)}

    async def execute_query(self, state: AnalystState) -> Dict[str, Any]:
        """
        Nodo 3: Ejecución.
        Si tiene éxito, actualiza la Memoria (last_successful_sql).
        """
        print("--- ⚡ EXECUTING SQL ---")
        try:
            sql_query = state.get("sql_query")
            if not sql_query:
                return {"execution_result": [], "error": "SQL query está vacío"}
            
            query_obj = SQLQuery(sql_query).mark_as_safe()
            results = await self.db.execute_query(query_obj)
            
            return {
                "execution_result": results if results is not None else [], 
                "error": None,
                "last_successful_sql": sql_query  #ACTUALIZACIÓN DE MEMORIA
            }
        except Exception as e:
            return {"execution_result": [], "error": f"DB Error: {str(e)}"}

    async def analyze_results(self, state: AnalystState) -> Dict[str, Any]:
        """Nodo 4: Análisis de Texto (Con limpieza de SQL)"""
        print("--- 🧠 ANALYZING RESULTS ---")
        data = state.get("execution_result", [])
        
        if not data:
            return {"messages": [AIMessage(content="Sin resultados.")]}

        try:
            question = ""
            if state.get("messages") and len(state.get("messages", [])) > 0:
                question = state["messages"][-1].content or ""
            
            llm = HybridLLMFactory.get_model(temperature=0.2)
            prompt = ANALYSIS_SYSTEM.format(
                question=question, 
                data=str(data[:15]) # Limite de contexto
            )
            response = await llm.ainvoke([HumanMessage(content=prompt)])
            
            # --- LIMPIEZA DE ALUCINACIONES SQL ---
            content = response.content or ""
            # Regex: Elimina cualquier cosa que empiece con SELECT/WITH y termine en ;
            clean_content = re.sub(r'^\s*(SELECT|WITH|INSERT|UPDATE|DELETE).*?;', '', content, flags=re.IGNORECASE | re.DOTALL).strip()
            # Elimina bloques markdown de sql
            clean_content = re.sub(r'^```sql.*?```', '', clean_content, flags=re.IGNORECASE | re.DOTALL).strip()
            
            return {"messages": [AIMessage(content=clean_content)]}
            
        except Exception as e:
            return {"messages": [AIMessage(content=f"Error analizando: {str(e)}")]}

    async def generate_viz_config(self, state: AnalystState) -> Dict[str, Any]:
        """Nodo 5: Configuración de Gráfico (Con lógica KPI)"""
        print("--- 🎨 GENERATING VIZ ---")
        data = state.get("execution_result", [])
        
        # 1. Validaciones tempranas
        if not data:
             return {"viz_config": {"chart_type": "none"}}

        # REGLA SENIOR: Si es 1 sola fila, son KPIs. NO GRAFICAR.
        if isinstance(data, list) and len(data) == 1:
             print("ℹ️ Datos de una sola fila detectados. Omitiendo gráfico (KPIs).")
             return {"viz_config": {"chart_type": "none"}}

        if isinstance(data, list) and len(data) > 0:
             if 'NO_DATA' in str(data[0].values()):
                 return {"viz_config": {"chart_type": "none"}}

        try:
            llm_viz = HybridLLMFactory.get_model(temperature=0)
            
            question = ""
            if state.get("messages") and len(state.get("messages", [])) > 0:
                question = state["messages"][-1].content or ""
            
            prompt = VIZ_SYSTEM.format(data=str(data[:5]), question=question)
            
            response = await llm_viz.ainvoke([SystemMessage(content=prompt)])
            content = response.content or ""

            # Parser Regex Robusto
            patterns = [
                r'\{[^{}]*"chart_type"[^{}]*"x_column"[^{}]*"y_column"[^{}]*"title"[^{}]*\}',
                r'\{[^{}]*"chart_type"[^{}]*\}',
                r'\{.*\}'
            ]
            
            for pattern in patterns:
                json_match = re.search(pattern, content, re.DOTALL)
                if json_match:
                    try:
                        config = json.loads(json_match.group())
                        if "chart_type" in config:
                            return {"viz_config": config}
                    except json.JSONDecodeError:
                        continue
            
        except Exception as e:
            print(f"❌ Error Viz LLM: {e}")
        
        # 3. Fallback Automático
        print("🔄 Ejecutando fallback Viz...")
        if isinstance(data, list) and len(data) > 0:
            sample = data[0]
            keys = list(sample.keys())
            
            if len(keys) >= 2:
                import pandas as pd
                df_sample = pd.DataFrame(data[:5])
                
                # Inferencia de tipos para X (cat) e Y (num)
                x_col = next((c for c in df_sample.columns if df_sample[c].dtype in ['object', 'string']), keys[0])
                y_col = next((c for c in df_sample.columns if df_sample[c].dtype in ['int64', 'float64', 'int32']), keys[1] if len(keys)>1 else keys[0])
                
                return {
                    "viz_config": {
                        "chart_type": "bar",
                        "x_column": x_col,
                        "y_column": y_col,
                        "title": "Análisis de Datos"
                    }
                }
        
        return {"viz_config": {"chart_type": "none"}}

    async def generate_suggestions(self, schema_info: str) -> Dict[str, Any]:
        """
        Genera sugerencias proactivas al cargar datos.
        """
        print("--- 💡 GENERATING SUGGESTIONS ---")
        try:
            llm = HybridLLMFactory.get_model(temperature=0.4) # Más creativo
            
            prompt = SUGGESTION_SYSTEM.format(schema=schema_info)
            response = await llm.ainvoke([SystemMessage(content=prompt)])
            content = response.content or ""

            # Parser Regex
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            
            # Fallback
            return {
                "summary": "Dataset cargado correctamente. Puedes realizar análisis exploratorios.",
                "questions": ["Muestra un resumen de los datos", "Grafica las variables numéricas"]
            }
        except Exception as e:
            print(f"Error generando sugerencias: {e}")
            return {"summary": "Datos listos.", "questions": []}