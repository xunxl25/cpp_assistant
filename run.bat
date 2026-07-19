@echo off
cd /d %~dp0

REM Clear Python cache
echo Clearing Python cache...
powershell -Command "Get-ChildItem -Path . -Include __pycache__ -Recurse -Directory | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue"

REM Clear Streamlit cache
echo Clearing Streamlit cache...
rd /s /q "%USERPROFILE%\.streamlit\cache" 2>nul

echo Checking dependencies...
pip install -q -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

echo Starting application...
streamlit run app/0_Overview.py
pause
