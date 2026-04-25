import pandas as pd
import io
import re


def _format_column_listing(df):
    """Return a numbered list of columns for user-facing display."""
    rows = [{"#": idx + 1, "Cột": col} for idx, col in enumerate(df.columns)]
    return pd.DataFrame(rows).to_markdown(index=False)


def _resolve_column_name(columns, ref):
    """Resolve a column by 1-based index or case-insensitive name."""
    ref = str(ref).strip()
    if ref.isdigit():
        index = int(ref) - 1
        if 0 <= index < len(columns):
            return columns[index]
        return None

    ref_lower = ref.casefold()
    for col in columns:
        if str(col).casefold() == ref_lower:
            return col
    return None


def _unique_nonempty_values(series):
    values = []
    seen = set()
    for value in series.tolist():
        if pd.isna(value):
            continue
        text = str(value).strip()
        if not text:
            continue
        if text in seen:
            continue
        seen.add(text)
        values.append(text)
    return values


def _format_unique_value_listing(df, column_name):
    values = _unique_nonempty_values(df[column_name])
    if not values:
        return f"📭 Cột `{column_name}` chưa có giá trị nào."

    lines = [f"📋 **Giá trị duy nhất của `{column_name}`**:"]
    for idx, value in enumerate(values, 1):
        lines.append(f"{idx}. {value}")
    return "\n".join(lines)


def _has_transaction_schema(df):
    lower_map = {str(col).casefold(): col for col in df.columns}
    return all(key in lower_map for key in ("muc", "thuchi", "sotien"))


def _parse_named_arguments(text):
    body = text.strip()
    if not body:
        return {}

    matches = list(re.finditer(r"(\w+)\s*=", body))
    if not matches:
        return {}

    parsed = {}
    for i, match in enumerate(matches):
        key = match.group(1).strip().lower()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        value = body[start:end].strip()
        if value.startswith("'") and value.endswith("'"):
            value = value[1:-1]
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        parsed[key] = value
    return parsed


def _parse_amount(text):
    raw = str(text).strip()
    if not raw:
        return None
    normalized = raw.replace(" ", "").replace(",", ".")
    try:
        value = float(normalized)
    except ValueError:
        return None
    if value.is_integer():
        return int(value)
    return round(value, 2)


def _auto_increment_id(df):
    if "id" not in df.columns:
        return None
    ids = pd.to_numeric(df["id"], errors="coerce")
    if ids.dropna().empty:
        return 1
    return int(ids.max()) + 1


def _transaction_summary(df, selected_muc=None, selected_thuchi=None):
    lower_map = {str(col).casefold(): col for col in df.columns}
    muc_col = lower_map.get("muc")
    thuchi_col = lower_map.get("thuchi")
    sotien_col = lower_map.get("sotien")
    noidung_col = lower_map.get("noidung")

    work_df = df.copy()
    work_df[muc_col] = work_df[muc_col].astype(str)
    work_df[thuchi_col] = work_df[thuchi_col].astype(str)
    work_df[sotien_col] = pd.to_numeric(work_df[sotien_col], errors="coerce").fillna(0)

    if selected_muc is not None:
        work_df = work_df[work_df[muc_col] == str(selected_muc)]

    if work_df.empty:
        return "❌ Không có dòng nào khớp với mục đã chọn.", None

    lines = []
    if selected_muc is not None:
        lines.append(f"📌 **Mục**: {selected_muc}")

    if selected_thuchi is not None:
        lines.append(f"📌 **Loại đang xem**: {selected_thuchi}")

    type_values = _unique_nonempty_values(work_df[thuchi_col])
    if selected_thuchi is not None and selected_thuchi in type_values:
        type_values = [selected_thuchi]

    for type_value in type_values:
        type_df = work_df[work_df[thuchi_col] == type_value]
        if type_df.empty:
            continue
        lines.append("")
        lines.append(f"**{type_value}**")
        for idx, row in type_df.iterrows():
            amount = row[sotien_col]
            detail = ""
            if noidung_col in work_df.columns:
                detail = str(row.get(noidung_col, "")).strip()
            if detail:
                lines.append(f"- {amount}: {detail}")
            else:
                lines.append(f"- {amount}")
        lines.append(f"Tổng {type_value.lower()}: {type_df[sotien_col].sum():g}")

    lines.append("")
    lines.append("**Tổng theo loại trong mục này**")
    for type_value in _unique_nonempty_values(work_df[thuchi_col]):
        type_df = work_df[work_df[thuchi_col] == type_value]
        lines.append(f"- {type_value}: {type_df[sotien_col].sum():g}")

    return "\n".join(lines), None


