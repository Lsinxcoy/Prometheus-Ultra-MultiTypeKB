@echo off
chcp 65001 >nul
set REPO=E:\Prometheus-Ultra-MultiTypeKB
set PYTHON=%REPO%\.venv\Scripts\python.exe
set DB=%REPO%\src\prometheus_ultra.db
cd /d "%REPO%"
echo [Ultra] Starting API server on 127.0.0.1:9200 (db=%DB%)...
start "Ultra-API-9200" "%PYTHON%" -m prometheus_ultra.services.api_server --host 127.0.0.1 --port 9200 --db-path "%DB%"
echo [Ultra] launched.
