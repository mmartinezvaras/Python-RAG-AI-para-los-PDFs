"""Publish this repository as a Hugging Face Space (Docker) for the online demo.

Needs the HF_TOKEN environment variable (a Hugging Face token with write access).
"""

import os
import tempfile

from huggingface_hub import HfApi

SPACE_NAME = os.getenv("HF_SPACE_NAME", "rag-over-pdfs")
GITHUB_URL = "https://github.com/mmartinezvaras/Python-RAG-AI-para-los-PDFs"

SPACE_README = f"""---
title: RAG over PDFs
emoji: 📄
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
short_description: Ask PDFs questions, get answers with cited sources
---

# RAG over PDFs

Ask questions about the sample PDFs and get answers generated **only** from the
documents, with the exact file, page and chunk each answer comes from.
Runs a local LLM (Llama 3.2 3B via Ollama) on the free CPU, so answers take a few seconds.

Source code, architecture and tests: {GITHUB_URL}
"""

def fail(step: str, exc: Exception):
    msg = f"{step}: {type(exc).__name__}: {exc}".replace("\n", "%0A")
    print(f"::error title=Hugging Face deploy failed::{msg}")
    raise SystemExit(1)


api = HfApi(token=os.environ["HF_TOKEN"].strip())
try:
    user = api.whoami()["name"]
except Exception as exc:
    fail("Checking the HF_TOKEN secret (is it pasted correctly?)", exc)
repo_id = f"{user}/{SPACE_NAME}"

try:
    api.create_repo(repo_id, repo_type="space", space_sdk="docker", exist_ok=True)
except Exception as exc:
    fail(f"Creating the Space {repo_id} (does the token have Write access?)", exc)

with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as fh:
    fh.write(SPACE_README)
    readme_path = fh.name

try:
    api.upload_folder(
        repo_id=repo_id,
        repo_type="space",
        folder_path=".",
        ignore_patterns=[".git/*", ".github/*", ".devcontainer/*", "docs/*", "chroma/*", "README.md", "**/__pycache__/*"],
        commit_message="Deploy from GitHub",
    )
    api.upload_file(
        repo_id=repo_id, repo_type="space", path_or_fileobj=readme_path, path_in_repo="README.md",
        commit_message="Space README",
    )
except Exception as exc:
    fail(f"Uploading the files to {repo_id}", exc)

url = f"https://huggingface.co/spaces/{repo_id}"
print(f"::notice title=Live demo deployed::{url}")
