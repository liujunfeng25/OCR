@echo off
REM 在启动 Python 前设置，避免 PDX 重复初始化与 oneDNN 未实现错误
set PADDLE_PDX_EAGER_INIT=0
set FLAGS_use_mkldnn=0
cd /d "%~dp0"
python -m uvicorn main:app --host 0.0.0.0 --port 8010 %*
