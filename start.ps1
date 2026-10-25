# Скрипт быстрого запуска LenQsec (Backend + Frontend + Xiaomi Camera Bridge)
param (
    [switch]$Standalone,
    [switch]$WithXiaomiBridge,
    [string]$Backend = "ONNX_CPU"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "              Запуск LenQsec [Dev Server]               " -ForegroundColor Cyan
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

# 3. Запуск видеомоста go2rtc для камеры Xiaomi (если установлен)
$Go2RtcExe = Join-Path $ProjectRoot "..\tools\go2rtc\go2rtc.exe"
$Go2RtcConfig = Join-Path $ProjectRoot "..\tools\go2rtc\go2rtc.yaml"
$Go2RtcJob = $null
if (Test-Path $Go2RtcExe) {
    Write-Host "[1/3] Запуск видеомоста go2rtc для камеры Xiaomi..." -ForegroundColor Magenta
    $Go2RtcJob = Start-Process -FilePath $Go2RtcExe -ArgumentList "-c", $Go2RtcConfig -WorkingDirectory (Split-Path $Go2RtcExe) -PassThru
}

# 4. Запуск Backend (FastAPI + uvicorn)
Write-Host "[2/3] Запуск FastAPI Backend (http://localhost:8000)..." -ForegroundColor Green
$env:INFERENCE_BACKEND = $Backend
$BackendJob = Start-Process -FilePath $PythonExe -ArgumentList "run.py" -WorkingDirectory $ProjectRoot -PassThru

# 5. Запуск Frontend (Vite dev server)
Write-Host "[3/3] Запуск Frontend (http://localhost:3000)..." -ForegroundColor Green
$FrontendDir = Join-Path $ProjectRoot "frontend"
$FrontendJob = Start-Process -FilePath "npm.cmd" -ArgumentList "run", "dev" -WorkingDirectory $FrontendDir -PassThru

Write-Host "`nСервисы запущены:" -ForegroundColor Cyan
Write-Host "  - UI Диспетчера:        http://localhost:3000" -ForegroundColor Yellow
Write-Host "  - API Swagger:           http://localhost:8000/docs" -ForegroundColor Yellow
if ($Go2RtcJob) {
    Write-Host "  - Мост камеры Xiaomi:    http://localhost:1984" -ForegroundColor Yellow
    Write-Host "  - RTSP поток камеры:     rtsp://127.0.0.1:8554/xiaomi_cam" -ForegroundColor Yellow
}
Write-Host "`nНажмите Ctrl+C для остановки всех процессов..."

try {
    $processes = @($BackendJob.Id, $FrontendJob.Id)
    if ($Go2RtcJob) { $processes += $Go2RtcJob.Id }
    Wait-Process -Id $processes
} finally {
    Stop-Process -Id $BackendJob.Id -ErrorAction SilentlyContinue
    Stop-Process -Id $FrontendJob.Id -ErrorAction SilentlyContinue
    if ($Go2RtcJob) { Stop-Process -Id $Go2RtcJob.Id -ErrorAction SilentlyContinue }
}
