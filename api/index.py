import os
import json
import requests
from fastapi import FastAPI, Request
from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

from utils.matrix import get_csv_info, process_matrix
from utils.calendar import solar_to_lunar_str

# Initialize FastAPI
app = FastAPI()

# Token from Environment Variable
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
bot = Bot(token=TOKEN)

@app.get("/")
def read_root():
    return {"message": "Telegram Bot is running!"}

@app.post("/api/webhook")
async def webhook_handler(request: Request):
    """Handles Telegram Webhooks"""
    data = await request.json()
    update = Update.de_json(data, bot)
    
    if update.message:
        message = update.message
        
        # 1. Handle Commands
        if message.text:
            text = message.text.strip()
            
            if text.startswith("/start"):
                await message.reply_text(
                    "Chào mừng! Tôi là Bot trợ lý tính toán.\n\n"
                    "1. Gửi file CSV để tính toán Matrix.\n"
                    "2. Gửi ngày dạng `dd/mm/yyyy` để xem lịch âm, can chi, tiết khí.\n"
                    "Ví dụ: `24/04/2026`"
                )
                return {"status": "ok"}

            # Handle date format (simple regex check or try-except)
            if "/" in text and len(text) >= 8:
                res = solar_to_lunar_str(text)
                await message.reply_text(res)
                return {"status": "ok"}

            # 2. Handle Formulas (as replies to CSV)
            if message.reply_to_message and message.reply_to_message.document:
                doc = message.reply_to_message.document
                if doc.file_name.endswith('.csv'):
                    await message.reply_text("🔄 Đang tính toán...")
                    file = await bot.get_file(doc.file_id)
                    content = requests.get(file.file_path).text
                    
                    result = process_matrix(content, text)
                    await message.reply_text(result, parse_mode='Markdown')
                    return {"status": "ok"}

        # 3. Handle CSV Upload
        if message.document and message.document.file_name.endswith('.csv'):
            await message.reply_text("🔄 Đang đọc file...")
            file = await bot.get_file(message.document.file_id)
            content = requests.get(file.file_path).text
            
            info = get_csv_info(content)
            await message.reply_text(info + "\n\n💡 **Mẹo**: Hãy REPLY (Trả lời) vào file này với công thức của bạn (VD: `cbr = sosinh * 1000 / dstb`)", parse_mode='Markdown')
            return {"status": "ok"}

    return {"status": "ok"}
