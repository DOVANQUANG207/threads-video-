@echo off
:: Chuyen vao thu muc chua file bat nay
cd /d "%~dp0"

set VENV_DIR=venv

if exist "%VENV_DIR%" (
    echo [INFO] Dang kich hoat moi truong ao (venv)...
    call "%VENV_DIR%\Scripts\activate.bat"
) else (
    echo [WARNING] Khong tim thay thu muc venv. Dang thu chay bang Python he thong...
)

echo [INFO] Dang bat dau chay bot...
python main.py

if errorlevel 1 (
    echo.
    echo [ERROR] Co loi xay ra khi chay bot.
    pause
)
