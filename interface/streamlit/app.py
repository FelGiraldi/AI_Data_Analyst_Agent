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

# --- CSS  ---
st.markdown("""
<style>
    /* Global Font */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    
    .stApp { background-color: #0e1117; }
    
    /* Header & Sidebar */
    header[data-testid="stHeader"] { background-color: transparent; z-index: 1; }
    section[data-testid="stSidebar"] { background-color: #161b22; border-right: 1px solid #30363d; }
    
    /* Métricas */
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, #1f2937 0%, #111827 100%);
        border: 1px solid #374151;
        border-radius: 12px;
        padding: 15px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: transparent;
        border-radius: 4px 4px 0px 0px;
        gap: 1px;
        padding-top: 10px;
        padding-bottom: 10px;
    }
    
    /* Botones */
    div.stButton > button[kind="primary"] {
        background-color: #238636;
        color: white;
        border-radius: 6px;
        font-weight: 600;
    }
    div.stButton > button:contains("Nueva Conversación") {
        border-color: #da3633; color: #f85149;
    }
    
    /* Chat Bubbles */
    .stChatMessage { padding: 1rem; border-radius: 12px; margin-bottom: 0.5rem; }
    .stChatMessage[data-testid="stChatMessage"]:nth-child(odd) { background-color: #151b23; border: 1px solid #30363d; }
    .stChatMessage[data-testid="stChatMessage"]:nth-child(even) { background-color: #1c2a3a; border: 1px solid #1f6feb; }
    
    /* Elementos Ocultos */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    div[data-testid="stDecoration"] {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# --- 3. SINGLETONS ---
@st.cache_resource
def get_infra(): return DuckDBAdapter(db_path=":memory:")

@st.cache_resource
def get_agent(_db): return build_analyst_graph(_db)

@st.cache_resource
def get_nodes(_db): return AgentNodes(_db)

# --- 4. LÓGICA VISUAL ---

def render_chart(df, config, key_suffix=""):
    """Genera gráficos Plotly."""
    try:
        chart_type = config.get("chart_type")
        title = config.get("title", "Visualización")
        cols = df.columns.tolist()
        x_col, y_col = config.get("x_column"), config.get("y_column")
        
        if x_col not in cols: x_col = cols[0]
        if y_col not in cols and len(cols) > 1: y_col = cols[1]

        common = dict(template="plotly_dark", height=450)

        if chart_type == "bar": fig = px.bar(df, x=x_col, y=y_col, title=title, color=x_col, **common)
        elif chart_type == "line": fig = px.line(df, x=x_col, y=y_col, title=title, markers=True, **common)
        elif chart_type == "scatter": fig = px.scatter(df, x=x_col, y=y_col, title=title, size=y_col if pd.api.types.is_numeric_dtype(df[y_col]) else None, **common)
        elif chart_type == "pie": fig = px.pie(df, names=x_col, values=y_col, title=title, template="plotly_dark")
        elif chart_type == "histogram": 
            fig = px.histogram(df, x=x_col, title=title, **common)
            fig.update_layout(bargap=0.1)
        elif chart_type == "box":
            fig = px.box(df, y=x_col, title=title, **common) if pd.api.types.is_numeric_dtype(df[x_col]) else px.box(df, x=x_col, y=y_col, title=title, **common)
        else: return

        st.plotly_chart(fig, use_container_width=True, key=f"chart_{uuid.uuid4()}_{key_suffix}")

    except Exception as e:
        st.warning(f"⚠️ Error gráfico: {str(e)}")

def render_message(msg, index):
    """Renderiza un mensaje del chat."""
    role, content = msg["role"], msg.get("content", "")
    viz_config, raw_data = msg.get("viz_config", {}), msg.get("data", [])

    with st.chat_message(role):
        if content: st.markdown(content)
        
        if raw_data and isinstance(raw_data, list) and len(raw_data) > 0:
            df_viz = pd.DataFrame(raw_data)
            
            # A. KPIs
            if len(df_viz) == 1:
                st.markdown("---")
                cols = st.columns(min(len(df_viz.columns), 4))
                for idx, col in enumerate(df_viz.columns[:4]):
                    val = df_viz.iloc[0][col]
                    d_val = f"{val:,.2f}" if isinstance(val, (int, float)) else str(val)
                    cols[idx].metric(col.replace("_", " ").title(), d_val)
            
            # B. Acciones (Descargar y Anclar)
            if len(df_viz) > 0:
                c1, c2 = st.columns([1, 1])
                csv = df_viz.to_csv(index=False).encode('utf-8')
                c1.download_button("⬇️ CSV", csv, f"data_{index}.csv", "text/csv", key=f"dl_{index}")
                
                # BOTÓN DE PINNING
                if viz_config.get("chart_type") != "none":
                    if c2.button("📌 Anclar", key=f"pin_{index}"):
                        # Guardar en dashboard
                        if "pinned_charts" not in st.session_state:
                            st.session_state["pinned_charts"] = []
                        st.session_state["pinned_charts"].append({
                            "config": viz_config,
                            "data": raw_data,
                            "id": str(uuid.uuid4())
                        })
                        st.toast("✅ Gráfico anclado al Dashboard", icon="📌")

            # C. Gráfico
            if viz_config.get("chart_type") != "none":
                is_stats = viz_config.get("chart_type") in ["histogram", "box"]
                if is_stats and len(df_viz) < 5: st.caption("ℹ️ Datos insuficientes para distribución.")
                else: 
                    st.divider()
                    render_chart(df_viz, viz_config, key_suffix=f"msg_{index}")

def render_dashboard():
    """Renderiza la pestaña de Dashboard."""
    st.header("📌 Executive Dashboard")
    
    if "pinned_charts" not in st.session_state or not st.session_state["pinned_charts"]:
        st.info("👋 Tu dashboard está vacío. Ve al chat y presiona '📌 Anclar' en cualquier gráfico para agregarlo aquí.")
        return

    # Botón borrar todo
    if st.button("🗑️ Limpiar Dashboard"):
        st.session_state["pinned_charts"] = []
        st.rerun()

    st.markdown("---")
    
    # Grid Layout (2 columnas)
    charts = st.session_state["pinned_charts"]
    
    # Iterar en pasos de 2 para crear filas
    for i in range(0, len(charts), 2):
        c1, c2 = st.columns(2)
        
        # Gráfico 1
        with c1:
            item = charts[i]
            with st.container(border=True):
                df = pd.DataFrame(item["data"])
                render_chart(df, item["config"], key_suffix=f"dash_{item['id']}")
                if st.button("❌ Quitar", key=f"del_{item['id']}"):
                    st.session_state["pinned_charts"].pop(i)
                    st.rerun()
        
        # Gráfico 2 (si existe)
        if i + 1 < len(charts):
            with c2:
                item = charts[i+1]
                with st.container(border=True):
                    df = pd.DataFrame(item["data"])
                    render_chart(df, item["config"], key_suffix=f"dash_{item['id']}")
                    if st.button("❌ Quitar", key=f"del_{item['id']}"):
                        st.session_state["pinned_charts"].pop(i+1)
                        st.rerun()

# --- 5. MAIN ---
def main():
    # --- SIDEBAR ---
    with st.sidebar:
        st.title("🤖 AI Analyst")
        uploaded_file = st.file_uploader("Data Source", type=["csv", "xlsx"])
        
        if uploaded_file:
            ext = os.path.splitext(uploaded_file.name)[1]
            temp_path = f"temp_upload{ext}"
            with open(temp_path, "wb") as f: f.write(uploaded_file.getbuffer())
            
            db = get_infra()
            if st.button("🚀 Ingestar", type="primary", use_container_width=True):
                with st.spinner("Procesando..."):
                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        schema = loop.run_until_complete(db.load_file(temp_path, "dataset_usuario"))
                        st.session_state["current_schema"] = schema.get_context_for_llm()
                        
                        nodes = get_nodes(db)
                        suggestions = loop.run_until_complete(nodes.generate_suggestions(schema.get_context_for_llm()))
                        st.session_state["suggestions"] = suggestions
                        
                        st.success("✅ Indexado")
                    except Exception as e: st.error(f"Error: {e}")
            if os.path.exists(temp_path): os.remove(temp_path)

        if "current_schema" in st.session_state:
            st.divider()
            if st.button("🗑️ Reset Chat", use_container_width=True):
                st.session_state["chat_history"] = []
                st.session_state["last_sql_memory"] = None
                st.rerun()

        if "suggestions" in st.session_state:
            st.divider()
            st.caption(st.session_state["suggestions"].get("summary", ""))
            for q in st.session_state["suggestions"].get("questions", []):
                if st.button(f"👉 {q}"):
                    st.session_state["triggered_question"] = q
                    st.rerun()

    # --- TABS PRINCIPALES ---
    tab_chat, tab_dash = st.tabs(["💬 Chat & Analysis", "📌 Dashboard"])

    # --- TAB 1: CHAT ---
    with tab_chat:
        if "chat_history" not in st.session_state: st.session_state.chat_history = []
        for i, msg in enumerate(st.session_state.chat_history): render_message(msg, i)

        manual_input = st.chat_input("Pregunta sobre tus datos...")
        triggered_input = st.session_state.pop("triggered_question", None)
        user_input = triggered_input if triggered_input else manual_input

        if user_input:
            if "current_schema" not in st.session_state:
                st.warning("⚠️ Sube un archivo primero.")
            else:
                user_msg = {"role": "user", "content": user_input}
                st.session_state.chat_history.append(user_msg)
                render_message(user_msg, len(st.session_state.chat_history)-1)

                with st.chat_message("assistant"):
                    result = None
                    with st.status("🧠 Analizando...", expanded=True) as status:
                        lc_messages = []
                        for m in st.session_state.chat_history:
                            if m["role"] == "user": lc_messages.append(HumanMessage(content=m["content"]))
                            else: lc_messages.append(AIMessage(content=m.get("content", "")))

                        db = get_infra()
                        agent = get_agent(db)
                        state = {
                            "messages": lc_messages, 
                            "schema_info": st.session_state["current_schema"],
                            "last_successful_sql": st.session_state.get("last_sql_memory")
                        }
                        
                        final_res = {"role": "assistant", "content": "", "viz_config": {}, "data": []}

                        async def run():
                            async for event in agent.astream(state):
                                for node, update in event.items():
                                    if "sql_query" in update: 
                                        status.write("🔧 SQL generado...")
                                        status.code(update["sql_query"], language="sql")
                                    if "error" in update and update["error"]: status.warning("⚠️ Corrigiendo...")
                                    if "execution_result" in update:
                                        status.write("✅ Datos obtenidos")
                                        final_res["data"] = update["execution_result"]
                                        if "last_successful_sql" in update:
                                            st.session_state["last_sql_memory"] = update["last_successful_sql"]
                                    if "viz_config" in update:
                                        status.write("🎨 Generando gráfico...")
                                        final_res["viz_config"] = update["viz_config"]
                                    if "messages" in update: final_res["content"] = update["messages"][-1].content
                            return final_res

                        try:
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            result = loop.run_until_complete(run())
                            status.update(label="✅ Listo", state="complete", expanded=False)
                        except Exception as e:
                            status.update(label="❌ Error", state="error")
                            st.error(f"Error: {e}")

                    if result:
                        st.session_state.chat_history.append(result)
                        render_message(result, len(st.session_state.chat_history)-1)

    # --- TAB 2: DASHBOARD ---
    with tab_dash:
        render_dashboard()

if __name__ == "__main__":
    main()