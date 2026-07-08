# VEGA v0.3.1 Test Document

VEGA is a local project coding-agent.

Current stage:
- v0.2.2: stable CLI agent with banner and short launch.
- v0.3.0: document/RAG scaffold.
- v0.3.1: local document ingestion.

The document ingestion module scans data/documents, reads supported text files, splits them into chunks, and saves a local JSON index into data/index/documents_index.json.

This stage does not use embeddings yet.
This stage does not modify the main VEGA CLI.
