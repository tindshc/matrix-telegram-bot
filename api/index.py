import os
import requests
import io
import json
import re
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
from utils.jobs import (
    is_job_name,
    job_file_type,
    job_default_df,
    ensure_job_schema,
    job_help_text,
    format_task_list,
    format_task_detail,
    mark_task_done,
    mark_task_done_visible,
    add_task,
    format_roster_summary,
    add_roster_entry,
    parse_job_task_payload,
    parse_job_roster_payload,
    parse_job_roster_bulk_payload,
    parse_job_date_text,
    roster_members,
    roster_members_for_department,
    roster_departments,
    JOB_KIND,
)

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


def _is_job_saved(user_id, fname):
    kind = db_get_kind(user_id, fname)
    if kind:
        return kind == JOB_KIND
    return is_job_name(fname)


def _job_state_key(fname):
    return "jobinput"


def _normalize_job_command(text):
    parts = text.strip().split()
    if not parts or not is_job_name(parts[0]):
        return None, None

    fname = parts[0].lower()
    formula = text[len(parts[0]):].strip()
    return fname, formula


def _known_job_departments(user_id):
    return []

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
        lines.append("Gõ /back để quay lại bước trước, /cancel để hủy.")
        return "\n".join(lines)

    if values and len(values) <= 8:
        lines.append("Chọn số hoặc gõ giá trị mới:")
        for idx, value in enumerate(values, 1):
            lines.append(f"{idx}. {value}")
        lines.append("Gõ số để chọn, hoặc gõ giá trị mới.")
        lines.append("Gõ /back để quay lại bước trước, /cancel để hủy.")
        return "\n".join(lines)

    lines.append("Nhập nội dung.")
    lines.append("Gõ /back để quay lại bước trước, /cancel để hủy.")
    return "\n".join(lines)


def _job_input_fields(fname, department=None):
    if job_file_type(fname) == "roster":
        return ["ten"] if department else ["phong", "ten"]
    return ["han", "viec", "phong", "diadiem", "nguoi", "ghichu"]


def _job_input_prompt(fname, df, field_name, position, total, department=None, selection_options=None):
    lines = [f"Bước {position}/{total}: nhập `{field_name}`"]
    kind = job_file_type(fname)

    if kind == "roster":
        if field_name == "phong":
            depts = selection_options or roster_departments(df)
            lines.append("Nhập phòng, ví dụ: `ds`, `gd`.")
            lines.append("Bạn có thể gõ số bên dưới nếu muốn chọn nhanh, nhưng không bắt buộc:")
            for idx, dept in enumerate(depts, 1):
                lines.append(f"{idx}. {dept}")
            lines.append("Gõ /back để quay lại bước trước, /cancel để hủy.")
            return "\n".join(lines)
        lines.append("Nhập tên ngắn, ví dụ: `ld`, `ngamy`, `congtin`.")
        lines.append("Gõ /back để quay lại bước trước, /cancel để hủy.")
        return "\n".join(lines)

    if field_name == "han":
        lines.append("Nhập ngày, ví dụ: `28/4` hoặc `28/4/2026`.")
        lines.append("Nếu là âm lịch, gõ `am 10/3` hoặc `am 10/3/2026`.")
        lines.append("Gõ /back để quay lại bước trước, /cancel để hủy.")
        return "\n".join(lines)

    if field_name == "diadiem":
        lines.append("Nhập địa điểm họp, ví dụ: `UBND phường`, hoặc để trống nếu không có.")
        lines.append("Gõ `-` hoặc `/skip` để bỏ qua.")
        lines.append("Gõ /back để quay lại bước trước, /cancel để hủy.")
        return "\n".join(lines)

    if field_name == "phong":
        lines.append("Nhập bộ phận, ví dụ: `ds`, `gd`.")
        lines.append("Gõ /back để quay lại bước trước, /cancel để hủy.")
        return "\n".join(lines)

    if field_name == "nguoi":
        options = selection_options or []
        if options:
            lines.append("Chọn người/nhóm phụ trách, có thể nhập nhiều số như `1,2`:")
            for idx, value in enumerate(options, 1):
                lines.append(f"{idx}. {value}")
        else:
            lines.append("Nhập người phụ trách hoặc danh sách ngắn, ví dụ: `ld`, `ngamy`, `congtin`.")
        lines.append("Gõ /back để quay lại bước trước, /cancel để hủy.")
        return "\n".join(lines)

    lines.append("Nhập nội dung.")
    lines.append("Gõ /back để quay lại bước trước, /cancel để hủy.")
    return "\n".join(lines)


