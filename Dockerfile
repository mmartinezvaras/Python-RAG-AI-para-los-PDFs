# Self-contained online demo: Ollama + models + indexed PDFs + Streamlit app.
# Used by the Hugging Face Space (port 7860); also runs anywhere with Docker:
#   docker build -t rag-demo . && docker run -p 7860:7860 rag-demo
FROM python:3.12-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates zstd procps \
 && rm -rf /var/lib/apt/lists/* \
 && curl -fsSL https://ollama.com/install.sh | sh

# Hugging Face Spaces runs the container as user 1000.
RUN useradd -m -u 1000 user \
 && mkdir -p /home/user/app && chown user:user /home/user/app
ENV HOME=/home/user \
    OLLAMA_MODELS=/home/user/.ollama/models \
    RAG_PUBLIC_DEMO=1 \
    PYTHONUNBUFFERED=1
WORKDIR /home/user/app

COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=user . .
USER user

# Bake the models and the vector index into the image so the demo starts fast.
RUN bash docker/build_index.sh

EXPOSE 7860
CMD ["bash", "docker/start.sh"]
