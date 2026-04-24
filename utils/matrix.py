import pandas as pd
import io

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
        df = pd.read_csv(io.StringIO(csv_content))
        
        # 1. Handle Filter/Query
        if formula.lower().startswith("filter "):
            condition = formula[7:].strip()
            if '==' not in condition and '=' in condition:
                condition = condition.replace('=', '==')
            
            filtered_df = df.query(condition)
            if filtered_df.empty:
                return "❌ Không có dòng nào khớp với điều kiện lọc.", None
            return f"🔍 **Kết quả lọc**:\n\n{filtered_df.to_markdown()}", None

        # 2. Handle Calculation
        updated_csv = None
        if '=' in formula:
            target_col, expr = formula.split('=', 1)
            target_col = target_col.strip()
            expr = expr.strip()
            
            df[target_col] = df.eval(expr)
            
            if pd.api.types.is_numeric_dtype(df[target_col]):
                df[target_col] = df[target_col].round(2)
            
            updated_csv = df.to_csv(index=False)
            msg = f"✅ Đã tính toán và cập nhật cột `{target_col}`.\n\n{df.head(10).to_markdown()}"
            return msg, updated_csv
        else:
            result = df.eval(formula)
            return f"📊 **Kết quả**:\n\n{result.to_string()}", None

    except Exception as e:
        return f"❌ Lỗi: {str(e)}", None
