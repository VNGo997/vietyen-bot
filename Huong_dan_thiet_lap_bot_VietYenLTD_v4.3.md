# HƯỚNG DẪN THIẾT LẬP & VẬN HÀNH BOT ĐĂNG TIN Y TẾ — VietYenLTD (v4.3)

> Cập nhật: 2025-10-10 18:23

Bản **v4.3** theo yêu cầu của bạn:
- ✅ **Bổ sung bộ lọc chủ đề & RSS** (6 nguồn chính thống).
- ✅ **Bộ lọc thông minh AI check** (dùng `OPENAI_API_KEY`, fallback từ khóa nếu không có).
- ✅ Ảnh **không ép tông thương hiệu**, chỉ theo tông y tế chuẩn (Unsplash, không cần API).
- ✅ **Tự chèn liên kết nội bộ** (Visionary…).
- ✅ **Chỉ đăng bản nháp** lên WordPress (post `status=draft`).

---

## 1) Tải gói bot
- Gói chạy thực tế: **[vietyen-bot-v4.3.zip](sandbox:/mnt/data/vietyen-bot-v4.3.zip)**

> Nếu link tải bị chặn, bấm chuột phải → *Save link as…*

---

## 2) Chuẩn bị trên WordPress
1. Tạo **Application Password** cho user bot (WP Admin → Người dùng → Hồ sơ → *Mật khẩu ứng dụng*).
2. Lưu 3 thông tin để dùng cho GitHub Actions:
   - `WP_URL` – ví dụ: `https://vietyenltd.com`
   - `WP_USERNAME` – user có Application Password
   - `WP_APP_PASSWORD` – chuỗi mật khẩu ứng dụng

---

## 3) Cập nhật repo GitHub `vietyen-bot`
1. Giải nén file zip.
2. Lên GitHub → Repo `vietyen-bot` → **Code → Add file → Upload files**.
3. Kéo–thả **toàn bộ** file (ghi đè).
4. **Commit changes**.

Cấu trúc thư mục:
```
vietyen-bot-v4.3/
├─ bot.py
├─ config.json
├─ requirements.txt
├─ style-template.css
├─ Visionary_Bai_mau_HTML.html
└─ .github/workflows/bot-daily.yml
```

---

## 4) Khai báo Secrets cho Actions
GitHub → **Settings → Secrets and variables → Actions → New repository secret**:
- `WP_URL`
- `WP_USERNAME`
- `WP_APP_PASSWORD`
- *(tuỳ chọn)* `OPENAI_API_KEY` — để bật **AI check**.

---

## 5) Chạy bot
1. Vào **Actions** → chọn workflow **Daily Bot Run** → **Run workflow**.
2. Kiểm tra **Bài viết → Bản nháp** trên WordPress.

> Lưu ý: Nếu không có `OPENAI_API_KEY`, bot vẫn hoạt động nhờ lọc từ khóa.

---

## 6) Tùy chỉnh nhanh (`config.json`)
- `rss_sources`: danh sách 6 nguồn RSS y tế (có thể thay).
- `ai_check.enabled`: `true/false` để bật/tắt AI gate.
- `internal_links`: mapping từ khóa → link nội bộ (Visionary…).
- `image_policy.min_images`: để `2` cho 1 ảnh hero + 1 ảnh giữa bài.
- `post_status`: luôn là `"draft"` theo yêu cầu.

---

## 7) Gỡ lỗi nhanh
- **Không thấy bản nháp**: thiếu Secrets hoặc user không đủ quyền.
- **Ảnh không hiện**: hosting chặn `source.unsplash.com` → thay bằng URL ảnh Media site trong `topics[].fallback_images`.
- **AI check không chạy**: chưa có `OPENAI_API_KEY` hoặc bị firewall → bot tự fallback về lọc từ khóa.

---

## 8) Ghi chú
- Bot **không đăng tự động** bản chính thức. Bạn duyệt rồi bấm *Đăng*.
- Có thể mở rộng thêm chuyên mục, auto meta title/description trong bản kế tiếp.

**Hết.** Chúc bạn triển khai thuận lợi!