async def _save_dataframe_file(user_id, fname, df, message, kind, caption_prefix):
    csv_file = io.BytesIO(df.to_csv(index=False).encode("utf-8"))
    csv_file.name = f"{fname}.csv"
    sent_msg = await bot.send_document(
        chat_id=message.chat_id,
        document=csv_file,
        caption=f"{caption_prefix} `{fname}`",
        disable_notification=True,
    )
    db_set(user_id, fname, sent_msg.document.file_id)
    db_set_kind(user_id, fname, kind)
    return sent_msg


async def _load_job_dataframe(user_id, fname, message, create_if_missing=True):
    file_id = db_get(user_id, fname)
    if not file_id:
        if not create_if_missing:
            return None, None
        df = job_default_df(fname)
        await _save_dataframe_file(user_id, fname, df, message, JOB_KIND, "📂 Đã tạo file việc mới")
        return df, ""

    file = await bot.get_file(file_id)
    content = requests.get(file.file_path).content.decode("utf-8")
    df = pd.read_csv(io.StringIO(content), engine="python")
    return ensure_job_schema(df, fname), content


async def _load_job_roster_dataframe(user_id):
    file_id = db_get(user_id, "jphong")
    if not file_id:
        return None
    file = await bot.get_file(file_id)
    content = requests.get(file.file_path).content.decode("utf-8")
    df = pd.read_csv(io.StringIO(content), engine="python")
    return ensure_job_schema(df, "jphong")


async def _job_member_options(user_id, department=None):
    df = await _load_job_roster_dataframe(user_id)
    if df is None:
        return ["ld", "ngamy", "congtin"]
    return roster_members_for_department(df, department)


async def _job_department_options(user_id):
    df = await _load_job_roster_dataframe(user_id)
    if df is None:
        return ["ds"]
    return roster_departments(df)


def _parse_multi_selection(answer, options):
    raw = str(answer).strip()
    if not raw:
        return ""

    tokens = [part.strip() for part in raw.split(",") if part.strip()]
    if len(tokens) == 1 and " " in tokens[0]:
        tokens = [part.strip() for part in tokens[0].split() if part.strip()]

    selected = []
    for token in tokens:
        if token.isdigit():
            idx = int(token) - 1
            if 0 <= idx < len(options):
                selected.append(options[idx])
                continue
        selected.append(token)

    return ", ".join(selected) if selected else raw

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

    if answer.lower() in {"/back", "back", "quaylai", "quay lại"}:
        current_index = int(state.get("index", 0))
        if current_index <= 0:
            await message.reply_text("ℹ️ Đây là bước đầu tiên, không thể quay lại.")
            return True

        current_index -= 1
        values = state.get("values", {})
        prev_field = fields[current_index]
        values.pop(prev_field, None)
        state["index"] = current_index
        state["values"] = values
        db_set_state(user_id, _csv_input_state_key(""), json.dumps(state, ensure_ascii=False))
        await message.reply_text(f"↩️ Đã quay lại bước `{prev_field}`.", parse_mode='Markdown')
        await message.reply_text(_csv_input_prompt(df, prev_field, current_index + 1, len(fields)))
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
        await message.reply_text(f"✅ Đã nhận `{field_name}` = `{value}`.", parse_mode='Markdown')
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

    await message.reply_text(f"✅ Đã nhận `{field_name}` = `{value}`.", parse_mode='Markdown')
    await message.reply_text(_format_row_vertical(appended, len(appended)), parse_mode='Markdown')
    return True


