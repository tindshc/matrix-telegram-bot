import os
import requests
import io
from fastapi import FastAPI, Request
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

from utils.matrix import get_csv_info, process_matrix
from utils.calendar import process_date_input, process_callicham_input
from utils.procedure import (
    get_procedure_info,
    process_procedure_markdown,
    merge_procedure_documents,
    count_procedure_sections,
)
from utils.db import db_set, db_get, db_list, db_delete

# Initialize FastAPI
app = FastAPI()

# Token from Environment Variable
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
bot = Bot(token=TOKEN)

def get_main_menu():
    keyboard = [
        [InlineKeyboardButton("ℹ️ Hướng dẫn tính năng", callback_data='mode_help')],
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


async def handle_markdown_logic(user_id, fname, formula, message):
    """Core logic for structured Markdown workflow docs."""
    file_id = db_get(user_id, fname)
    if not file_id:
        return False

    await message.reply_text(f"🔄 Đang xử lý trên file `{fname}`...", parse_mode='Markdown')
    file = await bot.get_file(file_id)
    content = requests.get(file.file_path).content.decode('utf-8')

    formula = formula.strip()
    formula_lower = formula.lower()

    if formula_lower.startswith("them "):
        source_name = formula[5:].strip().lower()
        if source_name.endswith(".md"):
            source_name = source_name[:-3]

        if source_name == fname:
            await message.reply_text("❌ Không thể gộp file vào chính nó.", parse_mode='Markdown')
            return True

        source_file_id = db_get(user_id, source_name)
        if not source_file_id:
            await message.reply_text(f"❌ Không tìm thấy file nguồn `{source_name}`.", parse_mode='Markdown')
            return True

        source_file = await bot.get_file(source_file_id)
        source_content = requests.get(source_file.file_path).content.decode('utf-8')
        merged_content = merge_procedure_documents(content, source_content)

        merged_file = io.BytesIO(merged_content.encode('utf-8'))
        merged_file.name = f"{fname}.md"
        sent_msg = await bot.send_document(
            chat_id=message.chat_id,
            document=merged_file,
            caption=f"📂 Đã gộp `{source_name}` vào `{fname}`",
            disable_notification=True
        )

        db_set(user_id, fname, sent_msg.document.file_id)
        db_delete(user_id, source_name)

        base_count = count_procedure_sections(content)
        extra_count = count_procedure_sections(source_content)
        await message.reply_text(
            f"✅ Đã gộp `{source_name}` vào `{fname}`.\n"
            f"- Mục chính cũ: {base_count}\n"
            f"- Mục chính thêm: {extra_count}\n"
            f"- File nguồn `{source_name}` đã được xóa khỏi bộ nhớ.",
            parse_mode='Markdown'
        )
        return True

    result_text, _ = process_procedure_markdown(content, formula)
    await message.reply_text(result_text, parse_mode='HTML')
    return True

@app.post("/api/webhook")
async def webhook_handler(request: Request):
    """Handles Telegram Webhooks"""
    try:
        data = await request.json()
        update = Update.de_json(data, bot)
        
        if not update.effective_user:
            return {"status": "ok"}
        user_id = update.effective_user.id

        if update.callback_query:
            query = update.callback_query
            await query.answer()
            
            if query.data == 'mode_help':
                await query.edit_message_text(
                    "ℹ️ **Hướng dẫn tính năng**\n\n- Upload CSV để nạp file, ví dụ `bctk.csv`.\n- CSV dùng lệnh: `tên_file hien`, `tên_file tim ...`, `tên_file xem ...`, `tên_file xoa`.\n- Markdown quy trình dùng tên có tiền tố `md`, ví dụ `mdquytrinh.md`.\n- Quy trình Markdown dùng `mdquytrinh hien`, `mdquytrinh tim ~...`, `mdquytrinh xem 1 1`, `mdquytrinh them file.md`.\n- Lịch âm dương dùng `callicham 10/3/2026` hoặc `callicham am 10/3/2026`.\n- Quản lý file: `/list`, `/del <tên_file>`.\n\nVí dụ: `bctk tim 5~'hoacuong' and 1==2020`",
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

            if text.lower().startswith("/del"):
                parts = text.split(maxsplit=1)
                if len(parts) < 2:
                    await message.reply_text("Dùng: `/del <tên_file>`", parse_mode='Markdown')
                    return {"status": "ok"}

                fname = parts[1].strip().lower()
                existed = db_get(user_id, fname)
                db_delete(user_id, fname)
                if existed:
                    await message.reply_text(f"🗑️ Đã xóa file `{fname}` khỏi bộ nhớ.", parse_mode='Markdown')
                else:
                    await message.reply_text(f"⚠️ Không tìm thấy file `{fname}` trong bộ nhớ.", parse_mode='Markdown')
                return {"status": "ok"}

            # 2. Handle Matrix (by Name or Reply)
            if text:
                if " " in text:
                    parts = text.split(" ", 1)
                    fname = parts[0].strip().lower()
                    action = parts[1].strip().lower()
                    if action in {"xoa", "del", "delete"}:
                        existed = db_get(user_id, fname)
                        db_delete(user_id, fname)
                        if existed:
                            await message.reply_text(f"🗑️ Đã xóa file `{fname}` khỏi bộ nhớ.", parse_mode='Markdown')
                        else:
                            await message.reply_text(f"⚠️ Không tìm thấy file `{fname}` trong bộ nhớ.", parse_mode='Markdown')
                        return {"status": "ok"}

                # Check if it's "name formula"
                if " " in text:
                    parts = text.split(" ", 1)
                    fname = parts[0].strip().lower()
                    formula = parts[1].strip()
                    if fname.startswith("md"):
                        if await handle_markdown_logic(user_id, fname, formula, message):
                            return {"status": "ok"}
                    if await handle_matrix_logic(user_id, fname, formula, message):
                        return {"status": "ok"}
                
                # Check if it's a Reply to CSV
                if message.reply_to_message and message.reply_to_message.document:
                    doc = message.reply_to_message.document
                    if doc.file_name.lower().endswith('.csv'):
                        fname = doc.file_name.lower().replace(".csv", "")
                        if await handle_matrix_logic(user_id, fname, text, message):
                            return {"status": "ok"}
                    if doc.file_name.lower().endswith('.md'):
                        fname = doc.file_name.lower().replace(".md", "")
                        if await handle_markdown_logic(user_id, fname, text, message):
                            return {"status": "ok"}

            # 3. Handle Date
            cal_res = process_callicham_input(text)
            if cal_res is not None:
                await message.reply_text(cal_res)
                return {"status": "ok"}

            if text and "/" in text and len(text) >= 8:
                res = process_date_input(text)
                await message.reply_text(res)
                return {"status": "ok"}

            # 4. Handle file upload
            if message.document and message.document.file_name.lower().endswith('.csv'):
                doc = message.document
                fname = doc.file_name.lower().replace(".csv", "")
                db_set(user_id, fname, doc.file_id)
                await message.reply_text(f"🔄 Đã ghi nhớ file: `{fname}`", parse_mode='Markdown')
                
                file = await bot.get_file(doc.file_id)
                content = requests.get(file.file_path).content.decode('utf-8')
                info = get_csv_info(content)
                await message.reply_text(info)
                return {"status": "ok"}

            if message.document and message.document.file_name.lower().endswith('.md'):
                doc = message.document
                fname = doc.file_name.lower().replace(".md", "")
                db_set(user_id, fname, doc.file_id)
                await message.reply_text(f"🔄 Đã ghi nhớ file quy trình: `{fname}`", parse_mode='Markdown')

                file = await bot.get_file(doc.file_id)
                content = requests.get(file.file_path).content.decode('utf-8')
                info = get_procedure_info(content)
                await message.reply_text(info, parse_mode='HTML')
                return {"status": "ok"}

        return {"status": "ok"}
    except Exception as e:
        print(f"Webhook error: {e}")
        return {"status": "ok"}
