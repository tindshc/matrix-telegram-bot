import io
import re
from datetime import datetime

import pandas as pd

from utils.calendar import SolarAndLunar
from utils.matrix import _format_row_vertical

TASK_COLUMNS = ["id", "han", "viec", "phong", "diadiem", "nguoi", "trangthai", "ghichu"]
ROSTER_COLUMNS = ["id", "phong", "vai_tro", "ten"]
DEFAULT_ROLES = ["lđ", "tin"]
JOB_KIND = "job"


def is_job_name(name: str) -> bool:
    return str(name).lower().startswith("j")


def job_file_type(fname: str) -> str:
    return "roster" if str(fname).lower().startswith("jphong") else "task"


def job_default_df(fname: str):
    columns = ROSTER_COLUMNS if job_file_type(fname) == "roster" else TASK_COLUMNS
    return pd.DataFrame(columns=columns)


def ensure_job_schema(df, fname: str):
    columns = ROSTER_COLUMNS if job_file_type(fname) == "roster" else TASK_COLUMNS
    work_df = df.copy()
    for column in columns:
        if column not in work_df.columns:
            work_df[column] = ""
    return work_df[columns]


def _auto_increment_id(df):
    if "id" not in df.columns:
        return ""
    ids = pd.to_numeric(df["id"], errors="coerce")
    if ids.dropna().empty:
        return 1
    return int(ids.max()) + 1


def _current_year():
    return datetime.now().year


def _parse_date_token(token: str, lunar: bool = False):
    token = str(token).strip()
    match = re.match(r"^(\d{1,2})/(\d{1,2})(?:/(\d{4}))?$", token)
    if not match:
        return None

    day = int(match.group(1))
    month = int(match.group(2))
    year = int(match.group(3) or _current_year())

    if lunar:
        s_day, s_month, s_year = SolarAndLunar.convertLunar2Solar(day, month, year, 0)
        return f"{s_day:02d}/{s_month:02d}/{s_year:04d}"

    datetime(year, month, day)
    return f"{day:02d}/{month:02d}/{year:04d}"


def parse_job_date_text(text: str):
    raw = str(text).strip()
    if not raw:
        return None

    lunar = False
    if raw.lower().startswith("am "):
        lunar = True
        raw = raw[3:].strip()

    return _parse_date_token(raw, lunar=lunar)


def parse_job_task_payload(payload: str, known_depts=None):
    text = str(payload).strip()
    known_depts = {str(x).lower() for x in (known_depts or []) if str(x).strip()}
    lunar = False

    if text.lower().startswith("am "):
        lunar = True
        text = text[3:].strip()

    tokens = text.split()
    if not tokens:
        return None, None

    date_value = None
    date_tokens = 0
    if tokens:
        candidate = tokens[0]
        if candidate.lower() == "am" and len(tokens) >= 2:
            lunar = True
            candidate = tokens[1]
            date_tokens = 2
        else:
            date_tokens = 1

        date_value = _parse_date_token(candidate, lunar=lunar)
        if date_value is None and len(tokens) >= 2 and tokens[0].lower() == "am":
            date_value = _parse_date_token(tokens[1], lunar=True)

    if date_value is None:
        return None, None

    remainder = tokens[date_tokens:]
    if not remainder:
        return {"han": date_value}, ""

    phong = ""
    if remainder[-1].lower() in known_depts:
        phong = remainder[-1]
        remainder = remainder[:-1]

    viec = " ".join(remainder).strip()
    data = {"han": date_value, "viec": viec}
    if phong:
        data["phong"] = phong
    return data, viec


def parse_job_roster_payload(payload: str, roles=None, department=None):
    text = str(payload).strip()
    roles = roles or DEFAULT_ROLES
    if not text:
        return None

    matches = list(re.finditer(r"(\w+)\s*=", text))
    named = {}
    for i, match in enumerate(matches):
        key = match.group(1).strip().lower()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        value = text[start:end].strip()
        if value.startswith("'") and value.endswith("'"):
            value = value[1:-1]
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        named[key] = value

    if named:
        result = {}
        if department:
            result["phong"] = department
        elif "phong" in named:
            result["phong"] = named.get("phong", "").strip()
        role_value = named.get("vai_tro") or named.get("role") or named.get("vt")
        name_value = named.get("ten") or named.get("name")
        if role_value:
            result["vai_tro"] = _normalize_role(role_value, roles)
        if name_value:
            result["ten"] = name_value
        return result if result else None

    tokens = text.split(maxsplit=1)
    if not tokens:
        return None

    first = tokens[0].strip()
    rest = tokens[1].strip() if len(tokens) > 1 else ""
    if first.isdigit():
        index = int(first) - 1
        if 0 <= index < len(roles):
            first = roles[index]
    elif first.lower() in {"1", "lđ", "ld"}:
        first = "lđ"
    elif first.lower() in {"2", "tin"}:
        first = "tin"

    if rest:
        result = {"vai_tro": first, "ten": rest}
        if department:
            result["phong"] = department
        return result

    result = {"ten": first}
    if department:
        result["phong"] = department
    return result


