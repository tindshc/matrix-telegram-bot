# 📊 Matrix & Lunar Telegram Bot

Bot Telegram hỗ trợ tính toán Matrix trên file CSV và tra cứu Lịch Âm/Dương Việt Nam. Triển khai trên Vercel (Python) và sử dụng Upstash Redis để ghi nhớ dữ liệu.

## 🚀 Tính năng chính

### 1. 📊 Tính toán Matrix (Pandas)
- **Ghi nhớ file**: Khi bạn gửi file `.csv`, Bot sẽ tự động lưu tên file vào bộ nhớ.
- **Lệnh chính**:
  - `tên_file hien`
  - `tên_file tim ...`
  - `tên_file xem ...`
  - `tên_file nhap gui`
  - `tên_file nhap ...`
  - `tên_file sua ...`
  - `tên_file xoa ...`
  - `tên_file tinh ...`
- **Nhập nhanh**: `tên_file nhap 1 1 15,5 Sương nộp`
- **Nhập từng bước**: `tên_file nhap gui`, rồi nhập theo prompt từng bước; dùng `/back` và `/cancel`.
- **Cột chọn**: Cột bắt đầu bằng `s` là cột chọn, ví dụ `sgioitinh`.
- **Xem/Sửa/Xóa hàng**: `tên_file xem 1`, `tên_file sua 1 ten=An`, `tên_file xoa 1`.
- **Tính toán**: `tên_file tinh cbr = sinh*1000/dstb`
- **Tìm**: `tên_file tim 5~'đồng yên'`, có thể ghép `and` / `or`.
- **Hiện giá trị duy nhất**: `tên_file hien muc`, `tên_file hien thuchi`.

### 1b. ✅ Giao việc và theo dõi tiến độ
- **File việc**: Dùng tiền tố `j`, ví dụ `jviec` và `jphong`. Các file này vẫn lưu theo CSV nhưng được xử lý riêng.
- **Hướng dẫn nhập**: `jviec cachnhap` và `jphong cachnhap`.
- **Giao việc**: `jviec giao 28/4 Báo cáo ctv ds`, `jviec giao am 10/3 UBND phường - Chạp mã nhà thờ lớn gd`.
- **Hiện/Xem/Xong**: `jviec hien`, `jviec xem`, `jviec xem 1`, `jviec xong 1`.
- **Nhập danh sách tên**: `jphong ds nhap ld ngamy congtin` hoặc `jphong ds nhap ten=ld,ngamy,congtin`.
- **Nhập từng bước**: `jphong nhap gui` và `jviec nhap gui` chỉ hiện prompt từng bước; `jviec` có `diadiem` trước `nguoi`.
- **Chọn người**: Ở bước `nguoi`, bot hiện danh sách tên của phòng để chọn nhiều số như `1,2`.
- **File việc**: Dùng `/listj`.

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
6. Với việc giao việc, dùng `jviec` và `jphong...` như phần trên để theo dõi tiến độ.

---
*Phát triển bởi Antigravity AI trợ lý cho tindshc.*
