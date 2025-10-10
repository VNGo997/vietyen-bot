# vietyen-bot — Bot đăng bài sức khỏe lên WordPress (bản nháp)

> Không cần server. Chạy bằng GitHub Actions mỗi sáng 08:00 (UTC+7). Bài **chỉ đăng dạng nháp**.

## 1) Cài đặt nhanh (5–10 phút)

### A. Tạo Application Password trên WordPress
1. Đăng nhập `WP-Admin` → **Users** → **Profile** (Hồ sơ) của tài khoản quản trị.
2. Tìm phần **Application Passwords** → nhập tên bất kỳ (VD: `vietyen-bot`) → **Add New Application Password**.
3. **Sao chép** mật khẩu ứng dụng vừa hiện ra (chỉ hiện **1 lần**).
4. Ghi lại 3 thứ:
   - `WP_URL` — VD: `https://vietyenltd.com`
   - `WP_USERNAME` — tên đăng nhập admin của bạn
   - `WP_APP_PASSWORD` — chuỗi mật khẩu ứng dụng vừa tạo

### B. Tạo repo GitHub và upload mã nguồn
1. Vào https://github.com → **New** repo → đặt tên `vietyen-bot`.
2. Tải file ZIP từ hướng dẫn và **Extract** ra.
3. Kéo thả **toàn bộ thư mục** vào repo (hoặc **Upload files**). Commit lên `main`.

### C. Thêm Secrets cho Actions
1. Trong repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**.
2. Tạo 3 secrets:
   - `WP_URL` → ví dụ `https://vietyenltd.com`
   - `WP_USERNAME` → tên đăng nhập admin
   - `WP_APP_PASSWORD` → mật khẩu ứng dụng
3. (Tuỳ chọn) Nếu muốn gán Category ID mặc định, mở `config.json` và điền `category_id` (số).

### D. Chạy thử tay
1. Repo → tab **Actions** → chọn workflow **Daily Bot Run**.
2. Bấm **Run workflow** → **Run**.
3. Xem logs; nếu OK → vào WordPress **Posts → Drafts** kiểm tra bài nháp.

> Mẹo: có thể chạy `python bot.py --test` để đăng một bài “Hello test” (khi chạy cục bộ).

## 2) Tùy chỉnh
- `config.json`: `bot_status`, `post_cycle`, `sources`, `category_id`, `tags`, `post_status`.
- `style-template.css`: chỉnh tông màu/độ rộng/chữ.
- Có thể thêm nguồn RSS khác (VD: chuyên đề mắt, phụ nữ…) — chỉ cần thêm vào `sources`.

## 3) Khắc phục lỗi nhanh
- 401/403: sai `WP_USERNAME` hoặc `WP_APP_PASSWORD` / tài khoản không đủ quyền.
- 404: sai `WP_URL` (thiếu `https://` hoặc domain khác).
- 5xx: WordPress đang bận → thử lại.
- Bài trắng: nguồn không cho copy nội dung → vẫn sẽ chèn “Nguồn bài viết” để bạn đọc tay.

---

Made with ❤️ for VietYenLTD