def _append_row(df, row_data):
    new_row = {col: "" for col in df.columns}
    if "id" in df.columns:
        new_row["id"] = _auto_increment_id(df)

    for key, value in row_data.items():
        if str(key).strip().lower() == "id":
            continue
        col_name = _resolve_column_name(df.columns, key)
        if col_name is None:
            continue
        if str(col_name).casefold() == "sotien":
            parsed_amount = _parse_amount(value)
            if parsed_amount is None:
                return None, f"❌ Cột `sotien` phải là số, ví dụ `15` hoặc `15,5`."
            new_row[col_name] = parsed_amount
        else:
            new_row[col_name] = value

    for col in df.columns:
        if col not in new_row:
            new_row[col] = ""

    appended = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    return appended, None


def _resolve_numeric_column_refs(condition, columns):
    """
    Replace references like `3=='X'` with the actual column name.

    The bot uses 1-based indexes in the `hien` output, so the same numbering
    is accepted here for `tim`.
    """
    def replace_match(match):
        index = int(match.group(1)) - 1
        op = match.group(2)
        if index < 0 or index >= len(columns):
            return match.group(0)
        col_name = columns[index]
        return f"`{col_name}` {op}"

    pattern = re.compile(r'(?<![\w`"\'\]])\b(\d+)\b\s*(==|!=|>=|<=|=|>|<)')
    return pattern.sub(replace_match, condition)


def _normalize_single_equals(condition):
    """Convert single `=` to `==` without touching `>=`, `<=`, `!=`, or `==`."""
    return re.sub(r'(?<![<>=!])=(?![=])', '==', condition)


def _escape_markdown(text):
    """Escape Telegram Markdown special characters in plain text values."""
    text = str(text)
    for ch in ('\\', '_', '*', '`', '[', ']', '(', ')'):
        text = text.replace(ch, f'\\{ch}')
    return text


def _format_row_vertical(df, row_number):
    """Format one row as a vertical key/value list for Telegram."""
    if row_number < 1 or row_number > len(df):
        return None

    row = df.iloc[row_number - 1]
    lines = [f"📄 **Dòng {row_number}**"]
    for col in df.columns:
        value = row[col]
        if pd.isna(value):
            value = ""
        lines.append(f"- **{_escape_markdown(col)}**: {_escape_markdown(value)}")
    return "\n".join(lines)


def _extract_numeric_column_contains(condition, columns):
    """
    Parse shorthand like `5~'dong yên'`.

    Returns (column_name, needle) or (None, None) if the format doesn't match.
    """
    match = re.match(r"^\s*(\d+)\s*~\s*(.+?)\s*$", condition)
    if not match:
        return None, None

    index = int(match.group(1)) - 1
    if index < 0 or index >= len(columns):
        return None, None

    needle = match.group(2).strip()
    if (needle.startswith("'") and needle.endswith("'")) or (needle.startswith('"') and needle.endswith('"')):
        needle = needle[1:-1]

    return columns[index], needle


