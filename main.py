import logging
import requests
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, ContextTypes
import config

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# State definitions for conversation handler
CHOOSING_SUBJECT, CHOOSING_DIFFICULTY, ANSWERING_QUESTION, ASKING_DOUBT = range(4)

# Points tracking
USER_POINTS = {}

def generate_quiz_question(subject, difficulty):
    # URL with API key as query parameter
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={config.GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    data = {
        "contents": [{"parts": [{"text": f"Generate a quiz question for {subject} at {difficulty} difficulty"}]}]
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        logger.info(f"Response status code: {response.status_code}")
        logger.info(f"Response content: {response.text}")
        response.raise_for_status()
        
        # Parse the response
        response_data = response.json()
        question = response_data.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', 'No question available')
        return question, None
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {e}")
        return "Error fetching question. Please try again later.", None

def generate_doubt_answer(doubt):
    # URL with API key as query parameter
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={config.GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    data = {
        "contents": [{"parts": [{"text": f"Answer the following question in detail: {doubt}"}]}]
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        logger.info(f"Response status code: {response.status_code}")
        logger.info(f"Response content: {response.text}")
        response.raise_for_status()
        
        # Parse the response
        response_data = response.json()
        answer = response_data.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', 'No answer available')
        return answer
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {e}")
        return "Error fetching answer. Please try again later."

# Start command handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Welcome to the Quiz and Doubt Clearing Bot! Type /quiz to start a quiz or /doubt to ask a question.")

# Quiz command handler
async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = [['Math', 'Science', 'English']]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text("Choose a subject:", reply_markup=reply_markup)
    return CHOOSING_SUBJECT

# Doubt command handler
async def doubt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Please enter your doubt or question:")
    return ASKING_DOUBT

# Subject choice handler
async def choose_subject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    subject = update.message.text.lower()
    if subject in ['math', 'science', 'english']:
        context.user_data['subject'] = subject
        # Ask for difficulty level
        keyboard = [['Easy', 'Medium', 'Hard']]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text("Choose difficulty level:", reply_markup=reply_markup)
        return CHOOSING_DIFFICULTY
    else:
        await update.message.reply_text("Please choose a valid subject: math, science, or english.")
        return CHOOSING_SUBJECT

# Difficulty level choice handler
async def choose_difficulty(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    difficulty = update.message.text.lower()
    if difficulty in ['easy', 'medium', 'hard']:
        context.user_data['difficulty'] = difficulty
        question, answer = generate_quiz_question(context.user_data['subject'], difficulty)
        if answer is None:
            context.user_data['question'] = question
            await update.message.reply_text(question)
            return ANSWERING_QUESTION
        context.user_data['answer'] = answer
        await update.message.reply_text(question)
        return ANSWERING_QUESTION
    else:
        await update.message.reply_text("Please choose a valid difficulty level: easy, medium, or hard.")
        return CHOOSING_DIFFICULTY

# Answer handler
async def answer_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_answer = update.message.text.strip().lower()
    correct_answer = context.user_data.get('answer', '').strip().lower()
    if user_answer == correct_answer:
        await update.message.reply_text("Correct! Type /quiz to play again.")
        # Update user points (if needed)
        user_id = update.message.from_user.id
        USER_POINTS[user_id] = USER_POINTS.get(user_id, 0) + 1
    else:
        await update.message.reply_text("Wrong! Type /quiz to play again.")
    return ConversationHandler.END

# Doubt answer handler
async def handle_doubt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    doubt = update.message.text
    answer = generate_doubt_answer(doubt)
    await update.message.reply_text(answer)
    return ConversationHandler.END

# Cancel command handler
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Action cancelled. Type /quiz to start a quiz or /doubt to ask a question.")
    return ConversationHandler.END

# Main function to run the bot
def main() -> None:
    application = Application.builder().token(config.BOT_TOKEN).build()

    # Conversation handler for the quiz
    quiz_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('quiz', quiz)],
        states={
            CHOOSING_SUBJECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_subject)],
            CHOOSING_DIFFICULTY: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_difficulty)],
            ANSWERING_QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, answer_question)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    # Conversation handler for the doubt clearing
    doubt_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('doubt', doubt)],
        states={
            ASKING_DOUBT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_doubt)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    application.add_handler(CommandHandler('start', start))
    application.add_handler(quiz_conv_handler)
    application.add_handler(doubt_conv_handler)
    
    try:
        application.run_polling()
    except Exception as e:
        logger.error(f"An error occurred: {e}")

if __name__ == '__main__':
    main()
