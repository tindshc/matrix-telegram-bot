import os
import requests
import io
import json
import pandas as pd
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
    delete_procedure_section,
)
from utils.db import db_set, db_get, db_list, db_delete, db_list_by_kind
from utils.db import db_set_kind, db_get_kind, db_delete_kind
from utils.db import db_set_state, db_get_state, db_delete_state
from utils.matrix import _parse_amount, _unique_nonempty_values, _append_row, _format_row_vertical

# Initialize FastAPI
app = FastAPI()

# Token from Environment Variable
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
bot = Bot(token=TOKEN)


def _is_markdown_name(name: str) -> bool:
    name = name.lower()
    return "md" in name


def _normalize_markdown_name(name: str) -> str:
    return os.path.splitext(name.lower())[0]


def _is_markdown_saved(user_id, fname):
    kind = db_get_kind(user_id, fname)
    if kind:
        return kind == "md"
    return "md" in fname.lower()

def get_main_menu():
    keyboard = [
        [InlineKeyboardButton("ℹ️ Hướng dẫn tính năng", callback_data='mode_help')],
        [InlineKeyboardButton("📋 Danh sách file CSV", callback_data='mode_list')]
    ]
    return InlineKeyboardMarkup(keyboard)


def _format_file_list(title, files, empty_text):
    if not files:
        return empty_text
    return f"{title}\n\n" + "\n".join([f"- `{f}`" for f in files])


def _csv_input_state_key(fname):
    return "csvinput"


def _csv_input_fields(df):
    return [col for col in df.columns if str(col).casefold() != "id"]


def _csv_input_prompt(df, field_name, position, total):
    values = _unique_nonempty_values(df[field_name])
    lines = [f"Bước {position}/{total}: nhập `{field_name}`"]

    if str(field_name).casefold() == "sotien":
        lines.append("Nhập số, ví dụ: 75 hoặc 15,5")
        lines.append("Gõ /cancel để hủy.")
        return "\n".join(lines)

    if values and len(values) <= 8:
        lines.append("Chọn số hoặc gõ giá trị mới:")
        for idx, value in enumerate(values, 1):
            lines.append(f"{idx}. {value}")
        lines.append("Gõ /cancel để hủy.")
        return "\n".join(lines)

    lines.append("Nhập nội dung.")
    lines.append("Gõ /cancel để hủy.")
    return "\n".join(lines)

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

    formula = formula.strip()
    formula_lower = formula.lower()

    if formula_lower == "cachnhap":
        help_text, _ = process_matrix(content, "nhap")
        await message.reply_text(help_text)
        return True

    if formula_lower == "nhap gui":
        return await _start_csv_input_session(user_id, fname, message)
    
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


async def _start_csv_input_session(user_id, fname, message):
    file_id = db_get(user_id, fname)
    if not file_id:
        return False

    file = await bot.get_file(file_id)
    content = requests.get(file.file_path).content.decode('utf-8')
    df = pd.read_csv(io.StringIO(content), engine='python')
    fields = _csv_input_fields(df)

    if not fields:
        await message.reply_text("❌ File CSV này không có cột nào để nhập.")
        return True

    state = {"fname": fname, "index": 0, "values": {}}
    db_set_state(user_id, _csv_input_state_key(fname), json.dumps(state, ensure_ascii=False))

    help_text, _ = process_matrix(content, "nhap")
    await message.reply_text(help_text)
    await message.reply_text(_csv_input_prompt(df, fields[0], 1, len(fields)))
    return True


