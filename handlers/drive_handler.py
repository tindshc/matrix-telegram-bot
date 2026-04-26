import io
from googleapiclient.http import MediaIoBaseUpload
from utils.google_api import get_drive_service

def save_markdown_to_drive(folder_id, filename, content):
    """
    Saves a markdown file to a specific Google Drive folder.
    """
    service = get_drive_service()
    if not service:
        return None, "❌ Chưa cấu hình Google Service Account."

    file_metadata = {
        'name': filename,
        'parents': [folder_id],
        'mimeType': 'text/markdown'
    }
    
    media = MediaIoBaseUpload(
        io.BytesIO(content.encode('utf-8')),
        mimetype='text/markdown',
        resumable=True
    )

    try:
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        return file.get('id'), "✅ Đã lưu file .md vào Google Drive."
    except Exception as e:
        return None, f"❌ Lỗi Google Drive: {str(e)}"
