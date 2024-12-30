import os
import asyncio
from telegram import Bot

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

async def check_chat_info():
    # Используем токен вашего бота поддержки
    bot = Bot(BOT_TOKEN)

    # ID вашего чата с темами
    chat_id = CHAT_ID

    try:
        print("Получаем информацию о чате...")

        # Получаем информацию о чате
        chat = await bot.get_chat(chat_id)

        print("\nИнформация о чате:")
        print(f"ID: {chat.id}")
        print(f"Тип: {chat.type}")
        print(f"Название: {chat.title}")
        print(f"Описание: {chat.description}")
        print(f"Можно ли отправлять сообщения: {chat.permissions}")
        print(f"Является ли форумом: {chat.is_forum}")

        if chat.is_forum:
            print("\nЭто форум-чат (с поддержкой тем)")
        else:
            print("\nЭто обычный чат (без поддержки тем)")
            print("Для работы с темами нужно:")
            print("1. Зайти в настройки группы")
            print("2. Включить 'Темы' в разделе разрешений")

    except Exception as e:
        print(f"Произошла ошибка: {e}")

    finally:
        await bot.close()

if __name__ == "__main__":
    asyncio.run(check_chat_info())
