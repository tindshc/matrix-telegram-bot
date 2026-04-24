from vnlunar import get_full_info
import vncalendar
from datetime import datetime

def get_solar_info_from_lunar(day, month, year, leap=0):
    """
    Converts Lunar date to Solar and returns full info.
    Attempts multiple import styles for vncalendar.
    """
    try:
        # Try different ways to call convertLunar2Solar based on library version
        s_day, s_month, s_year = None, None, None
        
        try:
            # Style 1: Direct from VanSu
            from vncalendar import VanSu
            s_day, s_month, s_year = VanSu.convertLunar2Solar(day, month, year, leap)
        except AttributeError:
            try:
                # Style 2: Nested SolarAndLunar
                from vncalendar import VanSu
                s_day, s_month, s_year = VanSu.SolarAndLunar.convertLunar2Solar(day, month, year, leap)
            except AttributeError:
                # Style 3: Direct from vncalendar
                from vncalendar import SolarAndLunar
                s_day, s_month, s_year = SolarAndLunar.convertLunar2Solar(day, month, year, leap)
        
        if s_day is None:
            raise Exception("Không tìm thấy hàm chuyển đổi trong thư viện vncalendar.")
            
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
        res.append(f"☀️ **Ngày Dương lịch**: {day}/{month}/{year}")
        res.append(f"🌙 **Ngày Âm lịch**: {info['lunar']['day']}/{info['lunar']['month']}/{info['lunar']['year']} ({'Nhuận' if info['is_leap'] else 'Thường'})")
        res.append(f"✨ **Năm**: {info['can_chi']['year']}")
        res.append(f"🎋 **Tháng**: {info['can_chi']['month']}")
        res.append(f"🧧 **Ngày**: {info['can_chi']['day']}")
        res.append(f"🌡️ **Tiết khí**: {info['solar_term']}")
        
        return "\n".join(res)
    except Exception as e:
        return f"Lỗi tính lịch: {str(e)}"

def process_date_input(text):
    """
    Parses input and decides if it's Solar or Lunar.
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
    except Exception as e:
        return f"Vui lòng nhập đúng định dạng:\n- `dd/mm/yyyy` (Dương -> Âm)\n- `am dd/mm/yyyy` (Âm -> Dương)\n\n(Lỗi: {str(e)})"


def process_callicham_input(text):
    """
    Parses `callicham` commands for standalone lunar/solar conversion.
    Supported forms:
    - `callicham 10/3/2026`
    - `callicham am 10/3/2026`
    - `callicham ngay 10/3/2026`
    """
    raw = text.lower().strip()
    if not raw.startswith("callicham"):
        return None

    payload = raw[len("callicham"):].strip()
    is_lunar = False

    if payload.startswith("ngay "):
        payload = payload[5:].strip()
    elif payload.startswith("am "):
        is_lunar = True
        payload = payload[3:].strip()

    if not payload:
        return "Vui lòng nhập đúng dạng:\n- `callicham 10/3/2026`\n- `callicham am 10/3/2026`\n- `callicham ngay 10/3/2026`"

    try:
        dt = datetime.strptime(payload, "%d/%m/%Y")
        if is_lunar:
            return get_solar_info_from_lunar(dt.day, dt.month, dt.year)
        return get_full_info_from_solar(dt.day, dt.month, dt.year)
    except Exception as e:
        return f"Vui lòng nhập đúng dạng:\n- `callicham 10/3/2026`\n- `callicham am 10/3/2026`\n- `callicham ngay 10/3/2026`\n\n(Lỗi: {str(e)})"
