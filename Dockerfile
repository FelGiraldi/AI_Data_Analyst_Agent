# ---------------------------------------
# Stage 1: Builder (Compilación)
# ---------------------------------------
FROM python:3.11-slim as builder

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copiar dependencias
COPY requirements.txt .

# Crear virtual environment y compilar wheels
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir -r requirements.txt

# ---------------------------------------
# Stage 2: Runner (Ejecución Ligera)
# ---------------------------------------
FROM python:3.11-slim

WORKDIR /app

# Copiar el entorno virtual desde el Stage 1
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Variables de entorno críticas
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Copiar el código fuente
COPY . .

# Exponer el puerto de Streamlit
EXPOSE 8501

# Healthcheck para saber si la app está viva
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Comando de arranque
CMD ["streamlit", "run", "interface/streamlit/app.py", "--server.port=8501", "--server.address=0.0.0.0"]