def _evaluate_atomic_filter(df, clause, columns):
    """
    Evaluate one atomic filter clause and return a boolean Series.

    Supports:
    - `5~'abc'` for contains, case-insensitive
    - normal pandas query expressions such as `3=='HOACUONG'` or `1==2020`
    """
    column_name, needle = _extract_numeric_column_contains(clause, columns)
    if column_name:
        series = df[column_name].astype(str)
        return series.str.contains(re.escape(needle), case=False, na=False, regex=False)

    condition = _normalize_single_equals(clause)
    condition = _resolve_numeric_column_refs(condition, columns)
    result = df.eval(condition, engine="python")
    if isinstance(result, bool):
        return pd.Series([result] * len(df), index=df.index)
    return result.fillna(False)


def _evaluate_timed_filter(df, condition, columns):
    """
    Evaluate a `tim` condition supporting `and` / `or` with `~` contains clauses.
    """
    or_parts = re.split(r"\s+or\s+", condition, flags=re.IGNORECASE)
    final_mask = None

    for or_part in or_parts:
        and_parts = re.split(r"\s+and\s+", or_part, flags=re.IGNORECASE)
        part_mask = None

        for clause in and_parts:
            clause = clause.strip()
            if not clause:
                continue
            mask = _evaluate_atomic_filter(df, clause, columns)
            part_mask = mask if part_mask is None else (part_mask & mask)

        if part_mask is None:
            continue
        final_mask = part_mask if final_mask is None else (final_mask | part_mask)

    if final_mask is None:
        return None
    return final_mask.fillna(False)

def get_csv_info(csv_content):
    """Returns column names and basic info of the CSV"""
    try:
        df = pd.read_csv(io.StringIO(csv_content))
        cols = ", ".join([f"`{c}`" for c in df.columns])
        return (
            f"Đã nhận file CSV.\nCác cột: {cols}\nSố dòng: {len(df)}\n"
            "Dùng `hien`, `hien <cột>`, `nhap`, `tim`, `xem`, `filter` hoặc công thức tính toán."
        )
    except Exception as e:
        return f"Lỗi đọc file: {str(e)}"

