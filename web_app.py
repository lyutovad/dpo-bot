from aiohttp import web
import logging
import os
from telegram.ext import Application
import asyncio
from tg_bot_support import SupportBot, SUPPORT_BOT_TOKEN


API_PORT = 8100

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WebApp:
    def __init__(self):
        self.web_app = None
        self.support_bot = None
        self.bot_app = None
        self.bot_initialized = asyncio.Event()

    async def init_telegram_bot(self):
        """Инициализация приложения Telegram бота"""
        try:
            self.bot_app = Application.builder().token(SUPPORT_BOT_TOKEN).build()
            self.support_bot = SupportBot()
            self.support_bot.app = self.bot_app
            
            # Настройка обработчиков бота
            self.bot_app = self.support_bot.setup_bot()
            
            # Запуск бота в фоновом режиме
            async def run_bot():
                await self.bot_app.initialize()
                await self.bot_app.start()
                await self.bot_app.updater.start_polling()
                self.bot_initialized.set()

            asyncio.create_task(run_bot())
            
            # Ожидание инициализации бота
            await self.bot_initialized.wait()
            logger.info("Telegram бот успешно инициализирован")
            
        except Exception as e:
            logger.error(f"Ошибка при инициализации Telegram бота: {e}")
            raise

    async def setup_web_app(self):
        """Настройка веб-приложения"""
        self.web_app = web.Application()
        self.web_app.router.add_post('/new_question', self.handle_new_question)
        
        # Инициализация Telegram бота перед запуском веб-сервера
        await self.init_telegram_bot()
        
        return self.web_app

    async def forward_to_support(self, client_id: int, question: str, category: str, name: str = None, email: str = None):
        if not self.support_bot or not self.bot_initialized.is_set():
            raise RuntimeError("Бот поддержки не инициализирован")

        await self.support_bot.forward_to_support(client_id, question, category, name, email)

    async def handle_new_question(self, request):
        """Обработка новых вопросов через API endpoint"""
        try:
            data = await request.json()
            print(data)
            required_fields = ['user_id', 'question', 'category']
            
            if not all(field in data for field in required_fields):
                return web.Response(
                    status=400,
                    text="Отсутствуют обязательные поля"
                )
            
            if data['name']:
                await self.forward_to_support(
                    data['user_id'],
                    data['question'],
                    data['category'],
                    data['name'],
                    data['email']
                )
            else:
                await self.forward_to_support(
                    data['user_id'],
                    data['question'],
                    data['category'],
                )
            
            return web.Response(status=200, text="Вопрос передан в поддержку")
        except Exception as e:
            logger.error(f"Ошибка при обработке нового вопроса: {e}")
            return web.Response(status=500, text=str(e))

    async def cleanup(self):
        """Очистка ресурсов при завершении работы"""
        if self.bot_app:
            await self.bot_app.stop()
            await self.bot_app.shutdown()
        
    async def init_web_app(self):
        """Инициализация и запуск веб-приложения"""
        try:
            web_app = await self.setup_web_app()
            runner = web.AppRunner(web_app)
            await runner.setup()
            site = web.TCPSite(runner, '0.0.0.0', API_PORT)
            await site.start()
            
            logger.info(f"Веб-приложение запущено на порту {API_PORT}")
            
            # Поддержание работы приложения
            try:
                while True:
                    await asyncio.sleep(3600)  # Сон в течение часа
            except asyncio.CancelledError:
                await self.cleanup()
                
        except Exception as e:
            logger.error(f"Ошибка при запуске веб-приложения: {e}")
            await self.cleanup()
            raise

if __name__ == "__main__":
    app = WebApp()
    asyncio.run(app.init_web_app())