def _normalize_role(value: str, roles=None):
    roles = roles or DEFAULT_ROLES
    raw = str(value).strip().lower()
    if raw.isdigit():
        index = int(raw) - 1
        if 0 <= index < len(roles):
            return roles[index]
    if raw in {"1", "lđ", "ld"}:
        return "lđ"
    if raw in {"2", "tin"}:
        return "tin"
    return value.strip()


def _append_row(df, row_data):
    work_df = ensure_job_schema(df, "jviec" if "han" in df.columns else "jphong")
    new_row = {col: "" for col in work_df.columns}
    if "id" in work_df.columns:
        new_row["id"] = _auto_increment_id(work_df)
    for key, value in row_data.items():
        if key in new_row:
            new_row[key] = value
    return pd.concat([work_df, pd.DataFrame([new_row])], ignore_index=True)


def job_help_text(fname: str):
    if job_file_type(fname) == "roster":
        return "\n".join(
            [
                "📝 **Cách dùng jphong**:",
                "- `jphong ds hien` để xem danh sách vai trò / nhân sự của phòng ds.",
                "- `jphong gd hien` để xem danh sách của phòng gd.",
                "- `jphong ds nhap 1 Nguyễn Văn A` hoặc `jphong ds nhap vai_tro=lđ ten=Nguyễn Văn A` để thêm người.",
                "- `jphong ds nhap gui` để bot hỏi lần lượt vai trò rồi tên.",
                "- `/back` để quay lại bước trước, `/cancel` để hủy.",
                "- Dữ liệu được lưu chung trong một file `jphong`, phân biệt theo cột `phong`.",
                "- Mặc định có 2 vai trò: `lđ` và `tin`.",
            ]
        )

    return "\n".join(
        [
            "📝 **Cách dùng jviec**:",
            "- `jviec giao 28/4 Báo cáo ctv ds` để giao việc; nếu bỏ năm thì bot tự hiểu là năm hiện tại.",
            "- `jviec giao am 10/3 Chạp mã nhà thờ lớn gd` để nhập ngày âm, bot sẽ đổi sang ngày dương.",
            "- `jviec hien` để xem các việc đang chờ.",
            "- `jviec xem` để xem toàn bộ, `jviec xem 1` để xem chi tiết việc số 1.",
            "- `jviec xong 1` để đánh dấu xong.",
            "- `jviec nhap gui` có cột `diadiem` trước `nguoi`; nếu không có địa điểm thì gõ `-` hoặc `/skip`.",
            "- `jviec nhap gui` để bot hỏi từng trường; ở bước `nguoi`, bot sẽ hiện danh sách từ `jphong` của phòng đó và cho chọn nhiều số như `1,2`.",
            "- `/back` để quay lại bước trước, `/cancel` để hủy.",
            "- File `jviec` lưu theo CSV riêng, tách khỏi CSV thường và Markdown.",
        ]
    )


def _task_row_display(row, row_number):
    han = str(row.get("han", "")).strip()
    viec = str(row.get("viec", "")).strip()
    phong = str(row.get("phong", "")).strip()
    diadiem = str(row.get("diadiem", "")).strip()
    nguoi = str(row.get("nguoi", "")).strip()
    trangthai = str(row.get("trangthai", "")).strip() or "chờ"
    ghichu = str(row.get("ghichu", "")).strip()

    label = f"{row_number}. {viec}"
    parts = []
    if han:
        parts.append(han)
    if phong:
        parts.append(phong)
    if diadiem:
        parts.append(diadiem)
    if nguoi:
        parts.append(nguoi)
    if trangthai:
        parts.append(trangthai)
    if parts:
        label += f" ({' | '.join(parts)})"
    if ghichu:
        label += f"\n  - {ghichu}"
    return label


def format_task_list(df, only_open=True):
    work_df = ensure_job_schema(df, "jviec")
    if only_open and "trangthai" in work_df.columns:
        mask = work_df["trangthai"].astype(str).str.lower().ne("done")
        work_df = work_df[mask]

    if work_df.empty:
        return "📭 Chưa có việc nào."

    lines = ["📋 **Danh sách việc**:"]
    for idx, (_, row) in enumerate(work_df.iterrows(), 1):
        lines.append(_task_row_display(row, idx))
    return "\n".join(lines)


def format_task_detail(df, row_number):
    work_df = ensure_job_schema(df, "jviec")
    if row_number < 1 or row_number > len(work_df):
        return None
    return _format_row_vertical(work_df, row_number)


