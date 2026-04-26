import os
import json
import google.generativeai as genai

# Configure Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

SYSTEM_PROMPT = """
Bạn là một trợ lý ảo thông minh cho hệ thống MATRIX. Nhiệm vụ của bạn là phân tích câu chat của người dùng và trả về kết quả dưới dạng JSON.

Các hành động (action) hỗ trợ:
1. "SPENDING": Ghi lại chi tiêu. 
   Ví dụ: "Ăn sáng phở 40k", "Mua xăng 50000", "Tiền điện 1tr2"
   Trả về: {"action": "SPENDING", "amount": 40000, "category": "Ăn uống", "note": "phở"}

2. "TASK": Ghi lại việc cần làm.
   Ví dụ: "Nhắc mai họp lúc 9h sáng", "Giao cho Sương làm báo cáo trước 25/12"
   Trả về: {"action": "TASK", "task": "Họp lúc 9h sáng", "due_date": "27/04/2026", "department": "Hải Châu"}

3. "NOTE": Ghi chú cá nhân (Obsidian).
   Ví dụ: "Ghi chú: Ý tưởng kinh doanh quán cafe", "Lưu note: Cách nấu phở ngon"
   Trả về: {"action": "NOTE", "title": "Ý tưởng kinh doanh", "content": "..."}

4. "MATRIX": Yêu cầu tính toán ma trận/CSV (nếu có các lệnh như tinh, hien, tim).
   Trả về: {"action": "MATRIX", "formula": "tinh sum(sotien)", "filename": "spending"}

5. "UNKNOWN": Nếu không thuộc các loại trên.

QUY TẮC:
- Số tiền 40k hiểu là 40000, 1tr hiểu là 1000000.
- Trả về JSON nguyên bản, không giải thích.
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
