import os
import requests
from fastapi import FastAPI, Request
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

from utils.matrix import get_csv_info, process_matrix
from utils.calendar import process_date_input
from utils.db import db_set, db_get, db_list, db_delete

# Initialize FastAPI
app = FastAPI()

# Token from Environment Variable
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
bot = Bot(token=TOKEN)

def get_main_menu():
    keyboard = [
        [InlineKeyboardButton("📊 Tính Matrix (CSV)", callback_data='mode_matrix')],
        [InlineKeyboardButton("🌙 Xem Lịch Âm/Dương", callback_data='mode_calendar')],
        [InlineKeyboardButton("📋 Danh sách file đã lưu", callback_data='mode_list')]
    ]
    return InlineKeyboardMarkup(keyboard)

@app.get("/")
def read_root():
    return {"message": "Telegram Bot is running!"}

@app.post("/api/webhook")
async def webhook_handler(request: Request):
    """Handles Telegram Webhooks"""
    data = await request.json()
    update = Update.de_json(data, bot)
    
    user_id = update.effective_user.id

    if update.callback_query:
        query = update.callback_query
        await query.answer()
        
        if query.data == 'mode_matrix':
            await query.edit_message_text(
                "📂 **Chế độ Matrix**\n\n- Gửi file CSV để lưu vào bộ nhớ.\n- Hoặc gõ `tên_file công_thức` để tính.\n\nVD: `bctk cbr=sosinh*1000/dstb`",
                parse_mode='Markdown'
            )
        elif query.data == 'mode_calendar':
            await query.edit_message_text(
                "📅 **Chế độ Xem Lịch**\n\n- Nhập `dd/mm/yyyy` (Dương -> Âm)\n- Nhập `am dd/mm/yyyy` (Âm -> Dương)",
                parse_mode='Markdown'
            )
        elif query.data == 'mode_list':
            files = db_list(user_id)
            if not files:
                await query.edit_message_text("📭 Bạn chưa lưu file nào.")
            else:
                text = "📋 **Danh sách file của bạn:**\n\n" + "\n".join([f"- `{f}`" for f in files])
                await query.edit_message_text(text, parse_mode='Markdown')
        return {"status": "ok"}

    if update.message:
        message = update.message
        text = message.text.strip() if message.text else ""
        
        # 1. Handle Commands
        if text.startswith("/start"):
            await message.reply_text(
                "👋 Chào mừng bạn! Tôi đã sẵn sàng hỗ trợ.\n\nHãy chọn chức năng:",
                reply_markup=get_main_menu()
            )
            return {"status": "ok"}

        if text.startswith("/list"):
            files = db_list(user_id)
            await message.reply_text("📋 Các file đã lưu: " + ", ".join(files) if files else "Chưa có file nào.")
            return {"status": "ok"}

        if text.startswith("/del "):
            fname = text.replace("/del ", "").strip()
            db_delete(user_id, fname)
            await message.reply_text(f"🗑 Đã xóa file `{fname}` khỏi bộ nhớ.", parse_mode='Markdown')
            return {"status": "ok"}

        # 2. Handle Matrix by Name (e.g. "bctk cbr=...")
        if text and " " in text:
            parts = text.split(" ", 1)
            fname = parts[0].strip()
            formula = parts[1].strip()
            
            file_id = db_get(user_id, fname)
            if file_id:
                await message.reply_text(f"🔄 Đang tính toán trên file `{fname}`...", parse_mode='Markdown')
                file = await bot.get_file(file_id)
                file_url = f"https://api.telegram.org/file/bot{TOKEN}/{file.file_path}"
                content = requests.get(file_url).content.decode('utf-8')
                result = process_matrix(content, formula)
                await message.reply_text(f"✅ **Kết quả ({fname})**:\n\n{result}", parse_mode='Markdown')
                return {"status": "ok"}

        # 3. Handle Date Input
        if text and "/" in text and len(text) >= 8:
            res = process_date_input(text)
            await message.reply_text(res)
            return {"status": "ok"}

        # 4. Handle CSV Upload (Save to Redis)
        if message.document and message.document.file_name.endswith('.csv'):
            doc = message.document
            fname = doc.file_name.replace(".csv", "").lower()
            
            # Save mapping in Redis
            db_set(user_id, fname, doc.file_id)
            
            await message.reply_text(f"🔄 Đã đọc file và lưu tên: `{fname}`", parse_mode='Markdown')
            
            file = await bot.get_file(doc.file_id)
            file_url = f"https://api.telegram.org/file/bot{TOKEN}/{file.file_path}"
            content = requests.get(file_url).content.decode('utf-8')
            info = get_csv_info(content)
            
            await message.reply_text(
                f"{info}\n\n💡 **Mẹo**: Bạn có thể gõ `{fname} công_thức` bất cứ lúc nào để tính.",
                parse_mode='Markdown'
            )
            return {"status": "ok"}

        # 5. Handle CSV Formula (Reply to CSV)
        if text and message.reply_to_message and message.reply_to_message.document:
            doc = message.reply_to_message.document
            if doc.file_name.endswith('.csv'):
                await message.reply_text("🔄 Đang tính toán trên file này...")
                file = await bot.get_file(doc.file_id)
                file_url = f"https://api.telegram.org/file/bot{TOKEN}/{file.file_path}"
                content = requests.get(file_url).content.decode('utf-8')
                result = process_matrix(content, text)
                await message.reply_text(f"✅ **Kết quả**:\n\n{result}", parse_mode='Markdown')
                return {"status": "ok"}

    return {"status": "ok"}