def _filter_roster_df(df, department=None):
    work_df = ensure_job_schema(df, "jphong")
    if department:
        dept = str(department).strip().lower()
        work_df = work_df[work_df["phong"].astype(str).str.strip().str.lower() == dept]
    return work_df


def _roster_departments(df):
    work_df = ensure_job_schema(df, "jphong")
    values = []
    seen = set()
    for item in work_df["phong"].tolist():
        text = str(item).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        values.append(text)
    return values or ["ds", "gd"]


def mark_task_done(df, row_number):
    work_df = ensure_job_schema(df, "jviec")
    if row_number < 1 or row_number > len(work_df):
        return None, "❌ Số việc không hợp lệ."
    work_df.loc[row_number - 1, "trangthai"] = "done"
    if "ghichu" in work_df.columns:
        note = str(work_df.loc[row_number - 1, "ghichu"]).strip()
        stamp = datetime.now().strftime("%d/%m/%Y")
        work_df.loc[row_number - 1, "ghichu"] = f"{note} | xong {stamp}".strip(" |")
    return work_df, None


def mark_task_done_visible(df, visible_number, only_open=True):
    work_df = ensure_job_schema(df, "jviec")
    if only_open and "trangthai" in work_df.columns:
        open_mask = work_df["trangthai"].astype(str).str.lower().ne("done")
        visible_indices = list(work_df[open_mask].index)
    else:
        visible_indices = list(work_df.index)

    if visible_number < 1 or visible_number > len(visible_indices):
        return None, "❌ Số việc không hợp lệ."

    row_idx = visible_indices[visible_number - 1]
    work_df.loc[row_idx, "trangthai"] = "done"
    if "ghichu" in work_df.columns:
        note = str(work_df.loc[row_idx, "ghichu"]).strip()
        stamp = datetime.now().strftime("%d/%m/%Y")
        work_df.loc[row_idx, "ghichu"] = f"{note} | xong {stamp}".strip(" |")
    return work_df, None


def add_task(df, data):
    work_df = ensure_job_schema(df, "jviec")
    row = {col: "" for col in work_df.columns}
    if "id" in row:
        row["id"] = _auto_increment_id(work_df)
    row["han"] = data.get("han", "")
    row["viec"] = data.get("viec", "")
    row["phong"] = data.get("phong", "")
    row["diadiem"] = data.get("diadiem", "")
    row["nguoi"] = data.get("nguoi", "")
    row["trangthai"] = data.get("trangthai", "chờ")
    row["ghichu"] = data.get("ghichu", "")
    return pd.concat([work_df, pd.DataFrame([row])], ignore_index=True)


def format_roster_summary(df, department=None):
    work_df = _filter_roster_df(df, department)
    if work_df.empty:
        if department:
            return f"📭 Phòng `{department}` chưa có nhân sự nào."
        return "📭 Chưa có nhân sự nào."

    lines = ["📋 **Danh sách nhân sự**:"]
    if department:
        departments = [department]
    else:
        departments = _roster_departments(work_df)

    for dept in departments:
        dept_df = _filter_roster_df(work_df, dept)
        if dept_df.empty:
            continue
        lines.append("")
        lines.append(f"**Phòng {dept}**")
        roles = DEFAULT_ROLES[:]
        extra_roles = [r for r in _unique_roles(dept_df["vai_tro"]) if r not in roles]
        roles.extend(extra_roles)
        for idx, role in enumerate(roles, 1):
            role_names = _names_for_role(dept_df, role)
            if not role_names:
                continue
            lines.append(f"{idx}. {role}")
            for name_idx, name in enumerate(role_names, 1):
                lines.append(f"  - {name_idx}. {name}")
    return "\n".join(lines)


def _unique_roles(series):
    values = []
    seen = set()
    for item in series.tolist():
        text = str(item).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        values.append(text)
    return values


def _names_for_role(df, role):
    subset = df[df["vai_tro"].astype(str).str.strip().str.lower() == str(role).strip().lower()]
    return [str(v).strip() for v in subset["ten"].tolist() if str(v).strip()]


def add_roster_entry(df, data):
    work_df = ensure_job_schema(df, "jphong")
    row = {col: "" for col in work_df.columns}
    if "id" in row:
        row["id"] = _auto_increment_id(work_df)
    row["phong"] = data.get("phong", "")
    row["vai_tro"] = data.get("vai_tro", "")
    row["ten"] = data.get("ten", "")
    return pd.concat([work_df, pd.DataFrame([row])], ignore_index=True)


def roster_roles(df):
    work_df = ensure_job_schema(df, "jphong")
    roles = _unique_roles(work_df["vai_tro"]) if not work_df.empty else []
    merged = []
    for role in DEFAULT_ROLES + roles:
        if role and role not in merged:
            merged.append(role)
    return merged


def roster_roles_for_department(df, department=None):
    return roster_roles(_filter_roster_df(df, department))


def roster_departments(df):
    return _roster_departments(df)
