import os
import aiohttp
import psycopg
from datetime import datetime
import time
import asyncio
import uuid
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler, Application
from langchain_main import OllamaModel
from pydantic import BaseModel

TG_BOT_TOKEN = os.getenv('TG_BOT_TOKEN')
SUPPORT_BOT_API_URL = os.getenv('SUPPORT_BOT_API_URL', 'http://dpo-web-service:8100/new_question')
POSTGRES_HOST = os.getenv("POSTGRES_HOST")
POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
POSTGRES_PORT = os.getenv("POSTGRES_PORT")
POSTGRES_DB = os.getenv("POSTGRES_DB")

connect_string = f"host={POSTGRES_HOST} port ={POSTGRES_PORT} dbname={POSTGRES_DB} user={POSTGRES_USER} password={POSTGRES_PASSWORD}"
Connection = psycopg.connect(connect_string)
conn = Connection
conn.autocommit = True

# Определение состояний
BUTTON_SELECTION = 1
ASKING_QUESTION = 2
FAQ_SELECTION = 3
OPERATOR_NAME = 4  
OPERATOR_EMAIL = 5
OPERATOR_QUESTION = 6

TIMEOUT = 2*60

Query_Insert_Chat_Id_To_Db = """
    INSERT INTO chat_ids (chat_id) VALUES (%s);
    """

Query_Get_Chat_Ids_From_Db = """
    SELECT chat_id FROM public.chat_ids
    ORDER BY 1
    """

