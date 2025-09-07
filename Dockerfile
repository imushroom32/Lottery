# Используем лёгкий образ Python
FROM python:3.11-slim

# Устанавливаем рабочую директорию внутри контейнера
WORKDIR /app

# Скопируем requirements (если есть)
COPY requirements.txt .

# Установим зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код бота внутрь контейнера
COPY . .

# Команда запуска
CMD ["python", "main.py"]