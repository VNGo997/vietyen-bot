#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vietyen-bot v4.3
- Lọc RSS sức khỏe
- AI check chủ đề (tùy chọn, qua OPENAI_API_KEY)
- Chèn ảnh minh họa (Unsplash, không cần API)
- Tạo bài viết bản nháp lên WordPress (Application Password)
- Tự chèn liên kết nội bộ theo từ khóa
"""
import os, re, json, time, html
from typing import List, Dict, Any, Optional
import requests

try:
    import feedparser
except Exception:
    pass

CONFIG_PATH = os.environ.get("BOT_CONFIG_PATH", "config.json")

def load_config() -> Dict[str, Any]:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def ai_health_gate(text: str, cfg: Dict[str, Any]) -> bool:
    settings = cfg.get("ai_check", {})
    if not settings.get("enabled"):
        return True
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return keyword_gate(text)
    prompt = settings.get("prompt", "Chỉ trả về Y nếu là y tế, N nếu không.")
    model = settings.get("model", "gpt-4o-mini")
    try:
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "You are a concise content gatekeeper. Answer with a single letter."},
                    {"role": "user", "content": prompt + "\n\n" + text[:6000]}
                ],
                "temperature": 0
            },
            timeout=30
        )
        resp.raise_for_status()
        data = resp.json()
        answer = data["choices"][0]["message"]["content"].strip().upper()
        return answer.startswith("Y")
    except Exception:
        return keyword_gate(text)

def keyword_gate(text: str) -> bool:
    text_low = text.lower()
    keywords = [
        "sức khỏe","y tế","bệnh","điều trị","dự phòng","triệu chứng","chẩn đoán",
        "nhãn khoa","bờ mi","khô mắt","viêm","thuốc","bác sĩ","bệnh viện",
        "phòng bệnh","vaccine","dinh dưỡng","tim mạch","da liễu","nhi khoa"
    ]
    return any(k in text_low for k in keywords)

def pick_images(cfg: Dict[str, Any], content: str) -> List[str]:
    text_low = content.lower()
    for tp in cfg.get("topics", []):
        for m in tp.get("match", []):
            if m.lower() in text_low:
                return tp.get("fallback_images", [])
    return [cfg.get("default_hero_url")]

def build_html(post_title: str, post_body: str, images: List[str], cfg: Dict[str, Any]) -> str:
    hero = images[0] if images else cfg.get("default_hero_url")
    mid_img = images[1] if len(images) > 1 else None
    caption = "Ảnh minh hoạ: Unsplash"
    bullets_html = ""
    import re as _re
    bullets = _re.findall(r"^[\-–•]\s*(.+)$", post_body, flags=_re.MULTILINE)
    if bullets:
        li = "\n".join([f"<li>✅ {html.escape(b)}</li>" for b in bullets[:6]])
        bullets_html = (
            '<h2 style="color:#004aad;border-bottom:2px solid #e1edff;padding-bottom:6px">💡 Điều bạn cần lưu ý</h2>'
            '<ul style="list-style:none;padding-left:0;line-height:1.75;margin:10px 0 22px">'
            + li + "</ul>"
        )
    core = html.escape(post_body).replace("\n","<br>")
    mid_html = ""
    if mid_img:
        mid_html = (
            '<figure style="margin:16px 0 18px">'
            f'<img src="{mid_img}" alt="" style="width:100%;height:auto;border-radius:14px;object-fit:cover;">'
            f'<figcaption style="text-align:center;color:#667;font-size:13px;margin-top:6px">{caption}</figcaption>'
            '</figure>'
        )
    html_doc = (
        "<!-- HERO -->"
        '<figure style="margin:0 0 18px">'
        f'<img src="{hero}" alt="" style="width:100%;height:auto;border-radius:14px;object-fit:cover;">'
        f'<figcaption style="text-align:center;color:#667;font-size:13px;margin-top:6px">{caption}</figcaption>'
        '</figure>'
        '<div style="background:linear-gradient(90deg,#eaf2ff,#f7fbff);border:1px solid #d9e7ff;border-radius:12px;padding:14px 16px;margin:16px 0">'
        '<strong style="color:#004aad">🩺 Tóm tắt ngắn gọn:</strong> Bài viết sức khỏe được biên tập ngắn gọn theo chuẩn Visionary.'
        '</div>'
        + bullets_html + mid_html +
        '<div style="margin-top:20px">' + core + '</div>'
    )
    return html_doc

def inject_internal_link(html_doc: str, cfg: Dict[str, Any], raw_text: str) -> str:
    txt = raw_text.lower()
    blocks = []
    for rule in cfg.get("internal_links", []):
        if any(k.lower() in txt for k in rule.get("keywords", [])):
            box = (
                '<div style="margin:26px 0;background:linear-gradient(135deg,#004aad,#0b73d5);color:#fff;border-radius:12px;padding:18px;text-align:center">'
                '<div style="font-size:18px;font-weight:700;margin-bottom:6px">💬 Gợi ý từ chuyên gia</div>'
                f'<div>Tham khảo: <a href="{html.escape(rule["url"])}" style="color:#ffe07a;text-decoration:underline">{html.escape(rule["title"])}</a></div>'
                '</div>'
            )
            blocks.append(box)
    if blocks:
        html_doc += "".join(blocks)
    footer = (
        '<div style="border:1px solid #e8eefc;border-radius:12px;padding:14px 16px;background:#fbfdff;margin-top:24px">'
        '<p style="margin:0 0 8px"><span style="color:#004aad">🔗 Nguồn tham khảo:</span> Tổng hợp từ các nguồn chính thống về sức khỏe.</p>'
        '<p style="margin:0;color:#667;font-size:14px">⚠️ <strong>Miễn trừ trách nhiệm:</strong> Nội dung chỉ tham khảo, không thay thế tư vấn y khoa.</p>'
        '</div>'
    )
    return html_doc + footer

def wp_create_draft(title: str, content: str, tags: List[str], cfg: Dict[str, Any]) -> Optional[int]:
    wp_url = os.environ.get("WP_URL", "").rstrip("/")
    user = os.environ.get("WP_USERNAME")
    app_pw = os.environ.get("WP_APP_PASSWORD")
    if not (wp_url and user and app_pw):
        print("Thiếu WP_URL/WP_USERNAME/WP_APP_PASSWORD → bỏ qua đăng bài.")
        return None
    tag_ids = []
    try:
        for t in tags:
            r = requests.get(f"{wp_url}/wp-json/wp/v2/tags", params={"search": t, "per_page": 1}, auth=(user, app_pw), timeout=20)
            if r.ok and r.json():
                tag_ids.append(r.json()[0]["id"])
            else:
                cr = requests.post(f"{wp_url}/wp-json/wp/v2/tags", json={"name": t}, auth=(user, app_pw), timeout=20)
                if cr.ok:
                    tag_ids.append(cr.json()["id"])
    except Exception as e:
        print("Tạo/gán tag lỗi:", e)

    payload = {"title": title, "content": content, "status": "draft", "tags": tag_ids}
    cat_id = cfg.get("category_id")
    if cat_id:
        payload["categories"] = [cat_id]
    try:
        pr = requests.post(f"{wp_url}/wp-json/wp/v2/posts", json=payload, auth=(user, app_pw), timeout=30)
        if pr.ok:
            pid = pr.json().get("id")
            print("Đã tạo bản nháp ID:", pid)
            return pid
        else:
            print("Lỗi tạo bài:", pr.status_code, pr.text[:300])
    except Exception as e:
        print("Lỗi kết nối WordPress:", e)
    return None

def fetch_rss_items(urls: List[str], limit_per_feed: int = 5) -> List[Dict[str, Any]]:
    items = []
    try:
        import feedparser
    except Exception:
        print("feedparser chưa sẵn sàng. Cài đặt: pip install feedparser")
        return items
    for u in urls:
        try:
            d = feedparser.parse(u)
            for e in d.entries[:limit_per_feed]:
                title = e.get("title","").strip()
                summary = e.get("summary","").strip()
                link = e.get("link","").strip()
                content = summary or title
                items.append({"title": title, "content": content, "link": link})
        except Exception as ex:
            print("RSS lỗi:", u, ex)
    return items

def main():
    cfg = load_config()
    rss_items = fetch_rss_items(cfg.get("rss_sources", []), limit_per_feed=5)
    if not rss_items:
        rss_items = [{
            "title": "Chăm sóc mắt khi dùng máy tính: giảm khô mỏi hiệu quả",
            "content": "- Chớp mắt thường xuyên\n- Nghỉ 20-20-20\n- Giữ độ ẩm phòng\n- Vệ sinh bờ mi mỗi ngày\n\nNội dung mẫu.",
            "link": "https://vietyenltd.com"
        }]
    for item in rss_items:
        raw = f"{item['title']}\n\n{item['content']}"
        if not keyword_gate(raw):
            continue
        if not ai_health_gate(raw, cfg):
            continue
        images = pick_images(cfg, raw)
        html_doc = build_html(item["title"], item["content"], images, cfg)
        html_doc = inject_internal_link(html_doc, cfg, raw)
        wp_create_draft(item["title"], html_doc, cfg.get("tags_by_name", []), cfg)

if __name__ == "__main__":
    main()
