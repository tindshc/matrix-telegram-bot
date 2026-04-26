# Hướng dẫn cấu hình MATRIX Assistant V2

Để hệ thống V2 hoạt động, bạn cần bổ sung các biến môi trường sau vào Vercel (hoặc file `.env` nếu chạy local):

### 1. Google API (Sheets & Drive)
*   **GOOGLE_SERVICE_ACCOUNT_JSON**: Toàn bộ nội dung file JSON của Service Account (dạng string).
*   **DEFAULT_SHEET_ID**: ID của file Google Sheet bạn muốn dùng làm database (lấy từ URL của sheet).
*   **DEFAULT_DRIVE_FOLDER_ID**: ID của folder trên Google Drive để lưu file Markdown cho Obsidian.

### 2. AI (Gemini)
*   **GEMINI_API_KEY**: API Key lấy từ [Google AI Studio](https://aistudio.google.com/).

### 3. Cấu trúc Google Sheet
Hãy tạo các Worksheet (tab) sau trong Google Sheet của bạn:
*   **Spending**: Các cột `Ngày`, `Số tiền`, `Hạng mục`, `Ghi chú`.
*   **Tasks**: Các cột `Hạn`, `Việc`, `Bộ phận`.
*   **Data**: (Nếu bạn muốn dùng tính năng Matrix trên Sheets).

### Cách hoạt động mới:
1.  **Nhập tự nhiên:** Chat *"Ăn sáng 30k"* -> Tự động vào sheet Spending.
2.  **Ghi chú:** Chat *"Ghi chú: Ý tưởng dự án mới..."* -> Tự động tạo file `.md` trên Drive.
3.  **Lệnh cũ:** Các lệnh như `/list`, `jviec hien`, ... vẫn hoạt động bình thường.
