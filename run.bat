@echo off
echo ==============================================
echo [Keitering Agent] Установка и Запуск
echo ==============================================

echo [1] Проверка наличия Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ОШИБКА] Python не найден! Пожалуйста, установите Python 3.9+ 
    pause
    exit /b
)

echo [2] Установка зависимостей (requirements.txt)...
pip install -r requirements.txt

echo [3] Запуск Backend сервера (FastAPI) в фоновом режиме...
start "Keitering Backend" cmd /c "uvicorn backend.main:app --reload --port 8000"

echo [4] Ожидание запуска сервера...
timeout /t 3 /nobreak >nul

echo [5] Открытие Frontend интерфейса...
start "" "frontend\index.html"

echo ==============================================
echo Готово! Бэкенд запущен в отдельном окне.
echo Если страница не открылась, откройте файл:
echo %CD%\frontend\index.html
echo ==============================================
pause
