# Changelog

## v0.5.0

Added:

* Task Console
* /workspace command
* /task command
* /task new <title>
* /task plan
* /task step <text>
* /task done <number>
* /task note <text>
* /task review
* /task close
* /task clear
* /q exit alias
* core\task_manager.py
* ui\task_views.py
* data\tasks storage
* task archive storage
* task checks in health-check

Changed:

* version updated to v0.5.0
* /help updated with Task Console commands
* /status now shows Task Console state
* startup command hint updated

## v0.3.1

Stabilization release for Documents / RAG.

Added:

* /status command
* improved /docs list
* improved /docs search <query>
* typo hints for /docs commands
* health-check script: scripts/check_v033.py

Changed:

* version updated to v0.3.1
* documents index handling improved
* service files are hidden from /docs list
* service files are ignored by document ingestion

Fixed:

* empty /docs search query handling
* missing index handling
* broken index handling
* accidental display of .gitkeep in documents list

## v0.3.0

Initial Documents / RAG scaffold.

## v0.2.x

Stable local CLI coding-agent foundation.
