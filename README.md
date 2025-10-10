# vietyen-bot v3 — tối ưu chủ đề & hình ảnh & chống trùng
- Lọc chủ đề sức khỏe/y tế dựa trên `include_keywords` trong **tiêu đề hoặc tóm tắt** + loại trừ `exclude_keywords`.
- Tự lấy **og:image** (hoặc `default_hero_url` nếu thiếu), **upload lên Media** và gán **Featured Image** cho bài nháp.
- Tạo tag theo **tên** nếu chưa có (config: `tags_by_name`).
- Chống trùng: bỏ qua nếu WordPress đã có bài **trùng tiêu đề**.
- Link nguồn kèm UTM; footer gọn đẹp.
