import os
import json
import google.generativeai as genai

# Configure Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

SYSTEM_PROMPT = """
Bạn là một trợ lý ảo thông minh cho hệ thống MATRIX. Nhiệm vụ của bạn là phân tích câu chat của người dùng và trả về kết quả dưới dạng JSON để hệ thống xử lý.

Các hành động (action) hỗ trợ:
1. "SPENDING": Ghi lại chi tiêu. Trả về: {"action": "SPENDING", "amount": number, "category": string, "note": string}
2. "TASK": Ghi lại việc cần làm. Trả về: {"action": "TASK", "task": string, "due_date": string (format DD/MM/YYYY), "department": string}
3. "NOTE": Ghi chú cá nhân (Obsidian). Trả về: {"action": "NOTE", "title": string, "content": string}
4. "MATRIX": Yêu cầu tính toán ma trận/CSV. Trả về: {"action": "MATRIX", "formula": string, "filename": string}
5. "UNKNOWN": Nếu không hiểu ý định.

Luôn trả về JSON nguyên bản, không kèm giải thích.
"""

def parse_user_intent(text):
    if not GEMINI_API_KEY:
        return {"action": "UNKNOWN", "error": "Chưa cấu hình API Key cho Gemini."}

    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content([SYSTEM_PROMPT, text])
        
        # Extract JSON from response
        res_text = response.text.strip()
        # Basic cleanup in case Gemini adds markdown code blocks
        if res_text.startswith("```json"):
            res_text = res_text[7:-3].strip()
        elif res_text.startswith("```"):
            res_text = res_text[3:-3].strip()
            
        return json.loads(res_text)
    except Exception as e:
        return {"action": "UNKNOWN", "error": str(e)}

async def transcribe_voice(voice_file_path):
    """
    Placeholder for voice-to-text. Gemini can handle audio files directly.
    """
    # implementation will go here when we integrate audio
    pass
