import pandas as pd
import io

def process_matrix(csv_content, formula):
    """
    Processes a CSV with a given formula or filter.
    Returns: (message_text, updated_csv_content_if_any)
    """
    try:
        df = pd.read_csv(io.StringIO(csv_content))
        
        # 1. Handle Filter/Query
        # Syntax: "filename filter condition"
        if formula.lower().startswith("filter "):
            condition = formula[7:].strip()
            # Handle equality if only one '=' is used
            if '==' not in condition and '=' in condition:
                condition = condition.replace('=', '==')
            
            filtered_df = df.query(condition)
            if filtered_df.empty:
                return "❌ Không có dòng nào khớp với điều kiện lọc.", None
            return f"🔍 **Kết quả lọc**:\n\n{filtered_df.to_markdown()}", None

        # 2. Handle Calculation
        # Syntax: "filename new_col = expr"
        updated_csv = None
        if '=' in formula:
            target_col, expr = formula.split('=', 1)
            target_col = target_col.strip()
            expr = expr.strip()
            
            df[target_col] = df.eval(expr)
            
            # Auto-round numeric
            if pd.api.types.is_numeric_dtype(df[target_col]):
                df[target_col] = df[target_col].round(2)
            
            # Prepare updated CSV content
            updated_csv = df.to_csv(index=False)
            msg = f"✅ Đã tính toán và cập nhật cột `{target_col}`.\n\n{df.head(10).to_markdown()}"
            return msg, updated_csv
        else:
            # Just evaluate an expression without saving
            result = df.eval(formula)
            return f"📊 **Kết quả**:\n\n{result.to_string()}", None

    except Exception as e:
        return f"❌ Lỗi: {str(e)}", None
