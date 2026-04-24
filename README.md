# 📊 Matrix & Lunar Telegram Bot

Bot Telegram hỗ trợ tính toán Matrix trên file CSV và tra cứu Lịch Âm/Dương Việt Nam. Triển khai trên Vercel (Python) và sử dụng Upstash Redis để ghi nhớ dữ liệu.

## 🚀 Tính năng chính

### 1. 📊 Tính toán Matrix (Pandas)
- **Ghi nhớ file**: Khi bạn gửi file `.csv`, Bot sẽ tự động lưu tên file vào bộ nhớ.
- **Tính toán theo tên**: Chỉ cần gõ `tên_file công_thức` để tính toán.
    - Ví dụ: `bctk cbr = sosinh * 1000 / dstb`
- **Tính toán bằng cách Reply**: Trả lời trực tiếp vào file CSV với công thức.
- **Hỗ trợ hàm Pandas**: Có thể dùng các phép tính cộng, trừ, nhân, chia, làm tròn...

### 2. 🌙 Tra cứu Lịch Âm/Dương
- **Dương sang Âm**: Nhập ngày `dd/mm/yyyy` (VD: `24/04/2026`).
- **Âm sang Dương**: Nhập `am dd/mm/yyyy` (VD: `am 01/01/2026`).
- **Thông tin chi tiết**: Trả về Ngày/Tháng/Năm Âm lịch, Can Chi (Ngày/Tháng/Năm) và Tiết khí.

### 3. 📋 Quản lý bộ nhớ (Redis)
- **/list**: Xem danh sách các file CSV đã lưu.
- **/del <tên_file>**: Xóa file khỏi bộ nhớ.

## 🛠 Hướng dẫn thiết lập (Cho Admin)

1. **Vercel Environment Variables**:
    - `TELEGRAM_BOT_TOKEN`: Token lấy từ @BotFather.
    - `UPSTASH_REDIS_REST_URL`: URL từ Upstash Redis.
    - `UPSTASH_REDIS_REST_TOKEN`: Token từ Upstash Redis.

2. **Kích hoạt Webhook**:
    Truy cập link sau trên trình duyệt:
    `https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://<YOUR_VERCEL_DOMAIN>/api/webhook`

## 📖 Cách sử dụng cho người dùng
1. Gõ `/start` để mở Menu chính.
2. Gửi file CSV (ví dụ `data.csv`) -> Bot báo đã lưu tên `data`.
3. Gõ `data x = a + b` để tính toán cột mới `x` từ hai cột `a` và `b`.
4. Nhập ngày tháng để xem lịch âm/dương.

---
*Phát triển bởi Antigravity AI trợ lý cho tindshc.*
