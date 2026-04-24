import pandas as pd
import io
import re


def _format_column_listing(df):
    """Return a numbered list of columns for user-facing display."""
    rows = [{"#": idx + 1, "Cột": col} for idx, col in enumerate(df.columns)]
    return pd.DataFrame(rows).to_markdown(index=False)


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

def get_csv_info(csv_content):
    """Returns column names and basic info of the CSV"""
    try:
        df = pd.read_csv(io.StringIO(csv_content))
        cols = ", ".join([f"`{c}`" for c in df.columns])
        return f"Đã nhận file CSV.\nCác cột: {cols}\nSố dòng: {len(df)}\nHãy nhập công thức để tính toán."
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
            text += "\n\nDùng số thứ tự này trong lệnh `tim`, ví dụ: `tim 3=='HOACUONG'`."
            return text, None

        # 1. Handle Filter/Query
        if formula_lower.startswith("tim "):
            condition = formula[4:].strip()
            condition = _normalize_single_equals(condition)
            condition = _resolve_numeric_column_refs(condition, list(df.columns))
            filtered_df = df.query(condition, engine="python")
            if filtered_df.empty:
                return "❌ Không có dòng nào khớp với điều kiện tìm kiếm.", None
            return f"🔍 **Kết quả tìm kiếm**:\n\n{filtered_df.to_markdown()}", None

        if formula_lower.startswith("filter "):
            condition = formula[7:].strip()
            # Standardize equality
            condition = _normalize_single_equals(condition)
            
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
