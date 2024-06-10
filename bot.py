import psycopg2
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Updater, CommandHandler, MessageHandler, ConversationHandler, CallbackQueryHandler, CallbackContext, Filters

DB_NAME = "ege_bot"
DB_USER = "postgres"
DB_PASSWORD = "123"
DB_HOST = "localhost"
DB_PORT = 5432


def db_connect():
    conn = psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT
    )
    return conn


def init_db():
    conn = psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id SERIAL PRIMARY KEY,
            first_name VARCHAR(100),
            last_name VARCHAR(100)
        );
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS scores (
            score_id SERIAL PRIMARY KEY,
            student_id INTEGER REFERENCES students(student_id),
            subject VARCHAR(100),
            score INTEGER
        );
    ''')
    conn.commit()
    cur.close()
    conn.close()


REGISTER, ENTER_FIRST_NAME, ENTER_LAST_NAME, CHOOSE_ACTION, CHOOSE_SUBJECT, CHOOSE_MATH_TYPE, ENTER_SCORE = range(7)
subjects = [
    "Русский язык", "География", "Литература", "Химия",
    "Обществознание", "Информатика", "История", "Физика",
    "Биология", "Английский язык", "Немецкий язык"
]
math_types = ["Базовая математика", "Профильная математика"]


# /start
def start(update: Update, context: CallbackContext) -> int:
    update.message.reply_text(
        "Привет! Я бот для сбора баллов ЕГЭ. Введите /register для регистрации."
    )
    return REGISTER


# /register
def register(update: Update, context: CallbackContext) -> int:
    update.message.reply_text("Введите ваше имя:")
    return ENTER_FIRST_NAME


# first_name
def enter_first_name(update: Update, context: CallbackContext) -> int:
    context.user_data['first_name'] = update.message.text
    update.message.reply_text("Введите вашу фамилию:")
    return ENTER_LAST_NAME


# last_name
def enter_last_name(update: Update, context: CallbackContext) -> int:
    context.user_data['last_name'] = update.message.text

    conn = psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO students (first_name, last_name) VALUES (%s, %s) RETURNING id",
        (context.user_data['first_name'], context.user_data['last_name'])
    )
    context.user_data['user_id'] = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()

    keyboard = [
        [InlineKeyboardButton("Ввести баллы", callback_data='enter_scores')],
        [InlineKeyboardButton("Посмотреть баллы", callback_data='view_scores')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("Выберите действие:", reply_markup=reply_markup)
    return CHOOSE_ACTION


# action
def choose_action(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()

    if query.data == 'enter_scores':
        keyboard = [[InlineKeyboardButton(subject, callback_data=subject)] for subject in subjects]
        keyboard.append([InlineKeyboardButton("Математика", callback_data="Математика")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text("Выберите предмет:", reply_markup=reply_markup)
        return CHOOSE_SUBJECT
    elif query.data == 'view_scores':
        return view_scores(update, context, is_callback=True)
    else:
        query.edit_message_text("Пожалуйста, выберите один из вариантов.")
        return CHOOSE_ACTION


# subject
def choose_subject(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()

    if query.data == "Математика":
        keyboard = [[InlineKeyboardButton(math_type, callback_data=math_type)] for math_type in math_types]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text("Выберите тип математики:", reply_markup=reply_markup)
        return CHOOSE_MATH_TYPE
    else:
        context.user_data['subject'] = query.data
        query.edit_message_text(f"Введите баллы по предмету '{context.user_data['subject']}':")
        return ENTER_SCORE


# type math
def choose_math_type(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()

    context.user_data['subject'] = query.data
    query.edit_message_text(f"Введите баллы по предмету '{context.user_data['subject']}':")
    return ENTER_SCORE


# /enter_scores
def enter_scores(update: Update, context: CallbackContext) -> int:
    try:
        score = int(update.message.text)
        subject = context.user_data['subject']
        if subject == "Базовая математика" and 0 <= score <= 5:
            pass
        elif subject == "Профильная математика" and 0 <= score <= 100:
            pass
        elif subject != "Базовая математика" and subject != "Профильная математика" and 0 <= score <= 100:
            pass
        else:
            if subject == "Базовая математика":
                update.message.reply_text("Введите корректное значение баллов (от 0 до 5):")
            else:
                update.message.reply_text("Введите корректное значение баллов (от 0 до 100):")
            return ENTER_SCORE

        conn = db_connect()
        cur = conn.cursor()
        cur.execute("INSERT INTO scores (student_id, subject, score) VALUES (%s, %s, %s)",
                    (context.user_data['user_id'], subject, score))
        conn.commit()
        cur.close()
        conn.close()

        update.message.reply_text(f"Баллы по предмету '{subject}' сохранены!")

        keyboard = [
            [InlineKeyboardButton("Ввести баллы", callback_data='enter_scores')],
            [InlineKeyboardButton("Посмотреть баллы", callback_data='view_scores')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text("Выберите действие:", reply_markup=reply_markup)
        return CHOOSE_ACTION
    except ValueError:
        update.message.reply_text("Введите корректное значение баллов (от 0 до 100):")
        return ENTER_SCORE


# /view_scores
def view_scores(update: Update, context: CallbackContext, is_callback: bool = False) -> int:
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("SELECT subject, score FROM scores WHERE student_id = %s", (context.user_data['user_id'],))
    scores = cur.fetchall()
    cur.close()
    conn.close()

    if is_callback:
        query = update.callback_query
        query.answer()
        if scores:
            message = "Ваши сохраненные баллы ЕГЭ:\n" + "\n".join(
                [f"{subject}: {score}" for subject, score in scores])
        else:
            message = "У вас пока нет сохраненных баллов ЕГЭ."
        query.edit_message_text(message)

        keyboard = [
            [InlineKeyboardButton("Ввести баллы", callback_data='enter_scores')],
            [InlineKeyboardButton("Посмотреть баллы", callback_data='view_scores')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.message.reply_text("Выберите действие:", reply_markup=reply_markup)
    else:
        if scores:
            message = "Ваши сохраненные баллы ЕГЭ:\n" + "\n".join(
                [f"{subject}: {score}" for subject, score in scores])
        else:
            message = "У вас пока нет сохраненных баллов ЕГЭ."
        update.message.reply_text(message)

        keyboard = [
            [InlineKeyboardButton("Ввести баллы", callback_data='enter_scores')],
            [InlineKeyboardButton("Посмотреть баллы", callback_data='view_scores')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text("Выберите действие:", reply_markup=reply_markup)

    return CHOOSE_ACTION


# error
def unknown(update: Update, context: CallbackContext) -> None:
    update.message.reply_text("Не понял вашего сообщения.")


def main() -> None:
    init_db()
    updater = Updater("7348283504:AAGlKZYVNQxW7zJYZ7L7rKYJ9S-CRaTYNSE", use_context=True)
    dispatcher = updater.dispatcher

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            REGISTER: [CommandHandler('register', register)],
            ENTER_FIRST_NAME: [MessageHandler(Filters.text & ~Filters.command, enter_first_name)],
            ENTER_LAST_NAME: [MessageHandler(Filters.text & ~Filters.command, enter_last_name)],
            CHOOSE_ACTION: [CallbackQueryHandler(choose_action)],
            CHOOSE_SUBJECT: [CallbackQueryHandler(choose_subject)],
            CHOOSE_MATH_TYPE: [CallbackQueryHandler(choose_math_type)],
            ENTER_SCORE: [MessageHandler(Filters.text & ~Filters.command, enter_scores)],
        },
        fallbacks=[MessageHandler(Filters.regex('^Cancel$'), ConversationHandler.END)],
    )

    dispatcher.add_handler(conv_handler)
    dispatcher.add_handler(CommandHandler('enter_scores', start_enter_scores))
    dispatcher.add_handler(CommandHandler('view_scores', start_view_scores))
    dispatcher.add_handler(MessageHandler(Filters.command, unknown))

    updater.start_polling()
    updater.idle()


def start_enter_scores(update: Update, context: CallbackContext) -> int:
    keyboard = [[InlineKeyboardButton(subject, callback_data=subject)] for subject in subjects]
    keyboard.append([InlineKeyboardButton("Математика", callback_data="Математика")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("Выберите предмет:", reply_markup=reply_markup)
    return CHOOSE_SUBJECT


def start_view_scores(update: Update, context: CallbackContext) -> int:
    return view_scores(update, context)


if __name__ == '__main__':
    main()
