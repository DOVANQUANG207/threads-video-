@echo off
setlocal enabledelayedexpansion
title Quangtrymbe - Video Maker

:: Di chuyển vào thư mục chứa file bat
cd /d "%~dp0"

set VENV_DIR=.venv

:: Kiểm tra môi trường ảo
if exist "%VENV_DIR%" (
    echo [INFO] Su dung moi truong ao: %VENV_DIR%
    set PYTHON_EXE=%VENV_DIR%\Scripts\python.exe
) else (
    echo [WARNING] Khong tim thay thu muc .venv. Su dung Python he thong...
    set PYTHON_EXE=python
)

echo ==========================================
echo       QUANGTRYMBE VIDEO MAKER
echo ==========================================
echo.
echo [INFO] Dang khoi chay Tao Video tren Terminal...
"%PYTHON_EXE%" main.py
pause
