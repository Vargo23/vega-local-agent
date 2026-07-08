# VEGA RAG Module

This folder is for VEGA v0.3 document/RAG logic.

Planned files:

- ingest.py — scan and chunk local documents
- store.py — save and load local JSON index
- search.py — keyword search over indexed chunks

First implementation rule:

Do not add heavy frameworks yet.
Do not add LangChain, LlamaIndex or Chroma at this stage.
Start with simple local JSON indexing.

Patch order:

1. v0.3.1 — document ingestion
2. v0.3.2 — keyword search
3. v0.3.3 — CLI commands
4. v0.3.4 — optional embeddings
