# ========================================================
# Dockerfile - Pedidos Granodoc (Gestão de Suprimentos)
# Otimizado para Deploy na Nuvem (Render, Railway, Fly.io)
# ========================================================

FROM python:3.12-slim

# Evita geração de arquivos .pyc e ativa buffer imediato de logs
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    GRANODOC_DB_PATH=/app/data/pedidos_granodoc.db

# Diretório padrão da aplicação
WORKDIR /app

# Instala curl para verificação de integridade (HEALTHCHECK)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instala dependências do Python primeiro para otimização de cache do Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Cria diretório de persistência de dados para o SQLite
RUN mkdir -p /app/data

# Copia todos os arquivos da aplicação
COPY . /app

# Declara o volume de dados persistente (evita perda de banco de dados em redeploys)
VOLUME ["/app/data"]

# Expõe a porta padrão
EXPOSE 8000

# Healthcheck que monitora a integridade do serviço em produção
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/login || exit 1

# Inicializa o Uvicorn respeitando a variável de ambiente $PORT fornecida pela nuvem
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"]