async def _continue_csv_input_session(user_id, text, message):
    state_raw = db_get_state(user_id, _csv_input_state_key(""))
    if not state_raw:
        return False

    try:
        state = json.loads(state_raw)
    except Exception:
        db_delete_state(user_id, _csv_input_state_key(""))
        return False

    fname = state.get("fname")
    if not fname:
        db_delete_state(user_id, _csv_input_state_key(""))
        return False

    answer = text.strip()
    if answer.lower() in {"/cancel", "cancel", "huy", "hủy"}:
        db_delete_state(user_id, _csv_input_state_key(""))
        await message.reply_text(f"🛑 Đã hủy nhập cho file `{fname}`.", parse_mode='Markdown')
        return True

    file_id = db_get(user_id, fname)
    if not file_id:
        db_delete_state(user_id, _csv_input_state_key(""))
        await message.reply_text(f"❌ Không tìm thấy file `{fname}` trong bộ nhớ.", parse_mode='Markdown')
        return True

    file = await bot.get_file(file_id)
    content = requests.get(file.file_path).content.decode('utf-8')
    df = pd.read_csv(io.StringIO(content), engine='python')
    fields = _csv_input_fields(df)
    index = int(state.get("index", 0))
    values = state.get("values", {})

    if index >= len(fields):
        db_delete_state(user_id, _csv_input_state_key(""))
        return False

    field_name = fields[index]
    field_lower = str(field_name).casefold()
    value = answer

    if field_lower == "sotien":
        parsed_amount = _parse_amount(answer)
        if parsed_amount is None:
            await message.reply_text("❌ Cột `sotien` phải là số, ví dụ `75` hoặc `15,5`.")
            await message.reply_text(_csv_input_prompt(df, field_name, index + 1, len(fields)))
            return True
        value = parsed_amount
    elif field_lower in {"muc", "thuchi"}:
        options = _unique_nonempty_values(df[field_name])
        if answer.isdigit():
            opt_index = int(answer) - 1
            if 0 <= opt_index < len(options):
                value = options[opt_index]

    values[field_name] = value
    state["index"] = index + 1
    state["values"] = values

    if state["index"] < len(fields):
        db_set_state(user_id, _csv_input_state_key(""), json.dumps(state, ensure_ascii=False))
        next_field = fields[state["index"]]
        await message.reply_text(_csv_input_prompt(df, next_field, state["index"] + 1, len(fields)))
        return True

    appended, error = _append_row(df, values)
    if error:
        db_delete_state(user_id, _csv_input_state_key(""))
        await message.reply_text(error)
        return True

    updated_csv = appended.to_csv(index=False)
    csv_file = io.BytesIO(updated_csv.encode('utf-8'))
    csv_file.name = f"{fname}.csv"

    sent_msg = await bot.send_document(
        chat_id=message.chat_id,
        document=csv_file,
        caption=f"📂 Đã lưu bản cập nhật của `{fname}`",
        disable_notification=True
    )

    db_set(user_id, fname, sent_msg.document.file_id)
    db_set_kind(user_id, fname, "csv")
    db_delete_state(user_id, _csv_input_state_key(""))

    await message.reply_text(_format_row_vertical(appended, len(appended)), parse_mode='Markdown')
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

    def _parse_path(text):
        parts = text.split()
        if len(parts) < 2:
            return None
        path = []
        for token in parts[1:]:
            if not token.isdigit():
                return None
            path.append(int(token))
        return path

    if formula_lower.startswith("them "):
        source_name = formula[5:].strip().lower()
        source_name = _normalize_markdown_name(source_name)

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
        db_set_kind(user_id, fname, "md")
        db_delete(user_id, source_name)
        db_delete_kind(user_id, source_name)

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

    if formula_lower.startswith("xoa "):
        path = _parse_path(formula)
        if path is None:
            await message.reply_text(
                "❌ Dùng đúng dạng <b>xoa 2</b> hoặc <b>xoa 2 1</b>.",
                parse_mode='HTML',
            )
            return True

        updated_content, deleted_title = delete_procedure_section(content, path)
        if updated_content is None:
            await message.reply_text("❌ Số mục không hợp lệ.", parse_mode='HTML')
            return True

        updated_file = io.BytesIO(updated_content.encode('utf-8'))
        updated_file.name = f"{fname}.md"
        sent_msg = await bot.send_document(
            chat_id=message.chat_id,
            document=updated_file,
            caption=f"📂 Đã xóa mục {' '.join(map(str, path))} khỏi `{fname}`",
            disable_notification=True
        )

        db_set(user_id, fname, sent_msg.document.file_id)
        db_set_kind(user_id, fname, "md")

        await message.reply_text(
            f"✅ Đã xóa mục {' '.join(map(str, path))}: `{deleted_title}` khỏi `{fname}`.",
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
                    "ℹ️ **Hướng dẫn tính năng**\n\n- Upload CSV để nạp file, ví dụ `bctk.csv`.\n- CSV dùng lệnh: `tên_file hien`, `tên_file hien muc`, `tên_file cachnhap`, `tên_file nhap 1=1 2=1 3=15,5 4=Sương nộp` hoặc `tên_file nhap 1 1 15,5 Sương nộp`, `tên_file nhap gui`, `tên_file tim ...`, `tên_file xem ...`, `tên_file xoa`.\n- Dùng `/list` để xem danh sách file CSV, `/listmd` để xem danh sách file Markdown.\n- Ánh xạ số nhập: `1=muc`, `2=thuchi`, `3=sotien`, `4=noidung`.\n- Với file có cột `muc`, `thuchi`, `sotien`, ba trường này là bắt buộc khi `nhap`.\n- Dạng ngắn của `nhap` sẽ đi theo thứ tự cột thật của file, ví dụ `muc thuchi sotien noidung`.\n- Markdown dùng tên có chữ `md` trong tên, ví dụ `mdquytrinh.md` hoặc `luatmd.doc.md`.\n- Markdown dùng `tên_file hien` hoặc `tên_file hien 1` để xem mục lục, ví dụ `mdphongtuc hien` sẽ hiện các chủ đề lớn; `tên_file xem 1 1` hoặc `tên_file xem 1 1 1` để xem toàn bộ chi tiết của nhánh đó, `tên_file xoa 2` để xóa mục theo số thứ tự, `tên_file them file.md` để gộp file.\n- Lịch âm dương dùng `callicham 10/3/2026` hoặc `callicham am 10/3/2026`.\n- Quản lý file: `/list`, `/listmd`, `/del <tên_file>`.\n\nVí dụ: `bctk tim 5~'hoacuong' and 1==2020`",
                    parse_mode='Markdown'
                )
            elif query.data == 'mode_list':
                files = db_list_by_kind(user_id, "csv")
                text = _format_file_list("📋 **Danh sách file CSV của bạn:**", files, "📭 Bạn chưa lưu file CSV nào.")
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
                db_delete_kind(user_id, fname)
                if existed:
                    await message.reply_text(f"🗑️ Đã xóa file `{fname}` khỏi bộ nhớ.", parse_mode='Markdown')
                else:
                    await message.reply_text(f"⚠️ Không tìm thấy file `{fname}` trong bộ nhớ.", parse_mode='Markdown')
                return {"status": "ok"}

            if text.lower() == "/list":
                files = db_list_by_kind(user_id, "csv")
                text_out = _format_file_list("📋 **Danh sách file CSV của bạn:**", files, "📭 Bạn chưa lưu file CSV nào.")
                await message.reply_text(text_out, parse_mode='Markdown')
                return {"status": "ok"}

            if text.lower() == "/listmd":
                files = db_list_by_kind(user_id, "md")
                text_out = _format_file_list("📋 **Danh sách file Markdown của bạn:**", files, "📭 Bạn chưa lưu file Markdown nào.")
                await message.reply_text(text_out, parse_mode='Markdown')
                return {"status": "ok"}

            if text.lower() == "/cancel":
                state_raw = db_get_state(user_id, _csv_input_state_key(""))
                if state_raw:
                    try:
                        state = json.loads(state_raw)
                        fname = state.get("fname", "")
                    except Exception:
                        fname = ""
                    db_delete_state(user_id, _csv_input_state_key(""))
                    if fname:
                        await message.reply_text(f"🛑 Đã hủy nhập cho file `{fname}`.", parse_mode='Markdown')
                    else:
                        await message.reply_text("🛑 Đã hủy phiên nhập đang chờ.")
                else:
                    await message.reply_text("Không có phiên nhập nào đang chạy.")
                return {"status": "ok"}

            if text and not text.startswith("/"):
                if await _continue_csv_input_session(user_id, text, message):
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
                        db_delete_kind(user_id, fname)
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
                    if _is_markdown_saved(user_id, fname):
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
                    if _is_markdown_name(doc.file_name):
                        fname = _normalize_markdown_name(doc.file_name)
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
                db_set_kind(user_id, fname, "csv")
                await message.reply_text(f"🔄 Đã ghi nhớ file: `{fname}`", parse_mode='Markdown')
                
                file = await bot.get_file(doc.file_id)
                content = requests.get(file.file_path).content.decode('utf-8')
                info = get_csv_info(content)
                await message.reply_text(info)
                return {"status": "ok"}

            if message.document and _is_markdown_name(message.document.file_name):
                doc = message.document
                fname = _normalize_markdown_name(doc.file_name)
                db_set(user_id, fname, doc.file_id)
                db_set_kind(user_id, fname, "md")
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