async def _start_job_input_session(user_id, fname, message, department=None):
    df, _ = await _load_job_dataframe(user_id, fname, message, create_if_missing=True)
    if df is None:
        await message.reply_text("❌ Không thể khởi tạo file việc.")
        return True

    fields = _job_input_fields(fname, department=department)
    state = {"fname": fname, "index": 0, "values": {}, "department": department}
    db_set_state(user_id, _job_state_key(fname), json.dumps(state, ensure_ascii=False))

    selection_options = None
    if fields[0] == "nguoi":
        selection_options = await _job_member_options(user_id, department)
    elif fields[0] == "phong":
        selection_options = await _job_department_options(user_id)
    await message.reply_text(_job_input_prompt(fname, df, fields[0], 1, len(fields), department=department, selection_options=selection_options))
    return True


async def _continue_job_input_session(user_id, text, message):
    state_raw = db_get_state(user_id, _job_state_key(""))
    if not state_raw:
        return False

    try:
        state = json.loads(state_raw)
    except Exception:
        db_delete_state(user_id, _job_state_key(""))
        return False

    fname = state.get("fname")
    if not fname:
        db_delete_state(user_id, _job_state_key(""))
        return False

    answer = text.strip()
    if answer.lower() in {"/cancel", "cancel", "huy", "hủy"}:
        db_delete_state(user_id, _job_state_key(""))
        await message.reply_text(f"🛑 Đã hủy nhập cho file `{fname}`.", parse_mode='Markdown')
        return True

    if answer.lower() in {"/skip", "skip", "-", "boqua", "bo qua", "bỏ qua"}:
        answer = ""

    if answer.lower() in {"/back", "back", "quaylai", "quay lại"}:
        current_index = int(state.get("index", 0))
        if current_index <= 0:
            await message.reply_text("ℹ️ Đây là bước đầu tiên, không thể quay lại.")
            return True
        current_index -= 1
        values = state.get("values", {})
        current_department = state.get("department") or values.get("phong")
        fields = _job_input_fields(fname, department=current_department)
        prev_field = fields[current_index]
        values.pop(prev_field, None)
        state["index"] = current_index
        state["values"] = values
        db_set_state(user_id, _job_state_key(""), json.dumps(state, ensure_ascii=False))
        df, _ = await _load_job_dataframe(user_id, fname, message, create_if_missing=True)
        await message.reply_text(f"↩️ Đã quay lại bước `{prev_field}`.", parse_mode='Markdown')
        selection_options = None
        if prev_field == "nguoi":
            selection_options = await _job_member_options(user_id, current_department)
        elif prev_field == "phong":
            selection_options = await _job_department_options(user_id)
        await message.reply_text(_job_input_prompt(fname, df, prev_field, current_index + 1, len(fields), department=current_department, selection_options=selection_options))
        return True

    df, _ = await _load_job_dataframe(user_id, fname, message, create_if_missing=True)
    if df is None:
        db_delete_state(user_id, _job_state_key(""))
        await message.reply_text(f"❌ Không tìm thấy file `{fname}`.", parse_mode='Markdown')
        return True

    index = int(state.get("index", 0))
    values = state.get("values", {})
    department = state.get("department") or values.get("phong")
    fields = _job_input_fields(fname, department=department)
    if index >= len(fields):
        db_delete_state(user_id, _job_state_key(""))
        return False

    field_name = fields[index]
    value = answer

    if job_file_type(fname) == "roster":
        parsed = parse_job_roster_payload("ten=" + answer, department=department)
        if parsed and parsed.get("ten"):
            value = parsed["ten"]
    else:
        if field_name == "han":
            parsed_date = parse_job_date_text(answer)
            if not parsed_date:
                await message.reply_text("❌ Ngày không hợp lệ, ví dụ `28/4` hoặc `am 10/3`.")
                await message.reply_text(_job_input_prompt(fname, df, field_name, index + 1, len(fields), department=department))
                return True
            value = parsed_date
        elif field_name == "phong":
            depts = await _job_department_options(user_id)
            if answer.isdigit():
                dept_index = int(answer) - 1
                if 0 <= dept_index < len(depts):
                    value = depts[dept_index]
        elif field_name == "diadiem":
            value = answer
        elif field_name == "nguoi":
            selection_options = await _job_member_options(user_id, department)
            value = _parse_multi_selection(answer, selection_options)

    values[field_name] = value
    state["index"] = index + 1
    state["values"] = values
    if field_name == "phong" and value:
        state["department"] = value

    if state["index"] < len(fields):
        db_set_state(user_id, _job_state_key(""), json.dumps(state, ensure_ascii=False))
        next_field = fields[state["index"]]
        await message.reply_text(f"✅ Đã nhận `{field_name}` = `{value}`.", parse_mode='Markdown')
        current_department = state.get("department") or values.get("phong")
        selection_options = None
        if next_field == "nguoi":
            selection_options = await _job_member_options(user_id, current_department)
        elif next_field == "phong":
            selection_options = await _job_department_options(user_id)
        await message.reply_text(_job_input_prompt(fname, df, next_field, state["index"] + 1, len(fields), department=current_department, selection_options=selection_options))
        return True

    if job_file_type(fname) == "roster":
        row_data = parse_job_roster_bulk_payload("ten=" + str(values.get("ten", "")), department=department)
        if not row_data:
            db_delete_state(user_id, _job_state_key(""))
            await message.reply_text("❌ Không thêm được nhân sự.")
            return True
        appended = df
        for item in row_data:
            appended = add_roster_entry(appended, item)
    else:
        row_data = dict(values)
        appended = add_task(df, row_data)

    sent_msg = await _save_dataframe_file(user_id, fname, appended, message, JOB_KIND, "📂 Đã lưu bản cập nhật của")
    db_delete_state(user_id, _job_state_key(""))
    await message.reply_text(f"✅ Đã nhận `{field_name}` = `{value}`.", parse_mode='Markdown')
    if job_file_type(fname) == "roster":
        await message.reply_text(format_roster_summary(appended), parse_mode='Markdown')
    else:
        await message.reply_text(_format_row_vertical(appended, len(appended)), parse_mode='Markdown')
    return True


