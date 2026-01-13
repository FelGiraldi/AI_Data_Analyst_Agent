import sys
import os
import asyncio
import uuid
from pathlib import Path
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage
import plotly.express as px

# --- 1. CONFIGURACIÓN DE PATH ---
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent.parent
sys.path.append(str(project_root))

from infrastructure.persistence.duckdb_adapter import DuckDBAdapter
from application.graph import build_analyst_graph
from application.nodes import AgentNodes

# --- 2. CONFIGURACIÓN UI ---
st.set_page_config(
    page_title="AI Data Analyst",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)
load_dotenv()

# --- CSS ---
st.markdown("""
<style>
    /* 1. FUENTES Y FONDO GLOBAL */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    .stApp {
        background-color: #0e1117;
    }
    
    /* 2. HEADER Y SIDEBAR */
    header[data-testid="stHeader"] {
        background-color: transparent;
        z-index: 1;
    }
    
    section[data-testid="stSidebar"] {
        background-color: #161b22;
        border-right: 1px solid #30363d;
    }
    
    /* 3. TARJETAS DE MÉTRICAS (KPIs) */
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, #1f2937 0%, #111827 100%);
        border: 1px solid #374151;
        border-radius: 12px;
        padding: 15px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
        transition: transform 0.2s;
    }
    div[data-testid="stMetric"]:hover {
        transform: translateY(-2px);
        border-color: #3b82f6;
    }

    /* 4. CHAT BUBBLES */
    .stChatMessage[data-testid="stChatMessage"]:nth-child(odd) {
        background-color: #151b23; 
        border: 1px solid #30363d;
        border-radius: 12px;
    }
    .stChatMessage[data-testid="stChatMessage"]:nth-child(even) {
        background-color: #1c2a3a;
        border: 1px solid #1f6feb;
        border-radius: 12px;
    }

    /* 5. BOTONES */
    div.stButton > button[kind="primary"] {
        background-color: #238636;
        color: white;
        border-radius: 6px;
        font-weight: 600;
    }
    
    /* Botón Nueva Conversación (Rojo) */
    div.stButton > button:contains("Nueva Conversación") {
        border-color: #da3633;
        color: #f85149;
    }
    div.stButton > button:contains("Nueva Conversación"):hover {
        background-color: #b62324;
        color: white;
    }

    /* Botones de sugerencias */
    div[data-testid="stSidebar"] div.stButton > button {
        background-color: #21262d;
        color: #c9d1d9;
        border: 1px solid #30363d;
        text-align: left;
    }
    div[data-testid="stSidebar"] div.stButton > button:hover {
        border-color: #8b949e;
        color: white;
    }

    /* 6. OTROS */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    div[data-testid="stDecoration"] {visibility: hidden;}
    div[data-testid="stStatusWidget"] {
        background-color: #0d1117;
        border: 1px solid #30363d;
    }
    .stCodeBlock {
        background-color: #0d1117 !important;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. SINGLETONS ---
@st.cache_resource
def get_infra():
    return DuckDBAdapter(db_path=":memory:")

@st.cache_resource
def get_agent(_db):
    return build_analyst_graph(_db)

@st.cache_resource
def get_nodes(_db):
    return AgentNodes(_db)

# --- 4. RENDERIZADO VISUAL ---

def render_chart(df, config):
    try:
        chart_type = config.get("chart_type")
        title = config.get("title", "Visualización")
        cols = df.columns.tolist()
        
        x_col = config.get("x_column")
        y_col = config.get("y_column")
        
        if x_col not in cols: x_col = cols[0]
        if y_col not in cols and len(cols) > 1: y_col = cols[1]

        common_layout = dict(template="plotly_dark", height=500)

        if chart_type == "bar":
            fig = px.bar(df, x=x_col, y=y_col, title=title, color=x_col, **common_layout)
        elif chart_type == "line":
            fig = px.line(df, x=x_col, y=y_col, title=title, markers=True, **common_layout)
        elif chart_type == "scatter":
            fig = px.scatter(df, x=x_col, y=y_col, title=title, size=y_col if pd.api.types.is_numeric_dtype(df[y_col]) else None, **common_layout)
        elif chart_type == "pie":
            fig = px.pie(df, names=x_col, values=y_col, title=title, template="plotly_dark")
        elif chart_type == "histogram":
            fig = px.histogram(df, x=x_col, title=title, **common_layout)
            fig.update_layout(bargap=0.1)
        elif chart_type == "box":
            if pd.api.types.is_numeric_dtype(df[x_col]):
                fig = px.box(df, y=x_col, title=title, **common_layout)
            else:
                fig = px.box(df, x=x_col, y=y_col, title=title, **common_layout)
        else:
            return 

        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.warning(f"⚠️ Error gráfico: {str(e)}")

def render_message(msg, msg_index):
    role = msg["role"]
    content = msg.get("content", "")
    viz_config = msg.get("viz_config", {})
    raw_data = msg.get("data", [])

    with st.chat_message(role):
        if content:
            st.markdown(content)
        
        if raw_data is not None and isinstance(raw_data, list) and len(raw_data) > 0:
            df_viz = pd.DataFrame(raw_data)
            
            # A. KPIs
            if len(df_viz) == 1:
                st.markdown("---")
                cols_ui = st.columns(min(len(df_viz.columns), 4))
                for idx, col_name in enumerate(df_viz.columns[:4]):
                    val = df_viz.iloc[0][col_name]
                    display_val = f"{val:,.2f}" if isinstance(val, (int, float)) else str(val)
                    cols_ui[idx].metric(label=col_name.replace("_", " ").title(), value=display_val)
            
            # B. Botón Descarga
            if len(df_viz) > 0:
                csv = df_viz.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="⬇️ Descargar Resultados",
                    data=csv,
                    file_name=f"analisis_export_{msg_index}.csv",
                    mime="text/csv",
                    key=f"dl_{msg_index}_{uuid.uuid4()}"
                )

            # C. Gráficos
            if viz_config and viz_config.get("chart_type") != "none":
                is_stats_chart = viz_config.get("chart_type") in ["histogram", "box"]
                is_small_data = len(df_viz) < 5
                
                if is_stats_chart and is_small_data:
                    st.caption("ℹ️ Datos insuficientes para distribución.")
                else:
                    st.divider()
                    render_chart(df_viz, viz_config)

# --- 5. MAIN APP ---
def main():
    st.title("📊 AI Analytics Dashboard")
    
    # --- SIDEBAR ---
    with st.sidebar:
        st.header("📂 Origen de Datos")
        uploaded_file = st.file_uploader("Sube CSV o Excel", type=["csv", "xlsx"])
        
        if uploaded_file:
            ext = os.path.splitext(uploaded_file.name)[1]
            temp_path = f"temp_upload{ext}"
            with open(temp_path, "wb") as f: f.write(uploaded_file.getbuffer())
            
            db = get_infra()
            if st.button("🚀 Ingestar y Analizar", type="primary"):
                with st.spinner("Procesando..."):
                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        schema = loop.run_until_complete(db.load_file(temp_path, "dataset_usuario"))
                        
                        st.session_state["current_schema"] = schema.get_context_for_llm()
                        st.session_state["chat_history"] = []
                        
                        # Generar Sugerencias
                        nodes = get_nodes(db)
                        suggestions = loop.run_until_complete(nodes.generate_suggestions(schema.get_context_for_llm()))
                        st.session_state["suggestions"] = suggestions
                        
                        st.success("✅ Datos Indexados")
                    except Exception as e:
                        st.error(f"Error: {e}")
            
            if os.path.exists(temp_path): os.remove(temp_path)

        # --- BOTÓN NUEVA CONVERSACIÓN  ---
        if "current_schema" in st.session_state:
            st.divider()
            if st.button("🗑️ Nueva Conversación", use_container_width=True):
                st.session_state["chat_history"] = []
                st.session_state["last_sql_memory"] = None
                st.session_state["triggered_question"] = None
                st.rerun()

        # Sugerencias
        if "suggestions" in st.session_state:
            st.divider()
            st.subheader("💡 Sugerencias")
            st.caption(st.session_state["suggestions"].get("summary", ""))
            
            st.markdown("**Prueba analizando:**")
            for q in st.session_state["suggestions"].get("questions", []):
                if st.button(f"👉 {q}"):
                    st.session_state["triggered_question"] = q
                    st.rerun()

    # --- HISTORIAL ---
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    for i, msg in enumerate(st.session_state.chat_history):
        render_message(msg, i)

    # --- INPUT ---
    manual_input = st.chat_input("Escribe tu pregunta...")
    triggered_input = st.session_state.pop("triggered_question", None)
    user_input = triggered_input if triggered_input else manual_input

    if user_input:
        if "current_schema" not in st.session_state:
            st.warning("⚠️ Sube un archivo primero.")
            return

        # 1. User Msg
        user_msg = {"role": "user", "content": user_input}
        st.session_state.chat_history.append(user_msg)
        render_message(user_msg, len(st.session_state.chat_history)-1)

        # 2. Assistant Msg
        with st.chat_message("assistant"):
            result = None

            with st.status("🧠 Analizando datos...", expanded=True) as status:
                
                lc_messages = []
                for m in st.session_state.chat_history:
                    if m["role"] == "user": lc_messages.append(HumanMessage(content=m["content"]))
                    else: lc_messages.append(AIMessage(content=m.get("content", "")))

                db = get_infra()
                agent = get_agent(db)
                
                state = {
                    "messages": lc_messages, 
                    "schema_info": st.session_state["current_schema"],
                    "last_successful_sql": st.session_state.get("last_sql_memory"),
                    "retry_count": 0
                }

                final_res = {"role": "assistant", "content": "", "viz_config": {}, "data": []}

                async def run_workflow():
                    async for event in agent.astream(state):
                        for node, update in event.items():
                            if "sql_query" in update:
                                status.write(f"🔧 Generando SQL...")
                                status.code(update['sql_query'], language="sql")
                            
                            if "error" in update and update["error"]:
                                status.warning(f"⚠️ Corrigiendo consulta...")
                            
                            if "execution_result" in update:
                                status.write("✅ Datos obtenidos.")
                                final_res["data"] = update["execution_result"]
                                if "last_successful_sql" in update:
                                    st.session_state["last_sql_memory"] = update["last_successful_sql"]

                            if "viz_config" in update:
                                status.write("🎨 Diseñando gráfico...")
                                final_res["viz_config"] = update["viz_config"]
                            
                            if "messages" in update:
                                final_res["content"] = update["messages"][-1].content
                    return final_res

                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    result = loop.run_until_complete(run_workflow())
                    
                    status.update(label="✅ Completado", state="complete", expanded=False)
                
                except Exception as e:
                    status.update(label="❌ Error", state="error")
                    st.error(f"Error inesperado: {str(e)}")
                    result = None

            if result:
                st.session_state.chat_history.append(result)
                render_message(result, len(st.session_state.chat_history)-1)

if __name__ == "__main__":
    main()