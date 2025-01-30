import asyncio
import logging
import requests
from pymongo import MongoClient
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import google.generativeai as genai

# Configuration
TOKEN = "7766013933:AAETZvlgdmGDGb7pxnYsmTxG5B8s-GxCiWk"
MONGO_URI = "mongodb+srv://peraboinasanthosh28:7LjouB5QlQ8dHuOj@cluster0.utrms.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
GEMINI_API_KEY = "AIzaSyB1X3VR_LGCfZdzDc_FAyEA-B5hNXasSSg"
GOOGLE_SEARCH_API_KEY = "YOUR_GOOGLE_SEARCH_API_KEY"
GOOGLE_CX_ID = "YOUR_CX_ID"  # Custom Search Engine ID

# Initialize MongoDB
client = MongoClient(MONGO_URI)
db = client["telegram_bot"]
users_collection = db["users"]
chats_collection = db["chats"]
files_collection = db["files"]

genai.configure(api_key=GEMINI_API_KEY)

# Logging setup
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.message.from_user
    existing_user = users_collection.find_one({"chat_id": user.id})
    
    if not existing_user:
        users_collection.insert_one({
            "chat_id": user.id,
            "first_name": user.first_name,
            "username": user.username,
            "phone_number": None
        })
        
        keyboard = [[KeyboardButton("Share Contact", request_contact=True)]]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        await update.message.reply_text("Please share your contact number to complete registration.", reply_markup=reply_markup)
    else:
        await update.message.reply_text("Welcome back! How can I assist you today?")

async def contact_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.message.from_user
    contact = update.message.contact
    
    users_collection.update_one({"chat_id": user.id}, {"$set": {"phone_number": contact.phone_number}})
    await update.message.reply_text("Thank you! Your registration is complete.")

async def chat_with_gemini(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.message.from_user
    text = update.message.text
    
    model = genai.GenerativeModel("gemini-pro")
    chat_response = model.generate_content(text)
    reply = chat_response.candidates[0].content if chat_response and chat_response.candidates else "Sorry, I couldn't process that."
    
    await update.message.reply_text(reply)
    
    chats_collection.insert_one({
        "chat_id": user.id,
        "user_input": text,
        "bot_response": reply
    })

async def handle_files(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.message.from_user
    document = update.message.document or update.message.photo[-1]
    
    file_id = document.file_id
    file = await context.bot.get_file(file_id)
    file_data = await file.download_as_bytearray()
    
    model = genai.GenerativeModel("gemini-pro-vision")
    response = model.generate_content([file_data])
    description = response.candidates[0].content if response and response.candidates else "Could not analyze the file."
    
    await update.message.reply_text(f"File analyzed: {description}")
    
    files_collection.insert_one({
        "chat_id": user.id,
        "file_id": file_id,
        "description": description
    })

async def web_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = " ".join(context.args)
    if not query:
        await update.message.reply_text("Please provide a search query.")
        return
    
    response = requests.get(f"https://www.googleapis.com/customsearch/v1?q={query}&key={GOOGLE_SEARCH_API_KEY}&cx={GOOGLE_CX_ID}")
    results = response.json().get("items", [])
    
    summary = "\n".join([f"{i+1}. {item['title']}: {item['link']}" for i, item in enumerate(results[:5])])
    await update.message.reply_text(summary if summary else "No results found.")

async def main():
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.CONTACT, contact_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat_with_gemini))
    app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, handle_files))
    app.add_handler(CommandHandler("websearch", web_search))
    
    await app.run_polling()

if __name__ == '__main__':
    asyncio.run(main())
