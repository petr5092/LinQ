# Скрипт быстрого запуска LinQ Safety Guard (Backend + Frontend)
param (
    [switch]$Standalone,
    [string]$Backend = "ONNX_CPU"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "         Запуск LinQ Safety Guard [Dev Server]          " -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

# 1. Проверка виртуального окружения Python
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    $PythonExe = Join-Path $ProjectRoot "venv\Scripts\python.exe"
}
if (-not (Test-Path $PythonExe)) {
    Write-Error "Виртуальное окружение не найдено (.venv или venv)!"
}

# 2. Запуск в режиме Standalone (быстрое локальное демо без Node.js)
if ($Standalone) {
    Write-Host "[1/1] Запуск автономного демо на встроенном сервере (порт 8000)..." -ForegroundColor Green
    & $PythonExe run.py --standalone
    exit 0
}

# 3. Запуск Backend (FastAPI + uvicorn)
Write-Host "[1/2] Запуск FastAPI Backend (http://localhost:8000)..." -ForegroundColor Green
$env:INFERENCE_BACKEND = $Backend
$BackendJob = Start-Process -FilePath $PythonExe -ArgumentList "run.py" -WorkingDirectory $ProjectRoot -PassThru

# 4. Запуск Frontend (Vite dev server)
Write-Host "[2/2] Запуск Frontend (http://localhost:3000)..." -ForegroundColor Green
$FrontendDir = Join-Path $ProjectRoot "frontend"
$FrontendJob = Start-Process -FilePath "npm.cmd" -ArgumentList "run", "dev" -WorkingDirectory $FrontendDir -PassThru

Write-Host "`nСервисы запущены:" -ForegroundColor Cyan
Write-Host "  - UI Диспетчера: http://localhost:3000" -ForegroundColor Yellow
Write-Host "  - API Swagger:    http://localhost:8000/docs" -ForegroundColor Yellow
Write-Host "`nНажмите Ctrl+C для остановки процессов PID $($BackendJob.Id) и $($FrontendJob.Id)..."

try {
    Wait-Process -Id $BackendJob.Id, $FrontendJob.Id
} finally {
    Stop-Process -Id $BackendJob.Id -ErrorAction SilentlyContinue
    Stop-Process -Id $FrontendJob.Id -ErrorAction SilentlyContinue
}
