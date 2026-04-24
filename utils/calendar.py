from vnlunar import get_full_info
from vncalendar import VanSu
from datetime import datetime

def get_solar_info_from_lunar(day, month, year, leap=0):
    """
    Converts Lunar date to Solar and returns full info.
    """
    try:
        # Convert Lunar to Solar
        s_day, s_month, s_year = VanSu.SolarAndLunar.convertLunar2Solar(day, month, year, leap)
        
        # Now get full info from that solar date
        return get_full_info_from_solar(s_day, s_month, s_year)
    except Exception as e:
        return f"Lỗi chuyển đổi lịch âm: {str(e)}"

def get_full_info_from_solar(day, month, year):
    """
    Returns full details (Lunar, Can Chi, Solar Term) from Solar date.
    """
    try:
        info = get_full_info(day, month, year)
        
        res = []
        res.append(f"☀️ Dương lịch: {day}/{month}/{year}")
        res.append(f"🌙 Âm lịch: {info['lunar']['day']}/{info['lunar']['month']}/{info['lunar']['year']} ({'Nhuận' if info['is_leap'] else 'Thường'})")
        res.append(f"✨ Năm: {info['can_chi']['year']}")
        res.append(f"🎋 Tháng: {info['can_chi']['month']}")
        res.append(f"🧧 Ngày: {info['can_chi']['day']}")
        res.append(f"🌡️ Tiết khí: {info['solar_term']}")
        
        return "\n".join(res)
    except Exception as e:
        return f"Lỗi tính lịch: {str(e)}"

def process_date_input(text):
    """
    Parses input and decides if it's Solar or Lunar.
    Syntax: 
    - 24/04/2026 (Solar -> Lunar)
    - am 24/04/2026 (Lunar -> Solar)
    """
    text = text.lower().strip()
    is_lunar = False
    
    if text.startswith("am "):
        is_lunar = True
        date_str = text.replace("am ", "").strip()
    else:
        date_str = text

    try:
        dt = datetime.strptime(date_str, "%d/%m/%Y")
        if is_lunar:
            return get_solar_info_from_lunar(dt.day, dt.month, dt.year)
        else:
            return get_full_info_from_solar(dt.day, dt.month, dt.year)
    except:
        return "Vui lòng nhập đúng định dạng:\n- `dd/mm/yyyy` (Dương -> Âm)\n- `am dd/mm/yyyy` (Âm -> Dương)"
