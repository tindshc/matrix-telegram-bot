from datetime import datetime


try:
    from main import SolarAndLunar, CanChi, TietKhi
except Exception:
    try:
        from vncalendar.main import SolarAndLunar, CanChi, TietKhi
    except Exception:
        from vncalendar import SolarAndLunar, CanChi, TietKhi


def get_full_info_from_solar(day, month, year):
    """
    Return lunar date, can chi, and solar term for a Gregorian date.
    """
    try:
        lunar_day, lunar_month, lunar_year, is_leap = SolarAndLunar.convertSolar2Lunar(day, month, year)
        lunar_label = "Nhuận" if is_leap else "Thường"

        res = []
        res.append(f"☀️ Ngày Dương lịch: {day}/{month}/{year}")
        res.append(f"🌙 Ngày Âm lịch: {lunar_day}/{lunar_month}/{lunar_year} ({lunar_label})")
        res.append(f"✨ Năm: {CanChi.nam(year)}")
        res.append(f"🎋 Tháng: {CanChi.thang(lunar_month, lunar_year)}")
        res.append(f"🧧 Ngày: {CanChi.ngay(day, month, year)}")
        res.append(f"🌡️ Tiết khí: {TietKhi.getTerm(day, month, year)}")

        return "\n".join(res)
    except Exception as e:
        return f"Lỗi tính lịch: {str(e)}"


def get_solar_info_from_lunar(day, month, year, leap=0):
    """
    Convert a lunar date to Gregorian and return full info for the solar date.
    """
    try:
        s_day, s_month, s_year = SolarAndLunar.convertLunar2Solar(day, month, year, leap)
        return get_full_info_from_solar(s_day, s_month, s_year)
    except Exception as e:
        return f"Lỗi chuyển đổi lịch âm: {str(e)}"


def process_date_input(text):
    """
    Backward-compatible direct date parsing.
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
        return get_full_info_from_solar(dt.day, dt.month, dt.year)
    except Exception as e:
        return (
            "Vui lòng nhập đúng định dạng:\n"
            "- `dd/mm/yyyy` (Dương -> Âm)\n"
            "- `am dd/mm/yyyy` (Âm -> Dương)\n"
            f"\n(Lỗi: {str(e)})"
        )


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
        return (
            "Vui lòng nhập đúng dạng:\n"
            "- `callicham 10/3/2026`\n"
            "- `callicham am 10/3/2026`\n"
            "- `callicham ngay 10/3/2026`"
        )

    try:
        dt = datetime.strptime(payload, "%d/%m/%Y")
        if is_lunar:
            return get_solar_info_from_lunar(dt.day, dt.month, dt.year)
        return get_full_info_from_solar(dt.day, dt.month, dt.year)
    except Exception as e:
        return (
            "Vui lòng nhập đúng dạng:\n"
            "- `callicham 10/3/2026`\n"
            "- `callicham am 10/3/2026`\n"
            "- `callicham ngay 10/3/2026`\n"
            f"\n(Lỗi: {str(e)})"
        )
