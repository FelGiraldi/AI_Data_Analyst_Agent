# ---------------------------------------
# Stage 1: Builder (Velocidad con UV)
# ---------------------------------------
FROM python:3.11-slim as builder

WORKDIR /app

# 1. Instalar 'uv' (El instalador más rápido del mundo)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# 2. Copiar dependencias
COPY requirements.txt .

# 3. Crear entorno virtual e instalar dependencias usando uv
# Esto tarda segundos en lugar de minutos
ENV VIRTUAL_ENV=/opt/venv
RUN uv venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
RUN uv pip install -r requirements.txt

# ---------------------------------------
# Stage 2: Runner (Ligero)
# ---------------------------------------
FROM python:3.11-slim

WORKDIR /app

# Copiar el entorno virtual listo desde el Stage 1
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Variables de entorno
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Copiar el código fuente
COPY . .

# Exponer puerto
EXPOSE 8501

# Healthcheck
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Comando de arranque
CMD ["streamlit", "run", "interface/streamlit/app.py", "--server.port=8501", "--server.address=0.0.0.0"]