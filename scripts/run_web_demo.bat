@echo off
echo Starting VEGA Remote Demo...
echo Open http://localhost:8000
python -m uvicorn web_demo.server:app --host 127.0.0.1 --port 8000
