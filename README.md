# 📊 Matrix & Lunar Telegram Bot

Bot Telegram hỗ trợ tính toán Matrix trên file CSV và tra cứu Lịch Âm/Dương Việt Nam. Triển khai trên Vercel (Python) và sử dụng Upstash Redis để ghi nhớ dữ liệu.

## 🚀 Tính năng chính

### 1. 📊 Tính toán Matrix (Pandas)
- **Ghi nhớ file**: Khi bạn gửi file `.csv`, Bot sẽ tự động lưu tên file vào bộ nhớ.
- **Tính toán theo tên**: Chỉ cần gõ `tên_file công_thức` để tính toán.
    - Ví dụ: `bctk cbr = sosinh * 1000 / dstb`
- **Hiện danh sách cột**: Gõ `tên_file hien` để xem cột theo số thứ tự.
- **Hiện giá trị cột**: Gõ `tên_file hien muc` hoặc `tên_file hien thuchi` để xem các giá trị không trùng của cột đó.
- **Nhập dòng mới**: Gõ `tên_file nhap muc=Quỹ cơ quan thuchi=Thu sotien=15,5 noidung=Sương nộp` để thêm dòng mới, `id` sẽ tự tăng nếu có cột `id`.
- **Tìm theo số cột**: Gõ `tên_file tim 5~'đồng yên'` để tìm chuỗi trong cột số 5, không phân biệt hoa thường. Có thể ghép thêm `and` / `or`, ví dụ `tên_file tim 5~'hoacuong' and 1==2020`.
- **Xem một dòng**: Gõ `tên_file xem 1` để hiện lại dòng số 1 theo dạng dọc.
- **Xem theo nhóm**: Với file có cột `muc`, `thuchi`, `sotien`, `noidung`, gõ `tên_file xem 1 1` để xem chi tiết theo nhóm đã chọn và tổng thu/chi.
- **Xóa file nhầm**: Gõ `tên_file xoa` hoặc `/del tên_file` để xóa file khỏi bộ nhớ.
- **Tính toán bằng cách Reply**: Trả lời trực tiếp vào file CSV với công thức.
- **Hỗ trợ hàm Pandas**: Có thể dùng các phép tính cộng, trừ, nhân, chia, làm tròn...

### 2. 🌙 Tra cứu Lịch Âm/Dương
- **Dương sang Âm**: Nhập `callicham 24/04/2026` hoặc `callicham ngay 24/04/2026`.
- **Âm sang Dương**: Nhập `callicham am 24/04/2026`.
- **Thông tin chi tiết**: Trả về Ngày/Tháng/Năm Âm lịch, Can Chi (Ngày/Tháng/Năm) và Tiết khí.

### 3. 📋 Quản lý bộ nhớ (Redis)
- **/list**: Xem danh sách các file CSV đã lưu.
- **/listmd**: Xem danh sách các file Markdown đã lưu.
- **/del <tên_file>**: Xóa file khỏi bộ nhớ.

### 4. 📄 Quy trình Markdown
- **Nạp file `.md`**: Bot lưu file theo tên, ví dụ `mdquytrinh.md` sẽ dùng tên `mdquytrinh`. Các file có chữ `md` trong tên cũng được nhận dạng là Markdown.
- **Cấu trúc**: Dùng `#` cho cấp 1, `##` cho cấp 2, `###` cho cấp 3.
- **Mục lục**: Gõ `mdquytrinh hien` hoặc `mdquytrinh hien 1 1` để xem mục con theo từng cấp. Ví dụ `mdphongtuc hien` sẽ hiện các chủ đề lớn.
- **Tìm**: Gõ `mdquytrinh tim ~'đại hội chi bộ'` để tìm theo tiêu đề/nội dung, không phân biệt hoa thường.
- **Xem chi tiết**: Gõ `mdquytrinh xem 1` để xem cấp 1, `mdquytrinh xem 1 1` để xem cấp 2, hoặc `mdquytrinh xem 1 1 1` để xem cấp 3.
- **Xóa mục con**: Gõ `mdquytrinh xoa 2` hoặc `mdquytrinh xoa 2 1` để xóa riêng một mục trong file Markdown.
- **Gộp**: Gõ `mdquytrinh them mdquytrinh2.md` để gộp file nguồn vào file tổng, rồi bot tự xóa file nguồn khỏi bộ nhớ.
- **Xóa file**: Gõ `mdquytrinh xoa` hoặc `/del mdquytrinh`.

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
2. Upload file CSV hoặc Markdown quy trình, bot sẽ tự ghi nhớ tên file.
3. Gõ `data x = a + b` để tính toán cột mới `x` từ hai cột `a` và `b`.
4. Gõ `callicham 24/04/2026` để xem lịch dương sang âm, hoặc `callicham am 24/04/2026` để đổi âm sang dương.
5. Gửi file Markdown quy trình như `mdquytrinh.md` rồi dùng `hien`, `tim`, `xem`, `xoa`, `them` theo cấu trúc trên.

---
*Phát triển bởi Antigravity AI trợ lý cho tindshc.*
