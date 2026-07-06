@echo off
cd /d %~dp0
set PYTHONPATH=%~dp0;%PYTHONPATH%
streamlit run app/app.py
pause
