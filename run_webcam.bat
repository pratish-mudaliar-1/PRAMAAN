@echo off
title PRAMAAN - Live Webcam Edge Agent (YOLOv8)
echo =====================================================================
echo PRAMAAN - Live Webcam Edge Agent (YOLOv8n CPU Inference)
echo =====================================================================
set "PATH=C:\Users\Pratish\AppData\Local\Programs\Python\Python312\Scripts;C:\Users\Pratish\AppData\Local\Programs\Python\Python312;%PATH%"
"%~dp0backend\.venv\Scripts\python.exe" "%~dp0backend\scripts\webcam_edge_agent.py" --interval-seconds 10 --api-url http://localhost:8001
pause
