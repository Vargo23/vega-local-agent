# VEGA v0.3 — Documents / RAG Architecture

## Goal

VEGA v0.3 adds local document support without breaking v0.2.2.

The agent should be able to:
- read local project documents;
- index text files;
- search indexed content;
- show which source files were used;
- work offline by default.

## Important Rule

v0.3 extends the current agent.

It must not break:
- banner startup;
- short launch command: vega;
- local launcher: .\vega;
- desktop launcher: VEGA.cmd;
- /status;
- /model;
- /log;
- logs/sessions.

## Folder Structure

VEGA_agent_package/
- data/documents/ — user documents
- data/index/ — generated local indexes
- rag/ — document ingestion and search logic
- docs/ — project documentation
- logs/sessions/ — session logs
- logs/checks/ — check reports

## First Supported File Types

Start only with simple text-based files:

.txt
.md
.py
.json
.yaml
.yml

Do not add PDF or DOCX in the first implementation.

## Patch Order

v0.3.0:
- create folders;
- create documentation;
- create checks.

v0.3.1:
- add document ingestion;
- scan data/documents;
- split files into chunks;
- save JSON index into data/index.

v0.3.2:
- add keyword search over indexed chunks.

v0.3.3:
- connect commands to VEGA CLI:
  - /docs
  - /docs list
  - /docs index
  - /docs search <query>

v0.3.4:
- add optional semantic search with Ollama embeddings.

## Safety Rules

- Do not send local documents to the internet.
- Do not pretend a document was read if it was not indexed.
- Always show source file paths.
- Empty document folder must not crash the agent.
- If nothing is found, say so directly.

## Coordinator Review Gate

Before closing v0.3:

[PASS] VEGA launches
[PASS] banner appears
[PASS] /status works
[PASS] /model works
[PASS] /log works
[PASS] data/documents exists
[PASS] data/index exists
[PASS] rag exists
[PASS] architecture doc exists
[PASS] document ingestion works
[PASS] document search works
[PASS] /docs commands work

## Current Status

v0.3.0 scaffold stage.
Next patch: v0.3.1 document ingestion.
