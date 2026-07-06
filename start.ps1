# PowerShell 启动脚本
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$env:PYTHONPATH = $scriptPath
Write-Host "PYTHONPATH 设置为: $env:PYTHONPATH" -ForegroundColor Green
Write-Host "正在启动应用..." -ForegroundColor Green
streamlit run app/app.py