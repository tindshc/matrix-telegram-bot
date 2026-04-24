import pandas as pd
import io
import re

def process_matrix(csv_content, formula):
    """
    Processes a CSV with a given formula.
    Example formula: "cbr = sosinh * 1000 / dstb"
    """
    try:
        # Load CSV
        df = pd.read_csv(io.StringIO(csv_content))
        
        # Clean formula: handle spaces and common math symbols
        # formula is expected to be like "new_col = col1 * col2"
        if '=' in formula:
            target_col, expr = formula.split('=', 1)
            target_col = target_col.strip()
            expr = expr.strip()
            
            # Use pandas eval for matrix-style calculation
            df[target_col] = df.eval(expr)
            
            # Round if numeric
            if pd.api.types.is_numeric_dtype(df[target_col]):
                df[target_col] = df[target_col].round(2)
        else:
            # Just evaluate the expression and return as a series/result
            result = df.eval(formula)
            return f"Kết quả:\n{result.to_string()}"

        # Return a summary or the first few rows
        return df.head(10).to_markdown()
    except Exception as e:
        return f"Lỗi tính toán: {str(e)}"

def get_csv_info(csv_content):
    """Returns column names and basic info of the CSV"""
    try:
        df = pd.read_csv(io.StringIO(csv_content))
        cols = ", ".join([f"`{c}`" for c in df.columns])
        return f"Đã nhận file CSV.\nCác cột: {cols}\nSố dòng: {len(df)}\nHãy nhập công thức để tính toán."
    except Exception as e:
        return f"Lỗi đọc file: {str(e)}"
