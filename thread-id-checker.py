import os
import asyncio
from telegram import Bot
import json

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

async def test_topics():
    # Используем токен вашего бота поддержки
    bot = Bot(BOT_TOKEN)

    # ID вашего чата с темами
    chat_id = CHAT_ID

    # Начнем с маленьких чисел и будем пробовать отправить сообщения
    test_thread_ids = range(1, 20)  # Проверим ID от 1 до 19

    working_topics = {}

    try:
        print("Проверяем ID тем...")

        for thread_id in test_thread_ids:
            try:
                # Пробуем отправить сообщение в тему с текущим ID
                message = await bot.send_message(
                    chat_id=chat_id,
                    message_thread_id=thread_id,
                    text=f"🔍 Проверка темы с ID {thread_id}. Это сообщение можно удалить."
                )

                # Если сообщение отправилось успешно, сохраняем ID
                print(f"\nУспешно отправлено в тему с ID: {thread_id}")
                print(f"Сообщение ID: {message.message_id}")

                working_topics[thread_id] = True

            except Exception as e:
                if "TOPIC_NOT_FOUND" in str(e):
                    print(f"Тема с ID {thread_id} не существует")
                elif "MESSAGE_THREAD_NOT_FOUND" in str(e):
                    print(f"Тема с ID {thread_id} не найдена")
                else:
                    print(f"Ошибка при проверке ID {thread_id}: {e}")

            # Небольшая пауза между запросами
            await asyncio.sleep(0.5)

        # Выводим итоговый результат
        print("\nНайденные рабочие ID тем:", list(working_topics.keys()))

        # Сохраняем результаты в файл
        with open('working_topics.json', 'w', encoding='utf-8') as f:
            json.dump({
                'chat_id': chat_id,
                'working_topic_ids': list(working_topics.keys())
            }, f, ensure_ascii=False, indent=2)

    except Exception as e:
        print(f"Произошла общая ошибка: {e}")

    finally:
        await bot.close()

if __name__ == "__main__":
    asyncio.run(test_topics())
