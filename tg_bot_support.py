import os
import asyncio
import uuid
import psycopg
from datetime import datetime
from aiohttp import web
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)
from tg_bot_main import connect_string

SUPPORT_BOT_TOKEN = os.getenv('TG_SUPPORT_BOT_TOKEN')
OPERATOR_CHAT_ID = os.getenv('OPERATOR_CHAT_ID')
MAIN_BOT_TOKEN = os.getenv('TG_BOT_TOKEN')

Connection = psycopg.connect(connect_string)

# Состояния для ConversationHandler
EXPECTING_ANSWER = 1  # Используем числа вместо строк
PROCESSING_ANSWER = 2
TIMEOUT = 2*60

TOPIC_IDS = {
    'МВА-Современные технологии управления ВЭД': 4,
    'Специалитет/магистратура + МВА': 6,
    'МВА-Стратегическое управление эффективностью бизнеса': 8,
    'Программа двух дипломов (магистратура + МВА) Бизнес-администрирование': 10,
}

Query_Insert_Info = """
    INSERT INTO information (id_rec, question, answer, comment, education_level_id, applicant_education_level_id, direction_id, program_id, user_id, date_created, modified_by)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

Query_Id_Programs = """
    SELECT id FROM public.programs
    WHERE program_name = %s
    """

Query_Id_User = """
    SELECT user_id FROM public.users
    WHERE chat_id = %s
    """

# Словарь для хранения информации о вопросах
questions_db = {}

class SupportBot:
    def __init__(self):
        self.app = None
        self.web_app = None
        self.questions_db = {}
        self.conn = Connection
        self.conn.autocommit = True

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        print(update.effective_chat.id)
        if update.effective_chat.id == int(OPERATOR_CHAT_ID):
            await update.message.reply_text(
                "Добро пожаловать в панель оператора поддержки. "
                "Здесь вы будете получать вопросы, на которые не смог ответить основной бот."
            )
        else:
            await update.message.reply_text(
                "Этот бот предназначен только для операторов поддержки."
            )
        return ConversationHandler.END

    async def forward_to_support(self, client_id: int, question: str, category: str, name: str = None, email: str = None):
        """Пересылает вопрос операторам поддержки"""
        question_id = str(uuid.uuid4())

        keyboard = [
            [InlineKeyboardButton("Ответить", callback_data=f"answer_{question_id}_{client_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)


        # Сохраняем информацию о вопросе
        self.questions_db[question_id] = {
            "client_id": client_id,
            "question": question,
            "category": category,
            "status": "pending"
        }


        topic_id = TOPIC_IDS.get(category)

        if name and email:
            message = (
            f"❗️ Заявка на связь с оператором (ID: {client_id}):\n"
            f"ФИО: {name}\n"
            f"Email: {email}\n"
            f"Категория: {category}\n\n"
            f"{question}"
            )

            await self.app.bot.send_message(
            chat_id=OPERATOR_CHAT_ID,
            message_thread_id=topic_id,
            text=message,
            )


        else:
            message = (
                f"❗️ Новый вопрос от пользователя (ID: {client_id}):\n"
                f"ID вопроса: {question_id}\n"
                f"Категория: {category}\n\n"
                f"{question}"
            )
        
            await self.app.bot.send_message(
                chat_id=OPERATOR_CHAT_ID,
                message_thread_id=topic_id,
                text=message,
                reply_markup=reply_markup
            )

    async def operator_answer(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработчик нажатия кнопки 'Ответить'"""
        query = update.callback_query

        await query.answer()
        
        client_id = int(query.data.split('_')[2])
        message_id = query.data.split('_')[1]
        
        if self.questions_db[message_id]["status"] == "answered":
            await query.edit_message_text(
                f"На этот вопрос уже ответили.\n\nВопрос:\n{self.questions_db[message_id]['question']}"
            )
            return ConversationHandler.END
        
        context.user_data['state'] = EXPECTING_ANSWER
        context.user_data['current_client'] = client_id
        context.user_data['current_message'] = message_id
        
        await query.edit_message_text(
            f"Напишите ответ на вопрос:\n\n{self.questions_db[message_id]['question']}"
        )
        
        return EXPECTING_ANSWER

    async def send_answer_to_main_bot(self, client_id: int, question: str, answer: str, category: str):
        """Отправляет ответ в основной бот через Telegram API"""
        async with Application.builder().token(MAIN_BOT_TOKEN).build() as main_bot:
            try:
                message = (
                    f"✅ Получен ответ от оператора на ваш вопрос:\n\n"
                    f"Ваш вопрос: {question}\n\n"
                    f"Ответ: {answer}"
                )
                
                await main_bot.bot.send_message(
                    chat_id=client_id,
                    text=message
                )

                program_id = self.get_program_id(category)[0]
                user_id = self.get_user_id(client_id)[0]


                data = {}
                data['question'] = question
                data['answer'] = answer
                data['comment'] = ''
                data['education_level_id'] = 3 # Хард-код
                data['applicant_education_level_id'] = 3 # Хард-код
                data['direction_id'] = 4 # Хард-код
                data['program_id'] = program_id
                
                self.add_question_to_db(data, user_id)
                return True
            except Exception as e:
                print(f"Error sending answer through main bot: {e}")
                return False

    async def process_operator_answer(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработка ответа оператора и отправка его обратно в основной бот"""
        client_id = context.user_data.get('current_client')
        message_id = context.user_data.get('current_message')

        operator_answer = update.message.text
        
        if not client_id:
            await update.message.reply_text("Произошла ошибка. Попробуйте начать сначала.")
            return ConversationHandler.END
        
        question_data = self.questions_db.get(message_id)
        if not question_data:
            await update.message.reply_text("Информация о вопросе не найдена.")
            return ConversationHandler.END
        
        success = await self.send_answer_to_main_bot(
            client_id,
            question_data["question"],
            operator_answer,
            question_data["category"]
        )
        
        if success:
            self.questions_db[message_id]["status"] = "answered"
            self.questions_db[message_id]["answer"] = operator_answer
            
            await update.message.reply_text(
                f"✅ Ответ успешно отправлен пользователю.\n\n"
                f"Вопрос: {question_data['question']}\n"
                f"Ваш ответ: {operator_answer}"
            )
        else:
            await update.message.reply_text(
                "❌ Произошла ошибка при отправке ответа. Пожалуйста, попробуйте позже."
            )
        
        return ConversationHandler.END

    async def debug_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        print(f"Debug handler caught message: {update.message.text}")
        print(f"Current state: {context.user_data.get('state')}")

    def get_all_from_query(self, cursor):
        rows = []
        for row in cursor.fetchall():
            dict = row[0]
            rows.append(dict)        
        return rows

    def add_question_to_db(self, data, user_id):
        cursor = self.conn.cursor()
        id_rec = uuid.uuid4()
        date_created = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        query = Query_Insert_Info

        try:
            cursor.execute(
                    query,
                    (
                        str(id_rec),
                        data['question'],
                        data['answer'],
                        data['comment'],
                        data['education_level_id'],
                        data['applicant_education_level_id'],
                        data['direction_id'],
                        data['program_id'],
                        user_id,
                        date_created,
                        user_id,
                    ),
                )
        except Exception as e:
            print(f"Error: {e}")
        finally:
            cursor.close()

    def get_program_id(self, program_name):
        cursor = self.conn.cursor()
        query = Query_Id_Programs
        try:
            cursor.execute(query, [program_name])
            return self.get_all_from_query(cursor)
        except Exception as e:
            print(f"Error: {e}")
        finally:
            cursor.close()

    def get_user_id(self, client_id):
        cursor = self.conn.cursor()
        query = Query_Id_User
        try:
            cursor.execute(query, [client_id])
            return self.get_all_from_query(cursor)
        except Exception as e:
            print(f"Error: {e}")
        finally:
            cursor.close()

    def setup_bot(self):
        """Настройка бота"""
        self.app = Application.builder().token(SUPPORT_BOT_TOKEN).build()
        
        conv_handler = ConversationHandler(
            entry_points=[
                CommandHandler("start", self.start),
                CallbackQueryHandler(self.operator_answer, pattern=r"^answer_([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})_(\d+)$")
            ],
            states={
                EXPECTING_ANSWER: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.process_operator_answer),
                ]
            },
            fallbacks=[
                CommandHandler("cancel", lambda u, c: ConversationHandler.END),
                MessageHandler(filters.ALL, self.debug_handler)
            ],
            per_message=False,
            per_chat=False,
            per_user=True,  # Отслеживаем состояния по пользователям
            allow_reentry=True,
            conversation_timeout=TIMEOUT
        )

       
        self.app.add_handler(conv_handler)
        return self.app
    
    def init_support_bot(self):
        bot_app = self.setup_bot()
        bot_app.run_polling()
