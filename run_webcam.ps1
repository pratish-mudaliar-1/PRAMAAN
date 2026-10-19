# PRAMAAN - Live Webcam Edge Agent (YOLOv8) Launcher
Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host "PRAMAAN - Starting Live Laptop Webcam Edge Agent (YOLOv8)" -ForegroundColor Green
Write-Host "=====================================================================" -ForegroundColor Cyan

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonExe = Join-Path $scriptDir "backend\.venv\Scripts\python.exe"
$agentPy   = Join-Path $scriptDir "backend\scripts\webcam_edge_agent.py"

& $pythonExe $agentPy --interval-seconds 10 --api-url http://localhost:8001
