#!/bin/bash
set -e
echo "🐍 Python: $(python3 --version)"
echo "⬆️ Обновление pip..."
python3 -m pip install --upgrade pip
pip3 install -r requirements.txt
echo "✅ Установка завершена!"
