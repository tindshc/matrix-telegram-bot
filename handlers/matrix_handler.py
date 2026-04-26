from utils.matrix import process_matrix
from handlers.sheets_handler import get_sheet_as_df, append_to_sheet

async def handle_matrix_command(user_id, sheet_id, worksheet_name, formula):
    """
    Adapter to run the existing matrix logic on data from Google Sheets.
    """
    df = get_sheet_as_df(sheet_id, worksheet_name)
    if df is None:
        return "❌ Không thể lấy dữ liệu từ Google Sheets."
    
    csv_content = df.to_csv(index=False)
    result_text, updated_csv = process_matrix(csv_content, formula)
    
    # If matrix operation updated the data (e.g. 'tinh' or 'xoa')
    # We would need a way to push back to Sheets. 
    # For now, let's just return the result.
    
    return result_text