Query_Insert_Info = """
    INSERT INTO information (id_rec, question, answer, comment, education_level_id, applicant_education_level_id, direction_id, program_id, user_id, date_created, modified_by)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

class Chats(BaseModel):
    chat_id: int = None

ollama_model = OllamaModel()

def get_start_keyboard():
    start_keyboard = [
            ['МВА-Современные технологии управления ВЭД', 'Специалитет/магистратура + МВА'],
            ['МВА-Стратегическое управление эффективностью бизнеса', 'Программа двух дипломов (магистратура + МВА) Бизнес-администрирование'],
            ['Общие вопросы']
        ]
    return ReplyKeyboardMarkup(start_keyboard, resize_keyboard=True, one_time_keyboard=False)

def get_return_keyboard():
    return_keyboard = [['Вернуться к началу', 
                        'Связаться с оператором'
                        ]]
    return ReplyKeyboardMarkup(return_keyboard, resize_keyboard=True, one_time_keyboard=False)

def get_faq_keyboard():
    faq_keyboard = [
            ['Критерии оценивания слушателя на экзамене по дисциплинам', 'Электронные библиотеки и ресурсы'],
            ['Критерии оценивания слушателя на зачете по дисциплинам', 'Критерии оценивания эссе'],
            ['Вернуться к началу']
        ]
    return ReplyKeyboardMarkup(faq_keyboard, resize_keyboard=True, one_time_keyboard=False)

def get_all_from_query(cursor):
        rows = []
        for row in cursor.fetchall():
            dict = row[0]
            rows.append(dict)        
        return rows

def get_active_chats():
    cursor = conn.cursor()
    try:
        cursor.execute(Query_Get_Chat_Ids_From_Db)
        res = get_all_from_query(cursor)
    except Exception as e:
        print(f"Error: {e}")
    finally:
        cursor.close()
        return res
    

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    client_id = update.effective_chat.id

    res = get_active_chats()
    try:
        cursor = conn.cursor()
        if client_id not in res:
                cursor.execute(Query_Insert_Chat_Id_To_Db, [client_id])
    except Exception as e:
        print(f"Error: {e}")
    finally:
        cursor.close()

    context.user_data['is_processing'] = False
    reply_markup = get_start_keyboard()
    await update.message.reply_text('Выберите кнопку:', reply_markup=reply_markup)
    return BUTTON_SELECTION

async def reset_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()  # Очищаем данные пользователя
    context.user_data['is_processing'] = False
    reply_markup = get_start_keyboard()
    await update.message.reply_text('Разговор сброшен. Выберите кнопку:', reply_markup=reply_markup)
    return BUTTON_SELECTION

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    button_pressed = update.message.text
    valid_buttons = [
        'МВА-Современные технологии управления ВЭД',
        'Специалитет/магистратура + МВА',
        'МВА-Стратегическое управление эффективностью бизнеса',
        'Программа двух дипломов (магистратура + МВА) Бизнес-администрирование',
        'Общие вопросы'
    ]

    if button_pressed not in valid_buttons:
        reply_markup = get_start_keyboard()
        await update.message.reply_text(
            "Вы не выбрали раздел. Пожалуйста, нажмите одну из кнопок.",
            reply_markup=reply_markup
        )
        return BUTTON_SELECTION

    if button_pressed == "Вернуться к началу":
        return await reset_conversation(update, context)
    
    if button_pressed == "Общие вопросы":
        reply_markup = get_faq_keyboard()
        await update.message.reply_text(
            "Выберите интересующий вас вопрос:",
            reply_markup=reply_markup
        )
        return FAQ_SELECTION
    
    await update.message.reply_text(f'Вы нажали: {button_pressed}. Пожалуйста, введите ваш вопрос:', reply_markup=get_return_keyboard())
    context.user_data['button_pressed'] = button_pressed
    context.user_data['is_processing'] = False
    return ASKING_QUESTION

async def faq_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    button_pressed = update.message.text
    
    if button_pressed == "Вернуться к началу":
        return await reset_conversation(update, context)

    valid_faq_buttons = [
        'Критерии оценивания слушателя на экзамене по дисциплинам',
        'Электронные библиотеки и ресурсы',
        'Критерии оценивания слушателя на зачете по дисциплинам',
        'Критерии оценивания эссе'
    ]

    if button_pressed not in valid_faq_buttons:
        reply_markup = get_faq_keyboard()
        await update.message.reply_text(
            "Пожалуйста, выберите один из предложенных разделов.",
            reply_markup=reply_markup
        )
        return FAQ_SELECTION

    context.user_data['button_pressed'] = button_pressed
    context.user_data['is_processing'] = False
    await update.message.reply_text(f'Вы нажали: {button_pressed}. Пожалуйста, введите ваш вопрос:', reply_markup=get_return_keyboard())
    return ASKING_QUESTION

async def handle_operator_contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    cancel_keyboard = [['Отменить']]
    reply_markup = ReplyKeyboardMarkup(cancel_keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Пожалуйста, введите ваше ФИО:",
        reply_markup=reply_markup
    )
    return OPERATOR_NAME

async def handle_operator_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text == "Отменить":
        return await reset_conversation(update, context)
    
    context.user_data['operator_name'] = update.message.text
    cancel_keyboard = [['Отменить']]
    reply_markup = ReplyKeyboardMarkup(cancel_keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Теперь введите ваш email:",
        reply_markup=reply_markup
    )
    return OPERATOR_EMAIL

async def handle_operator_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text == "Отменить":
        return await reset_conversation(update, context)
    
    context.user_data['operator_email'] = update.message.text
    cancel_keyboard = [['Отменить']]
    reply_markup = ReplyKeyboardMarkup(cancel_keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Пожалуйста, введите ваш вопрос оператору:",
        reply_markup=reply_markup
    )
    return OPERATOR_QUESTION

async def handle_operator_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text == "Отменить":
        return await reset_conversation(update, context)
    
    question = update.message.text
    name = context.user_data.get('operator_name')
    email = context.user_data.get('operator_email')
    button_pressed = context.user_data.get('button_pressed'),

    success = await forward_to_support_bot(
        update.effective_user.id,
        question,
        button_pressed[0],
        name=name,
        email=email
    )
    
    if success:
        await update.message.reply_text(
            "Спасибо! Ваши данные и вопрос отправлены оператору. Мы свяжемся с вами в ближайшее время.",
            reply_markup=get_return_keyboard()
        )
    else:
        await update.message.reply_text(
            "Произошла ошибка при отправке данных. Пожалуйста, попробуйте позже.",
            reply_markup=get_return_keyboard()
        )
    
    return ASKING_QUESTION


async def handle_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if context.user_data.get('is_processing', False):
        await update.message.reply_text(
            "Пожалуйста, дождитесь ответа на ваш предыдущий запрос или попробуйте попытку позже!",
            reply_markup=get_return_keyboard()
        )
        return ASKING_QUESTION

    user_question = update.message.text
    button_pressed = context.user_data.get('button_pressed')

    if user_question == "Вернуться к началу":
        return await reset_conversation(update, context)
    
    if user_question == "Связаться с оператором":
        return await handle_operator_contact(update, context)


    try:
        context.user_data['is_processing'] = True
        message = await update.message.reply_text('_Нейросеть задумалась..._', parse_mode='Markdown')
        await asyncio.sleep(2)

        num_coll = None

        # Определение num_coll на основе нажатой кнопки
        if button_pressed == 'МВА-Современные технологии управления ВЭД':
            num_coll = 1
        elif button_pressed == 'Специалитет/магистратура + МВА':
            num_coll = 2
        elif button_pressed == 'МВА-Стратегическое управление эффективностью бизнеса':
            num_coll = 3
        elif button_pressed == 'Программа двух дипломов (магистратура + МВА) Бизнес-администрирование':
            num_coll = 4
        elif button_pressed == 'Критерии оценивания слушателя на экзамене по дисциплинам':
            num_coll = 5
        elif button_pressed == 'Электронные библиотеки и ресурсы':
            num_coll = 6
        elif button_pressed == 'Критерии оценивания слушателя на зачете по дисциплинам':
            num_coll = 7
        elif button_pressed == 'Критерии оценивания эссе':
            num_coll = 8

        response_text = ollama_model.ask_question(user_question, num_coll)
        
        await message.delete()

        if response_text == "Нет ответа на поставленный вопрос.":
            success = await forward_to_support_bot(
                update.effective_user.id,
                user_question,
                button_pressed
            )
            
            if success:
                response_text = (
                    "К сожалению, я не могу ответить на ваш вопрос. "
                    "Он был передан операторам поддержки, которые ответят вам в ближайшее время."
                )
            else:
                response_text = (
                    "К сожалению, я не могу ответить на ваш вопрос. "
                    "Также произошла ошибка при попытке связаться со службой поддержки. "
                    "Пожалуйста, попробуйте позже."
                )
        
        await update.message.reply_text(
            response_text,
            reply_markup=get_return_keyboard()
        )
    finally:
        context.user_data['is_processing'] = False
    
    return ASKING_QUESTION

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text('Отменено. Если хотите, начните заново с /start.')
    return ConversationHandler.END


async def forward_to_support_bot(user_id: int, question: str, category: str, name: str = None, email: str = None) -> bool:
    """Пересылает вопрос в бот поддержки через API"""
    data = {
        "user_id": user_id,
        "question": question,
        "category": category,
        "name": name,
        "email": email,
        "timestamp": datetime.now().isoformat()
    }

    print(data)   

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(SUPPORT_BOT_API_URL, json=data, ssl=False) as response:
                if response.status == 200:
                    return True
                else:
                    print(f"Error forwarding question to support bot: {await response.text()}")
                    return False
    except Exception as e:
        print(f"Error sending question to support bot: {e}")
        return False
    
async def post_init(application: Application):
    """Вызывается сразу после запуска бота"""
    await application.bot.set_my_commands([('start', 'Перезапустить бота')])
    
    async def broadcast_restart():
        """Отправляет сообщение о перезапуске всем активным чатам"""
        active_chats = get_active_chats()
        reply_markup = get_start_keyboard()
        
        for chat_id in active_chats:
            try:
                await application.bot.send_message(
                    chat_id=chat_id,
                    text="🔄 Бот был перезапущен. Нажмите /start для продолжения работы:",
                    reply_markup=reply_markup
                )

                time.sleep(1)

                await application.bot.send_message(
                    chat_id=534551946,
                    text=f"Отправлено сообщение в {chat_id}",
                    reply_markup=reply_markup
                )

                time.sleep(1)

            except Exception as e:
                await application.bot.send_message(
                    chat_id=534551946,
                    text=f"Failed to send restart message to chat {chat_id}: {e}",
                    reply_markup=reply_markup
                )
                print(f"Failed to send restart message to chat {chat_id}: {e}")
                pass


    # Запускаем рассылку в фоновом режиме
    asyncio.create_task(broadcast_restart())


def main() -> None:
    app = ApplicationBuilder().token(TG_BOT_TOKEN).read_timeout(120).write_timeout(120).connect_timeout(120).post_init(post_init).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            BUTTON_SELECTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, button_handler)
            ],
            FAQ_SELECTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, faq_handler)
            ],
            ASKING_QUESTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_question)
            ],

            OPERATOR_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_operator_name)
            ],
            OPERATOR_EMAIL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_operator_email)
            ],

             OPERATOR_QUESTION: [ 
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_operator_question)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            MessageHandler(filters.Regex("^Вернуться к началу$"), reset_conversation)
        ],
        conversation_timeout=TIMEOUT
    )

    app.add_handler(conv_handler)
    app.run_polling()