def process_matrix(csv_content, formula):
    """
    Processes a CSV with a given formula or filter.
    Returns: (message_text, updated_csv_content_if_any)
    """
    try:
        # Use low_memory=False and engine='python' for stability
        df = pd.read_csv(io.StringIO(csv_content), engine='python')
        formula = formula.strip()
        formula_lower = formula.lower()

        # 0. Show columns with numbering
        if formula_lower == "hien":
            text = "📋 **Danh sách cột**:\n\n" + _format_column_listing(df)
            text += "\n\nDùng số thứ tự này trong lệnh `tim`, ví dụ: `tim 5~'đồng yên'`."
            return text, None

        if formula_lower.startswith("hien "):
            column_ref = formula[5:].strip()
            column_name = _resolve_column_name(list(df.columns), column_ref)
            if not column_name:
                return "❌ Không tìm thấy cột cần hiện.", None
            return _format_unique_value_listing(df, column_name), None

        if formula_lower.startswith("nhap"):
            raw_args = formula[4:].strip()
            if not raw_args:
                lines = [
                    "📝 **Mẫu nhập mới**:",
                    "- `nhap muc=Quỹ cơ quan thuchi=Thu sotien=15,5 noidung=Sương nộp`",
                    "- `id` sẽ tự tăng nếu cột này có trong file.",
                    "- Nếu `muc` hoặc `thuchi` nhập giá trị mới thì nó sẽ được thêm như mục mới.",
                ]
                if "muc" in {str(c).casefold() for c in df.columns}:
                    lines.append("")
                    lines.append(_format_unique_value_listing(df, _resolve_column_name(list(df.columns), "muc")))
                if "thuchi" in {str(c).casefold() for c in df.columns}:
                    lines.append("")
                    lines.append(_format_unique_value_listing(df, _resolve_column_name(list(df.columns), "thuchi")))
                return "\n".join(lines), None

            row_data = _parse_named_arguments(raw_args)
            if not row_data:
                return "❌ Dùng đúng dạng `nhap muc=... thuchi=... sotien=... noidung=...`.", None

            appended, error = _append_row(df, row_data)
            if error:
                return error, None

            updated_csv = appended.to_csv(index=False)
            msg = f"✅ Đã thêm dòng mới vào file.\n\n{appended.tail(5).to_markdown(index=False)}"
            return msg, updated_csv

        if formula_lower.startswith("xem "):
            row_part = formula[4:].strip()
            parts = formula.split()

            if len(parts) == 3 and all(p.isdigit() for p in parts[1:]) and _has_transaction_schema(df):
                lower_map = {str(col).casefold(): col for col in df.columns}
                muc_col = lower_map["muc"]
                thuchi_col = lower_map["thuchi"]
                muc_values = _unique_nonempty_values(df[muc_col])
                thuchi_values = _unique_nonempty_values(df[thuchi_col])

                muc_index = int(parts[1]) - 1
                thuchi_index = int(parts[2]) - 1
                if muc_index < 0 or muc_index >= len(muc_values):
                    return "❌ Số mục không hợp lệ.", None
                if thuchi_index < 0 or thuchi_index >= len(thuchi_values):
                    return "❌ Số loại không hợp lệ.", None

                selected_muc = muc_values[muc_index]
                selected_thuchi = thuchi_values[thuchi_index]
                return _transaction_summary(df, selected_muc, selected_thuchi)

            if len(parts) == 2 and parts[1].isdigit() and _has_transaction_schema(df):
                lower_map = {str(col).casefold(): col for col in df.columns}
                muc_col = lower_map["muc"]
                muc_values = _unique_nonempty_values(df[muc_col])
                muc_index = int(parts[1]) - 1
                if muc_index < 0 or muc_index >= len(muc_values):
                    return "❌ Số mục không hợp lệ.", None
                return _transaction_summary(df, muc_values[muc_index], None)

            if not row_part.isdigit():
                return "❌ Dùng đúng dạng `xem 1` để xem dòng theo số thứ tự.", None

            rendered = _format_row_vertical(df, int(row_part))
            if not rendered:
                return "❌ Số dòng không hợp lệ.", None
            return rendered, None

        # 1. Handle Filter/Query
        if formula_lower.startswith("tim "):
            condition = formula[4:].strip()
            mask = _evaluate_timed_filter(df, condition, list(df.columns))
            if mask is None:
                return "❌ Không có điều kiện hợp lệ trong lệnh tìm kiếm.", None
            filtered_df = df[mask]
            if filtered_df.empty:
                return "❌ Không có dòng nào khớp với điều kiện tìm kiếm.", None
            return f"🔍 **Kết quả tìm kiếm**:\n\n{filtered_df.to_markdown()}", None

        if formula_lower.startswith("filter "):
            condition = formula[7:].strip()
            # Standardize equality
            condition = _normalize_single_equals(condition)
            condition = _resolve_numeric_column_refs(condition, list(df.columns))
            
            # Use engine='python' for more robust querying
            filtered_df = df.query(condition, engine='python')
            if filtered_df.empty:
                return "❌ Không có dòng nào khớp với điều kiện lọc.", None
            return f"🔍 **Kết quả lọc**:\n\n{filtered_df.to_markdown()}", None

        # 2. Handle Calculation
        updated_csv = None
        if '=' in formula:
            target_col, expr = formula.split('=', 1)
            target_col = target_col.strip()
            expr = expr.strip()
            
            # Use engine='python' for calculation as well
            df[target_col] = df.eval(expr, engine='python')
            
            if pd.api.types.is_numeric_dtype(df[target_col]):
                df[target_col] = df[target_col].round(2)
            
            updated_csv = df.to_csv(index=False)
            msg = f"✅ Đã tính toán và cập nhật cột `{target_col}`.\n\n{df.head(10).to_markdown()}"
            return msg, updated_csv
        else:
            # Just evaluate an expression
            result = df.eval(formula, engine='python')
            return f"📊 **Kết quả**:\n\n{result.to_string()}", None

    except Exception as e:
        # Provide more context in error
        return f"❌ Lỗi: {str(e)}", None