async def handle_job_logic(user_id, fname, formula, message):
    formula = formula.strip()
    formula_lower = formula.lower()
    kind = job_file_type(fname)

    if formula_lower in {"cachnhap", "help"}:
        await message.reply_text(job_help_text(fname), parse_mode='Markdown')
        return True

    if formula_lower in {"nhap gui", "giao gui"}:
        return await _start_job_input_session(user_id, fname, message)

    def _parse_roster_command(text):
        parts = text.split()
        if not parts:
            return None, None, None
        actions = {"hien", "nhap", "xem", "xoa", "cachnhap", "help", "gui"}
        if parts[0].lower() in actions:
            return None, parts[0].lower(), " ".join(parts[1:]).strip()
        if len(parts) < 2:
            return parts[0].lower(), None, ""
        return parts[0].lower(), parts[1].lower(), " ".join(parts[2:]).strip()

    task_add_action = formula_lower.startswith("giao") or formula_lower.startswith("nhap") or formula_lower.startswith("them") or formula_lower.startswith("am ") or re.match(r"^\d{1,2}/\d{1,2}", formula_lower)
    roster_add_action = formula_lower.startswith("nhap") or formula_lower.startswith("them")

    file_id = db_get(user_id, fname)
    if not file_id and ((kind == "task" and task_add_action) or (kind == "roster" and roster_add_action)):
        df = job_default_df(fname)
    else:
        df, _ = await _load_job_dataframe(user_id, fname, message, create_if_missing=True)
    if df is None:
        await message.reply_text(f"❌ Không xử lý được file `{fname}`.", parse_mode='Markdown')
        return True

    if kind == "roster":
        department, action, payload = _parse_roster_command(formula)
        dept_df = df
        if department:
            dept_df = df[df["phong"].astype(str).str.strip().str.lower() == department]

        if action in {"nhap", "them"}:
            if not payload and not department:
                await message.reply_text(job_help_text(fname), parse_mode='Markdown')
                return True
            if payload.lower() == "gui":
                return await _start_job_input_session(user_id, fname, message, department=department)
            bulk_rows = parse_job_roster_bulk_payload(payload, department=department)
            if not bulk_rows:
                await message.reply_text("❌ Dữ liệu nhập nhân sự không hợp lệ.")
                return True
            appended = df
            for row_data in bulk_rows:
                if department and "phong" not in row_data:
                    row_data["phong"] = department
                appended = add_roster_entry(appended, row_data)
            await _save_dataframe_file(user_id, fname, appended, message, JOB_KIND, "📂 Đã lưu bản cập nhật của")
            await message.reply_text(format_roster_summary(appended, department=department), parse_mode='Markdown')
            return True

        if action == "hien":
            await message.reply_text(format_roster_summary(df, department=department), parse_mode='Markdown')
            return True

        if action == "xem":
            await message.reply_text(format_roster_summary(df, department=department), parse_mode='Markdown')
            return True

        if action == "xoa":
            parts = payload.split()
            if len(parts) != 1 or not parts[0].isdigit():
                await message.reply_text("❌ Dùng đúng dạng `xoa 1`.", parse_mode='Markdown')
                return True
            row_number = int(parts[0])
            dept_rows = dept_df.reset_index()
            if row_number < 1 or row_number > len(dept_rows):
                await message.reply_text("❌ Số mục không hợp lệ.", parse_mode='Markdown')
                return True
            row_idx = dept_rows.loc[row_number - 1, "index"]
            updated = df.drop(index=row_idx).reset_index(drop=True)
            await _save_dataframe_file(user_id, fname, updated, message, JOB_KIND, "📂 Đã lưu bản cập nhật của")
            await message.reply_text(format_roster_summary(updated, department=department), parse_mode='Markdown')
            return True

        if action is None and department:
            await message.reply_text(format_roster_summary(df, department=department), parse_mode='Markdown')
            return True

        await message.reply_text(job_help_text(fname), parse_mode='Markdown')
        return True

    # task file
    if task_add_action:
        payload = formula
        if formula_lower.startswith(("giao ", "nhap ", "them ")):
            payload = formula.split(" ", 1)[1].strip() if " " in formula else ""
        roster_df = await _load_job_roster_dataframe(user_id)
        if roster_df is None:
            roster_df = pd.DataFrame(columns=["phong"])
        known_depts = roster_departments(roster_df)
        data, _ = parse_job_task_payload(payload, known_depts=known_depts)
        if not data or not data.get("han") or not data.get("viec"):
            await message.reply_text("❌ Dùng dạng `jviec giao 28/4 Báo cáo ctv ds` hoặc `jviec giao am 10/3 Chạp mã nhà thờ lớn gd`.")
            return True
        appended = add_task(df, data)
        await _save_dataframe_file(user_id, fname, appended, message, JOB_KIND, "📂 Đã lưu bản cập nhật của")
        await message.reply_text(_format_row_vertical(appended, len(appended)), parse_mode='Markdown')
        return True

    if formula_lower == "hien":
        await message.reply_text(format_task_list(df, only_open=True), parse_mode='Markdown')
        return True

    if formula_lower == "xem":
        await message.reply_text(format_task_list(df, only_open=False), parse_mode='Markdown')
        return True

    if formula_lower.startswith("xem "):
        parts = formula.split()
        if len(parts) == 2 and parts[1].isdigit():
            detail = format_task_detail(df, int(parts[1]))
            if not detail:
                await message.reply_text("❌ Số việc không hợp lệ.", parse_mode='Markdown')
                return True
            await message.reply_text(detail, parse_mode='Markdown')
            return True
        await message.reply_text("❌ Dùng đúng dạng `xem 1`.", parse_mode='Markdown')
        return True

    if formula_lower.startswith("xong "):
        parts = formula.split()
        if len(parts) != 2 or not parts[1].isdigit():
            await message.reply_text("❌ Dùng đúng dạng `xong 1`.", parse_mode='Markdown')
            return True
        updated, error = mark_task_done_visible(df, int(parts[1]), only_open=True)
        if error:
            await message.reply_text(error, parse_mode='Markdown')
            return True
        await _save_dataframe_file(user_id, fname, updated, message, JOB_KIND, "📂 Đã lưu bản cập nhật của")
        await message.reply_text(format_task_list(updated, only_open=True), parse_mode='Markdown')
        return True

    await message.reply_text(job_help_text(fname), parse_mode='Markdown')
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
                    "ℹ️ **Hướng dẫn tính năng**\n\n- Upload CSV để nạp file, ví dụ `bctk.csv`.\n- CSV dùng lệnh: `tên_file hien`, `tên_file hien muc`, `tên_file cachnhap`, `tên_file nhap 1=1 2=1 3=15,5 4=Sương nộp` hoặc `tên_file nhap 1 1 15,5 Sương nộp`, `tên_file nhap gui`, `tên_file tim ...`, `tên_file xem ...`, `tên_file xoa`.\n- Dùng `/list` để xem danh sách file CSV, `/listmd` để xem danh sách file Markdown, `/listj` để xem file việc.\n- Ánh xạ số nhập: `1=muc`, `2=thuchi`, `3=sotien`, `4=noidung`.\n- Với file có cột `muc`, `thuchi`, `sotien`, ba trường này là bắt buộc khi `nhap`.\n- Dạng ngắn của `nhap` sẽ đi theo thứ tự cột thật của file, ví dụ `muc thuchi sotien noidung`.\n- Khi `nhap gui`, bạn có thể gõ `/back` để quay lại bước trước và sửa giá trị.\n- File việc dùng tiền tố `j`, ví dụ `jviec` và `jphong`.\n- `jviec` là nhánh giao việc: `jviec giao 28/4 Báo cáo ctv ds`, `jviec giao am 10/3 Chạp mã nhà thờ lớn gd`, `jviec hien`, `jviec xem 1`, `jviec xong 1`.\n- Ở bước `nguoi` của `jviec nhap gui`, bot sẽ hiện danh sách tên từ `jphong` của phòng đó và cho nhập nhiều số như `1,2`.\n- `jphong` là sổ tên chung theo phòng: `jphong ds hien`, `jphong ds nhap ld ngamy congtin`, `jphong ds nhap ten=ld,ngamy,congtin`.\n- `ld` chỉ là một tên bình thường trong sổ, không phải vai trò riêng.\n- Markdown dùng tên có chữ `md` trong tên, ví dụ `mdquytrinh.md` hoặc `luatmd.doc.md`.\n- Markdown dùng `tên_file hien` hoặc `tên_file hien 1` để xem mục lục, ví dụ `mdphongtuc hien` sẽ hiện các chủ đề lớn; `tên_file xem 1 1` hoặc `tên_file xem 1 1 1` để xem toàn bộ chi tiết của nhánh đó, `tên_file xoa 2` để xóa mục theo số thứ tự, `tên_file them file.md` để gộp file.\n- Lịch âm dương dùng `callicham 10/3/2026` hoặc `callicham am 10/3/2026`.\n- Quản lý file: `/list`, `/listmd`, `/listj`, `/del <tên_file>`.\n\nVí dụ: `bctk tim 5~'hoacuong' and 1==2020`",
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

            if text.lower() == "/listj":
                files = db_list_by_kind(user_id, JOB_KIND)
                text_out = _format_file_list("📋 **Danh sách file việc của bạn:**", files, "📭 Bạn chưa lưu file việc nào.")
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
                    job_state_raw = db_get_state(user_id, _job_state_key(""))
                    if job_state_raw:
                        try:
                            state = json.loads(job_state_raw)
                            fname = state.get("fname", "")
                        except Exception:
                            fname = ""
                        db_delete_state(user_id, _job_state_key(""))
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
                if await _continue_job_input_session(user_id, text, message):
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

                job_fname, job_formula = _normalize_job_command(text)
                if job_fname:
                    if await handle_job_logic(user_id, job_fname, job_formula, message):
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
            if message.document and message.document.file_name.lower().endswith('.csv') and is_job_name(message.document.file_name.lower().replace(".csv", "")):
                doc = message.document
                fname = doc.file_name.lower().replace(".csv", "")
                db_set(user_id, fname, doc.file_id)
                db_set_kind(user_id, fname, JOB_KIND)
                await message.reply_text(f"🔄 Đã ghi nhớ file việc: `{fname}`", parse_mode='Markdown')
                file = await bot.get_file(doc.file_id)
                content = requests.get(file.file_path).content.decode('utf-8')
                df = pd.read_csv(io.StringIO(content), engine='python')
                await message.reply_text(format_task_list(df, only_open=False), parse_mode='Markdown')
                return {"status": "ok"}

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
