# VEGA Project State

## Current stable version

v0.5.0

## Main entrypoint

scripts\vega.py

## Current model

vega-core

## Current interface

CLI with Task Console.

## Current stable features

* Startup screen
* Interactive CLI
* Session logs
* Help command
* Status command
* Workspace command
* Task Console
* Local Documents / RAG
* Document indexing
* Document search
* Health-check script

## Important folders

core\

Core project logic.

scripts\

Main executable scripts.

ui\

Startup screen and terminal rendering.

rag\

Documents / RAG logic.

data\documents\

User documents for indexing.

data\index\

Generated document index.

data\tasks\

Current Task Console state.

data\tasks\archive\

Archived completed tasks.

logs\sessions\

Session logs.

config\

Project config.

ollama\

Ollama model configuration.

## Important files

core\task_manager.py

Task Console storage and task workflow logic.

ui\task_views.py

Task Console terminal output formatting.

## Do not change without reason

* scripts\vega.py
* core\task_manager.py
* ui\task_views.py
* rag\commands.py
* rag\ingest.py
* ui\startup_screen.py
* ollama\Modelfile

## Next planned stage

Undecided.

Do not start GUI, model profiles, internet tools, or GitHub setup unless explicitly requested.
