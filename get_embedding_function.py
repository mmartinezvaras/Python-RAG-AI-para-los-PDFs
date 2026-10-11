"""Embedding provider factory.

By default everything runs locally with Ollama (no accounts, no API keys).
Set RAG_EMBEDDINGS=bedrock to use AWS Bedrock instead
(requires `pip install langchain-aws` and an AWS profile with Bedrock access).

Note: the vector database must be rebuilt (`python populate_database.py --reset`)
whenever you switch embedding provider or model.
"""

import os

EMBEDDING_PROVIDER = os.getenv("RAG_EMBEDDINGS", "ollama").lower()
OLLAMA_EMBED_MODEL = os.getenv("RAG_EMBED_MODEL", "nomic-embed-text")


def get_embedding_function():
    if EMBEDDING_PROVIDER == "bedrock":
        from langchain_aws import BedrockEmbeddings

        return BedrockEmbeddings(
            credentials_profile_name=os.getenv("AWS_PROFILE", "default"),
            region_name=os.getenv("AWS_REGION", "us-east-1"),
        )

    from langchain_ollama import OllamaEmbeddings

    return OllamaEmbeddings(model=OLLAMA_EMBED_MODEL)
