# Используем лёгкий образ Python
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Создаём папку под базу (если нет)
RUN mkdir -p /opt/drone/data

# Декларируем volume (хранение базы вне контейнера)
VOLUME ["/opt/drone/data"]

CMD ["python", "bot.py"]
