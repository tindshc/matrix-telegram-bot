import os
import requests
import io
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

async def handle_matrix_logic(user_id, fname, formula, message):
    """Core logic for calculating/filtering and saving CSV"""
    file_id = db_get(user_id, fname)
    if not file_id:
        return False
        
    await message.reply_text(f"🔄 Đang xử lý trên file `{fname}`...", parse_mode='Markdown')
    file = await bot.get_file(file_id)
    content = requests.get(file.file_path).content.decode('utf-8')
    
    result_text, updated_csv = process_matrix(content, formula)
    
    await message.reply_text(result_text, parse_mode='Markdown')
    
    # If there's updated CSV, upload it back to Telegram and update Redis
    if updated_csv:
        csv_file = io.BytesIO(updated_csv.encode('utf-8'))
        csv_file.name = f"{fname}.csv"
        
        # Upload new version
        sent_msg = await bot.send_document(
            chat_id=message.chat_id,
            document=csv_file,
            caption=f"📂 Đã lưu bản cập nhật của `{fname}`",
            disable_notification=True
        )
        
        # Update Redis with new file_id
        db_set(user_id, fname, sent_msg.document.file_id)
        await message.reply_text(f"💾 Đã ghi đè dữ liệu mới vào tên file `{fname}`.", parse_mode='Markdown')
    
    return True

@app.post("/api/webhook")
async def webhook_handler(request: Request):
    """Handles Telegram Webhooks"""
    data = await request.json()
    update = Update.de_json(data, bot)
    
    if not update.effective_user:
        return {"status": "ok"}
    user_id = update.effective_user.id

    if update.callback_query:
        query = update.callback_query
        await query.answer()
        
        if query.data == 'mode_matrix':
            await query.edit_message_text(
                "📂 **Chế độ Matrix**\n\n- Gửi file CSV để lưu.\n- Xem cột theo số thứ tự: `tên_file hien`\n- Tìm theo số cột: `tên_file tim 3=='HOACUONG'`\n- Tính toán: `tên_file cột_mới = biểu_thức` (Sẽ tự lưu đè).\n- Lọc dữ liệu: `tên_file filter điều_kiện`.\n\nVD: `bctk filter Phuong=='HOACUONG'`",
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
        
        # 1. Commands
        if text.startswith("/start"):
            await message.reply_text("👋 Chào mừng!", reply_markup=get_main_menu())
            return {"status": "ok"}

        # 2. Handle Matrix (by Name or Reply)
        if text:
            # Check if it's "name formula"
            if " " in text:
                parts = text.split(" ", 1)
                fname = parts[0].strip().lower()
                formula = parts[1].strip()
                if await handle_matrix_logic(user_id, fname, formula, message):
                    return {"status": "ok"}
            
            # Check if it's a Reply to CSV
            if message.reply_to_message and message.reply_to_message.document:
                doc = message.reply_to_message.document
                if doc.file_name.endswith('.csv'):
                    fname = doc.file_name.lower().replace(".csv", "")
                    if await handle_matrix_logic(user_id, fname, text, message):
                        return {"status": "ok"}

        # 3. Handle Date
        if text and "/" in text and len(text) >= 8:
            res = process_date_input(text)
            await message.reply_text(res)
            return {"status": "ok"}

        # 4. Handle CSV Upload
        if message.document and message.document.file_name.endswith('.csv'):
            doc = message.document
            fname = doc.file_name.lower().replace(".csv", "")
            db_set(user_id, fname, doc.file_id)
            await message.reply_text(f"🔄 Đã ghi nhớ file: `{fname}`", parse_mode='Markdown')
            
            file = await bot.get_file(doc.file_id)
            content = requests.get(file.file_path).content.decode('utf-8')
            info = get_csv_info(content)
            await message.reply_text(info, parse_mode='Markdown')
            return {"status": "ok"}

    return {"status": "ok"}
