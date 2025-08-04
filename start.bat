@echo off
cd /d %~dp0

echo 🔹 Активируем виртуальное окружение...
call venv\Scripts\activate.bat

echo 🔹 Устанавливаем зависимости (на всякий случай)...
pip install -r requirements.txt

echo 🔹 Запускаем Telegram-бота...
python main.py

pause
