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

:MENU
cls
echo ==========================================
echo       QUANGTRYMBE VIDEO MAKER
echo ==========================================
echo.
echo  1. Chay chuong trinh Tao Video (main.py)
echo  2. Chay giao dien quan ly (GUI.py)
echo  3. Thoat
echo.
set /p choice="Nhap lua chon cua ban (1-3): "

if "%choice%"=="1" goto RUN_MAIN
if "%choice%"=="2" goto RUN_GUI
if "%choice%"=="3" exit
goto MENU

:RUN_MAIN
echo [INFO] Dang khoi chay Tao Video...
"%PYTHON_EXE%" main.py
pause
goto MENU

:RUN_GUI
echo [INFO] Dang khoi chay Giao dien Web (localhost:4000)...
start "" http://localhost:4000
"%PYTHON_EXE%" GUI.py
pause
goto MENU
