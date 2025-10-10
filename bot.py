# vietyen-bot v4.2c
# Tự sinh phần "Gợi ý từ chuyên gia" theo chủ đề bài viết

import json

def detect_topic(title, cfg):
    for t in cfg.get("topics", []):
        if any(k.lower() in title.lower() for k in t.get("match", [])):
            return t
    return None

def render_expert_advice(topic_name, cfg):
    advice_cfg = (cfg.get("expert_advice", {}) or {}).get(topic_name) or (cfg.get("expert_advice", {}) or {}).get("default", {})
    title = advice_cfg.get("title", "💬 Gợi ý từ chuyên gia")
    lead  = advice_cfg.get("lead", "Bác sĩ khuyên duy trì vệ sinh, nghỉ ngơi và lối sống lành mạnh mỗi ngày.")
    label = advice_cfg.get("product_label", "Xem thêm sản phẩm")
    url   = advice_cfg.get("product_url", "https://vietyenltd.com/san-pham/")
    return f'''
    <h2>{title}</h2>
    <div class="vy-cta" style="line-height:1.7;padding:24px 20px;background:linear-gradient(135deg,#004aad,#0b73d5);color:#fff;border-radius:12px;text-align:center">
      <p style="font-size:17px;margin-bottom:12px">👩‍⚕️ <strong>Khuyên dùng:</strong> {lead}</p>
      <p style="margin:0">🌐 Tham khảo: <a href="{url}" target="_blank" rel="noopener" style="color:#ffe07a;text-decoration:underline;font-weight:600">{label}</a></p>
    </div>
    '''

def build_html(title, css, hero, mid, expert_html):
    return f'''
    <html><head><style>{css}</style></head><body>
    <div class="vy-hero"><img src="{hero}" style="width:100%;border-radius:14px"></div>
    <h1>{title}</h1>
    <p>Bài viết được đăng tự động nhằm chia sẻ kiến thức sức khỏe tới cộng đồng.</p>
    <img src="{mid}" style="width:100%;border-radius:10px;margin:18px 0">
    {expert_html}
    </body></html>
    '''

def main():
    with open("config.json", "r", encoding="utf-8") as f:
        cfg = json.load(f)

    title = "Chăm sóc mắt và phòng ngừa khô mắt ở người dùng máy tính"
    topic = detect_topic(title, cfg)
    topic_name = (topic or {}).get("name", "default")
    expert_html = render_expert_advice(topic_name, cfg)
    css = "body{font-family:sans-serif}"
    hero = cfg.get("default_hero_url")
    mid = "https://source.unsplash.com/1200x800/?eyecare,health"
    html = build_html(title, css, hero, mid, expert_html)

    with open("demo_expert_output.html", "w", encoding="utf-8") as f:
        f.write(html)

if __name__ == "__main__":
    main()
