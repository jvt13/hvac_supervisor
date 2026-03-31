$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

$exeName = "HVAC_WATCHDOG"

Write-Host "Encerrando processo antigo, se estiver em execucao..." -ForegroundColor Cyan
Get-Process $exeName -ErrorAction SilentlyContinue | Stop-Process -Force

Write-Host "Validando sintaxe dos modulos..." -ForegroundColor Cyan
python -m py_compile `
  watchdog.py

Write-Host "Gerando EXE ($exeName)..." -ForegroundColor Cyan
pyinstaller `
  --noconfirm `
  --clean `
  --console `
  --onedir `
  --name $exeName `
  --icon icone_automacao.ico `
  --hidden-import psutil `
  watchdog.py

Write-Host ""
Write-Host "Build concluido com sucesso." -ForegroundColor Green
Write-Host "Executavel:" -NoNewline
Write-Host " dist\\$exeName\\$exeName.exe" -ForegroundColor Green
