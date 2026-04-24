from vnlunar import get_full_info
from datetime import datetime

def get_lunar_info(day, month, year):
    """
    Given a solar date, returns detailed lunar info.
    """
    try:
        info = get_full_info(day, month, year)
        
        # info structure typically contains lunar_day, lunar_month, lunar_year, can_chi, etc.
        res = []
        res.append(f"📅 Dương lịch: {day}/{month}/{year}")
        res.append(f"🌙 Âm lịch: {info['lunar_day']}/{info['lunar_month']} ({'Nhuận' if info['is_leap'] else 'Thường'})")
        res.append(f"✨ Năm: {info['can_chi']['year']}")
        res.append(f"🎋 Tháng: {info['can_chi']['month']}")
        res.append(f"🧧 Ngày: {info['can_chi']['day']}")
        res.append(f"🕒 Giờ: {info['can_chi']['hour']}")
        res.append(f"🌡️ Tiết khí: {info['solar_term']}")
        
        return "\n".join(res)
    except Exception as e:
        return f"Lỗi tính lịch: {str(e)}"

def solar_to_lunar_str(date_str):
    """Parses dd/mm/yyyy and returns lunar info"""
    try:
        dt = datetime.strptime(date_str, "%d/%m/%Y")
        return get_lunar_info(dt.day, dt.month, dt.year)
    except:
        return "Vui lòng nhập ngày theo định dạng: dd/mm/yyyy (ví dụ: 24/04/2026)"
