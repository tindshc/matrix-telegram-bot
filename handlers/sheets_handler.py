import pandas as pd
from utils.google_api import get_sheets_client

def append_to_sheet(sheet_id, worksheet_name, data_dict):
    """
    Appends a single row of data to a Google Sheet worksheet.
    data_dict: Dictionary where keys are column names and values are the data.
    """
    client = get_sheets_client()
    if not client:
        return None, "❌ Chưa cấu hình Google Service Account."

    try:
        sh = client.open_by_key(sheet_id)
        try:
            wks = sh.worksheet(worksheet_name)
        except gspread.WorksheetNotFound:
            # If worksheet doesn't exist, create it with headers from data_dict
            wks = sh.add_worksheet(title=worksheet_name, rows="100", cols="20")
            wks.append_row(list(data_dict.keys()))
        
        # Get headers to ensure alignment
        headers = wks.row_values(1)
        if not headers:
            headers = list(data_dict.keys())
            wks.append_row(headers)
            
        # Prepare row values based on headers
        row_values = []
        for header in headers:
            row_values.append(data_dict.get(header, ""))
            
        wks.append_row(row_values)
        return True, "✅ Đã lưu vào Google Sheets."
    except Exception as e:
        return None, f"❌ Lỗi Sheets: {str(e)}"

def get_sheet_as_df(sheet_id, worksheet_name):
    """Retrieves a worksheet as a Pandas DataFrame."""
    client = get_sheets_client()
    if not client:
        return None
    
    try:
        sh = client.open_by_key(sheet_id)
        wks = sh.worksheet(worksheet_name)
        data = wks.get_all_records()
        return pd.DataFrame(data)
    except Exception:
        return None
