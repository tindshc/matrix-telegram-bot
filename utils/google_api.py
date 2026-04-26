import os
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
import gspread

# Scopes for Google Sheets and Drive
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def get_google_credentials():
    """
    Retrieves Google credentials from environment variables or a local file.
    On Vercel, it's best to use environment variables.
    """
    # 1. Try to get from individual environment variables (Vercel-friendly)
    # The user would provide GOOGLE_SERVICE_ACCOUNT_JSON as a string
    creds_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    
    if creds_json:
        try:
            info = json.loads(creds_json)
            return service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
        except Exception as e:
            print(f"Error parsing GOOGLE_SERVICE_ACCOUNT_JSON: {e}")

    # 2. Try to look for service_account.json in the current directory
    local_path = "service_account.json"
    if os.path.exists(local_path):
        return service_account.Credentials.from_service_account_file(local_path, scopes=SCOPES)

    return None

def get_sheets_client():
    creds = get_google_credentials()
    if not creds:
        return None
    return gspread.authorize(creds)

def get_drive_service():
    creds = get_google_credentials()
    if not creds:
        return None
    return build("drive", "v3", credentials=creds)
