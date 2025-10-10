# v4.2b — Post a guaranteed sample health article with 1–2 Unsplash images
import json, datetime
from wordpress_connection import get_wp_from_env

def detect_topic(title, cfg):
    for t in cfg.get("topics", []):
        if any(k.lower() in title.lower() for k in t.get("match", [])):
            return t
    return None

def build_html(title, css, hero, mid):
    bullets = [
        "Khoảng <strong>80%</strong> người làm việc máy tính trên 4 giờ/ngày gặp triệu chứng khô hoặc mỏi mắt.",
        "Không khí điều hòa làm giảm độ ẩm, dễ gây khô rát và kích ứng.",
        "Tần suất chớp mắt giảm mạnh khi nhìn màn hình tập trung.",
        "Nghỉ mắt 20–20–20, chớp mắt thường xuyên và vệ sinh bờ mi giúp mắt khỏe hơn."
    ]
    body = f"""
<style>{css}</style>
<article class="vy-article">
  <div class="vy-meta"><span class="vy-badge">Bản nháp tự động</span>{datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}</div>
  <h1>{title}</h1>
  <figure class="vy-hero"><img src="{hero}" alt="Ảnh minh họa y tế"/></figure>

  <div class="vy-note"><strong style="color:#004aad">🩺 Tóm tắt ngắn gọn:</strong> 
  Làm việc trước màn hình lâu có thể khiến mắt khô, mỏi và mờ thoáng qua. Bài viết tóm lược nguyên nhân và cách chăm sóc an toàn mỗi ngày.</div>

  <h2>💡 Điều bạn cần lưu ý</h2>
  <ul style="list-style:none;padding-left:0;line-height:1.75;margin:10px 0 22px">
    {''.join(f'<li>✅ {b}</li>' for b in bullets)}
  </ul>

  {f'<figure class="vy-hero"><img src="{mid}" alt="Ảnh minh họa y tế"/><figcaption style="text-align:center;color:#667;font-size:13px;margin-top:6px">Ảnh minh họa: Unsplash</figcaption></figure>' if mid else ''}

  <h2>❓ Vì sao bạn dễ gặp tình trạng này?</h2>
  <p>Thói quen nhìn màn hình liên tục khiến màng nước mắt bay hơi nhanh, làm khô giác mạc và tạo cảm giác rát hoặc nhức mỏi. 
  Trong môi trường điều hòa, độ ẩm thường thấp, càng khiến mắt dễ kích ứng.</p>
  <p>Hội chứng thị giác màn hình (Computer Vision Syndrome) bao gồm khô, mờ, đau đầu và nhạy sáng. 
  Nếu kéo dài, mắt có thể viêm bờ mi hoặc rối loạn tiết dầu.</p>

  <h2>🧭 Cách chăm sóc và phòng ngừa hiệu quả</h2>
  <div class="vy-card">
    <ol style="margin:0 0 0 18px;line-height:1.7">
      <li><strong>Quy tắc 20–20–20:</strong> Sau mỗi 20 phút, nhìn xa 6m trong ít nhất 20 giây.</li>
      <li><strong>Giữ độ ẩm phòng:</strong> 50–60%, tránh luồng gió thổi trực tiếp vào mắt.</li>
      <li><strong>Vệ sinh bờ mi:</strong> Dùng gạc vệ sinh vô trùng, nhẹ dịu mỗi ngày.</li>
      <li><strong>Ánh sáng hợp lý:</strong> Tránh màn hình quá chói hoặc phòng quá tối.</li>
    </ol>
    <p style="margin:10px 0 0;color:#556;font-size:14px">ℹ️ Nếu khô rát kéo dài &gt; 1 tuần, hãy đi khám nhãn khoa.</p>
  </div>

  <h2>👥 Ai nên áp dụng những hướng dẫn này</h2>
  <ul style="list-style:disc;margin-left:22px;line-height:1.7">
    <li>Nhân viên văn phòng, lập trình viên, học sinh – sinh viên.</li>
    <li>Người làm việc trong phòng kín, môi trường điều hòa.</li>
    <li>Người đeo kính áp tròng hoặc trang điểm mắt thường xuyên.</li>
  </ul>

  <h2>💬 Gợi ý từ chuyên gia</h2>
  <div class="vy-cta">
    <div style="font-size:18px;font-weight:700;margin-bottom:6px">Chăm sóc mắt khỏe mỗi ngày</div>
    <div>🌐 Tham khảo: <a href="https://vietyenltd.com/san-pham/gac-ve-sinh-bo-mi-visionary/" target="_blank" rel="noopener">Gạc vệ sinh bờ mi Visionary</a></div>
  </div>

  <div class="vy-footer">
    <div class="vy-src"><strong style="color:#004aad">🔗 Nguồn tham khảo:</strong><br>
      <a href="https://suckhoedoisong.vn" target="_blank" rel="nofollow noopener">Sức Khỏe &amp; Đời Sống</a>
    </div>
    <div class="vy-src"><strong style="color:#004aad">⚠️ Miễn trừ trách nhiệm:</strong><br>
      Nội dung chỉ nhằm mục đích tham khảo, không thay thế tư vấn, chẩn đoán hoặc điều trị y khoa.
    </div>
  </div>
</article>
"""
    return body

def main():
    with open("config.json","r",encoding="utf-8") as f:
        cfg = json.load(f)
    css = open("style-template.css","r",encoding="utf-8").read()

    title = "Chăm sóc mắt và phòng ngừa khô mắt ở người dùng máy tính"
    topic = detect_topic(title, cfg) or {}
    fallbacks = topic.get("fallback_images", []) or [cfg.get("default_hero_url")]
    hero = fallbacks[0]
    mid = fallbacks[1] if len(fallbacks) > 1 else None

    html = build_html(title, css, hero, mid)

    wp = get_wp_from_env()
    featured_id = wp.upload_media_from_url(hero, filename="hero.jpg")
    tags = wp.create_or_get_tags(cfg.get("tags_by_name"))
    res = wp.post_article(title, html, status=cfg.get("post_status","draft"),
                          category_id=cfg.get("category_id"), tag_ids=tags, featured_media=featured_id)
    print("Posted draft:", res.get("link","(no link)"))

if __name__ == "__main__":
    main()
