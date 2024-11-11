# Используем базовый образ Python
FROM python:3.10-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем requirements.txt
COPY requirements.txt .

# Устанавливаем зависимост
RUN pip install -r requirements.txt

# Копируем остальные файлы приложения
COPY . .

# Указываем порт
EXPOSE 7860

# Команда для запуска приложения
CMD ["python", "app.py"]