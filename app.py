import os
import json
import requests
import logging
from flask import Flask, request, jsonify, Response, stream_with_context
import re

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Импортируем класс GigaChat из новой библиотеки langchain_community
from langchain_community.chat_models.gigachat import GigaChat

# Задайте URL-адрес API для GigaChat
GIGACHAT_API_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"  # Обновите на правильный URL, если необходимо
credentials = "MTAyMGFiOTQtMzViZS00ODI1LWE1M2EtMjM2NWRhMDQwYTI4OjFjZjQ4YmY3LTNhZDQtNGY1Ni05MTc0LThjYTM1MzY5MmQwMA=="
logging.debug(f"Using credentials: {credentials}")
logging.debug(f"Using API URL: {GIGACHAT_API_URL}")

model = GigaChat(
    credentials=credentials,
    scope="GIGACHAT_API_PERS",
    model="GigaChat-Pro",
    verify_ssl_certs=False,
)

command_buffer = {}

def load_commands():
    instructions_dir = "./instructions"
    if not os.path.exists(instructions_dir):
        logging.error(f"Каталог '{instructions_dir}' не найден.")
        return

    for filename in os.listdir(instructions_dir):
        command_name = os.path.splitext(filename)[0]
        file_path = os.path.join(instructions_dir, filename)

        with open(file_path, encoding='utf-8') as file:
            data = file.read()
            description = re.search(r"\${description:(.*?)}", data)
            initial_message = re.search(r"\${initialMessage:(.*?)}", data)
            hint_message = re.search(r"\${hintMessage:(.*?)}", data)
            assistantInstructions = re.search(r"\${assistantInstructions:([\s\S]*?)}", data)

            command_buffer[command_name] = {
                "description": description.group(1) if description else "Нет описания",
                "initial_message": initial_message.group(1) if initial_message else "",
                "hint_message": hint_message.group(1) if hint_message else "",
                "assistantInstructions": assistantInstructions.group(1) if assistantInstructions else ""
            }
            logging.info(f"Загружена команда: /{command_name}")

load_commands()

def get_gigachat_response_stream(messages):
    try:
        # Устанавливаем параметры для стриминга
        headers = {
            'Accept': 'application/json',
            'Authorization': f'Basic {credentials}'
        }

        payload = {
            "model": model.model,
            "messages": messages,
            "stream": True
        }

        # Используем заданный URL-адрес API
        response = requests.post(GIGACHAT_API_URL, headers=headers, json=payload, stream=True, verify=model.verify_ssl_certs)

        response.raise_for_status()

        # Генерация ответа с использованием потоков
        def generate():
            for line in response.iter_lines(decode_unicode=True):
                if line and line != 'data: [DONE]':
                    data = json.loads(line.split('data: ')[-1])
                    if 'choices' in data and 'delta' in data['choices'][0]:
                        content = data['choices'][0]['delta'].get('content', '')
                        if content:
                            yield content

        return Response(stream_with_context(generate()), content_type='text/plain')

    except requests.exceptions.RequestException as e:
        logging.error(f"Ошибка при получении стримингового ответа: {e}")
        return "Ошибка при подключении к GigaChat API."

# Инициализация Flask приложения
app = Flask(__name__)

@app.route('/commands', methods=['GET'])
def list_commands():
    logging.info("Запрос списка команд.")
    return jsonify(commands=command_buffer)

@app.route('/', methods=['POST'])
def chat_with_ai():
    user_message = request.json.get('userMessage')
    command_name = request.json.get('commandName')
    history = request.json.get('history', [])

    if not user_message or not command_name:
        logging.warning('Пользовательское сообщение или commandName не предоставлены.')
        return jsonify(error='User message or commandName not provided'), 400

    command = command_buffer.get(command_name)
    if not command:
        logging.warning(f'Команда "{command_name}" не найдена.')
        return jsonify(error=f'Command "{command_name}" not found'), 400

    try:
        assistantInstructions = command.get("assistantInstructions", "")
        messages = [{"role": "system", "content": assistantInstructions}]
        for message in history:
            messages.append({"role": message['role'], "content": message['content']})
        messages.append({"role": "user", "content": user_message})

        return get_gigachat_response_stream(messages)
    except Exception as e:
        logging.error(f"Ошибка при обработке запроса: {e}")
        return jsonify(error=str(e)), 500

if __name__ == "__main__":
    port = int(os.getenv("PORT"))
    app.run(host='0.0.0.0', port=port)
