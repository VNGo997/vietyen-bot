
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vietyen-bot v4.3.6
- AI viết lại bài đầy đủ (tiếng Việt tự nhiên) từ RSS chính thống
- AI tạo "Tóm tắt ngắn gọn" theo ngữ cảnh từng bài
- AI tạo "Gợi ý từ chuyên gia" theo nội dung đã viết lại
- Bỏ mục "Nguồn bài gốc"; thay bằng chèn link nguồn vào "Nguồn tham khảo"
- Giữ: AI check, SEO + JSON-LD, 1 bài/ngày, draft mode, UI Visionary
"""
import os, re, json, html, random, requests, unicodedata, datetime
from typing import List, Dict, Any, Optional

try:
    import feedparser
except Exception:
    pass

CONFIG_PATH = os.environ.get("BOT_CONFIG_PATH", "config.json")

TAG_RE = re.compile(r"<[^>]+>")
IMG_RE = re.compile(r'<img[^>]+src="([^"]+)"', re.IGNORECASE)

def strip_html(raw_html: str) -> str:
    if not raw_html: return ""
    cleaned = re.sub(r"<(script|style)[^>]*>.*?</\\1>", "", raw_html, flags=re.I|re.S)
    text = TAG_RE.sub("", cleaned)
    text = re.sub(r"\\s+\\n", "\\n", text)
    text = re.sub(r"\\n{3,}", "\\n\\n", text).strip()
    return text

def first_img_src(raw_html: str) -> Optional[str]:
    if not raw_html: return None
    m = IMG_RE.search(raw_html)
    return m.group(1) if m else None

def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def keyword_gate(text):
    t = text.lower()
    keys = ["sức khỏe","y tế","bệnh","điều trị","dự phòng","triệu chứng","chẩn đoán",
            "nhãn khoa","bờ mi","khô mắt","viêm","thuốc","bác sĩ","bệnh viện",
            "phòng bệnh","vaccine","dinh dưỡng","tim mạch","da liễu","nhi khoa","cấp cứu","đa chấn thương"]
    return any(k in t for k in keys)

def ai_health_gate(text, cfg):
    s = cfg.get("ai_check", {})
    if not s.get("enabled"): return True
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key: return keyword_gate(text)
    try:
        r = requests.post("https://api.openai.com/v1/chat/completions",
            headers={"Authorization": "Bearer {}".format(api_key), "Content-Type": "application/json"},
            json={
                "model": s.get("model", "gpt-4o-mini"),
                "messages": [
                    {"role": "system", "content": "Answer Y or N only."},
                    {"role": "user", "content": s.get("prompt","") + "\\n\\n" + text[:6000]}
                ],
                "temperature": 0
            }, timeout=30)
        ans = r.json()["choices"][0]["message"]["content"].strip().upper()
        return ans.startswith("Y")
    except Exception:
        return keyword_gate(text)

# -------- AI helpers --------
def call_openai(messages, model="gpt-4o-mini", temperature=0.4, timeout=45):
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        r = requests.post("https://api.openai.com/v1/chat/completions",
            headers={"Authorization": "Bearer {}".format(api_key), "Content-Type":"application/json"},
            json={"model": model, "messages": messages, "temperature": temperature},
            timeout=timeout)
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        return None

def ai_compose_full_article(title: str, source_text: str) -> str:
    """
    Viết lại toàn bộ bài theo phong cách Visionary.
    Nếu không có API key, dùng fallback mở rộng nội dung an toàn.
    """
    sys = "Bạn là biên tập viên y tế viết tiếng Việt tự nhiên, chính xác, tôn trọng nguồn."
    user = (
        "Viết lại TOÀN BỘ BÀI theo phong cách Visionary (y tế):\\n"
        "- Không trùng lặp; không bịa chi tiết; chỉ dựa trên nội dung đã cho.\\n"
        "- Bố cục: Mở bài (1 đoạn) → Bối cảnh/Tình huống (1–2 đoạn) → Thông tin y khoa/cách xử trí (1–2 đoạn) → Lời khuyên thực tế (1 đoạn) → Kết (1 đoạn).\\n"
        "- Giọng văn tự nhiên, thân thiện, tránh giật tít.\\n"
        "Tiêu đề nguồn: {title}\\n\\nTóm tắt/đoạn trích nguồn:\\n{src}"
    ).format(title=title, src=source_text[:2000])
    out = call_openai(
        [{"role":"system","content":sys},{"role":"user","content":user}]
    )
    if out: return out
    # Fallback (không API): nới rộng phần tóm tắt thành 3–4 đoạn
    parts = source_text.split("\\n")
    intro = "Bài viết sau đây được tóm lược từ nguồn chính thống, trình bày theo ngôn ngữ dễ hiểu."
    detail = source_text
    conclude = "Các thông tin chỉ mang tính tham khảo, người đọc nên tìm đến cơ sở y tế khi cần."
    return intro + "\\n\\n" + detail + "\\n\\n" + conclude

def ai_summary(title: str, full_text: str) -> str:
    """Sinh tóm tắt 1–2 câu theo ngữ cảnh bài viết."""
    user = (
        "Tóm tắt ngắn gọn (1–2 câu) nội dung bài dưới đây, tiếng Việt tự nhiên, không dùng thuật ngữ khó.\\n"
        "Tiêu đề: {t}\\n\\nNội dung:\\n{c}"
    ).format(t=title, c=full_text[:2500])
    out = call_openai(
        [{"role":"system","content":"Bạn là biên tập viên y tế tóm tắt súc tích."},
         {"role":"user","content":user}], temperature=0.3, timeout=30
    )
    if out: return out
    # Fallback: lấy 1–2 câu đầu
    sents = re.split(r"[\\.!?]\\s", full_text.strip())
    return (sents[0] + (". " + sents[1] if len(sents)>1 else "")).strip()

def ai_expert_tip_from_full(full_text: str, link_rule: Optional[Dict[str,str]]) -> str:
    """Sinh gợi ý từ chuyên gia dựa trên bài đã viết lại."""
    extra = " Sản phẩm gợi ý: {}".format(link_rule.get("title")) if link_rule else ""
    user = (
        "Dựa trên nội dung sau, hãy viết 3–5 câu lời khuyên thực tế, an toàn, dễ làm cho người đọc. Tránh phóng đại.{extra}\\n\\n{c}"
        .format(extra=extra, c=full_text[:2500])
    )
    out = call_openai(
        [{"role":"system","content":"Bạn là chuyên gia y tế tư vấn ngắn gọn, thực tế."},
         {"role":"user","content":user}], temperature=0.35, timeout=30
    )
    if out: return html.escape(out.strip())
    # Fallback an toàn
    tip = "Duy trì lối sống điều độ, theo dõi triệu chứng và ưu tiên chăm sóc tại nhà. Nếu không cải thiện, hãy liên hệ bác sĩ."
    if link_rule: tip += " Có thể cân nhắc sản phẩm hỗ trợ: {}".format(html.escape(link_rule.get("title")))
    return tip

# -------- SEO helpers --------
def slugify(value: str) -> str:
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^a-zA-Z0-9\\-\\s]', '', value).strip().lower()
    value = re.sub(r'[\\s\\-]+', '-', value)
    return value[:80].strip('-') or 'bai-viet-suc-khoe'

def gen_seo(title: str, body: str) -> Dict[str, str]:
    base_title = title.strip()
    if len(base_title) > 60: base_title = base_title[:57].rstrip() + "..."
    sentences = re.split(r'[\\.!?]\\s', body)
    first = (sentences[0] or "").strip()
    if len(first) < 50 and len(sentences) > 1: first += ". " + sentences[1].strip()
    desc = first[:157].rstrip() + "..." if len(first) > 160 else first
    words = re.findall(r"[a-zA-ZÀ-ỹ0-9]{4,}", (title + " " + body).lower())
    common = {"và","cho","của","khi","bị","về","trong","được","bệnh","sức","khỏe","người","bài","viết","này","các","một"}
    uniq = []
    for w in words:
        if w in common: continue
        if w not in uniq: uniq.append(w)
    keywords = ", ".join(uniq[:8])
    return {"seo_title": base_title, "seo_desc": desc, "seo_keywords": keywords, "seo_slug": slugify(title)}

def jsonld_article(cfg, title, desc, url, img):
    site = cfg.get("brand",{}).get("site_name","VietYenLTD Health Desk")
    logo = cfg.get("brand",{}).get("publisher_logo","")
    data = {
      "@context": "https://schema.org",
      "@type": "NewsArticle",
      "headline": title,
      "description": desc,
      "image": [img] if img else [],
      "datePublished": datetime.datetime.utcnow().isoformat() + "Z",
      "author": {"@type":"Organization","name": site},
      "publisher": {"@type":"Organization","name": site, "logo":{"@type":"ImageObject","url": logo}},
      "mainEntityOfPage": url or ""
    }
    import json as _json
    return '<script type="application/ld+json">{}</script>'.format(_json.dumps(data, ensure_ascii=False))

# -------- UI builder --------
def build_html(title, summary_text, full_text, hero_img, cfg, expert_tip_html, rule, source_url=None, seo=None):
    cap = "Ảnh minh hoạ: Unsplash"
    expert = '<div style="margin:26px 0;background:linear-gradient(135deg,#004aad,#0b73d5);color:#fff;border-radius:12px;padding:18px;"><div style="font-size:18px;font-weight:700;margin-bottom:6px">💬 Gợi ý từ chuyên gia</div><div style="line-height:1.7">{}</div>'.format(expert_tip_html)
    if rule:
        expert += '<div style="margin-top:10px">🌐 Tham khảo: <a href="{}" style="color:#ffe07a;text-decoration:underline">{}</a></div>'.format(html.escape(rule["url"]), html.escape(rule["title"]))
    expert += '</div>'
    # Footer: chỉ còn "Nguồn tham khảo" + miễn trừ; chèn link nguồn tại đây
    ref = ' <a href="{}" target="_blank" rel="noopener">Xem bài gốc</a>'.format(html.escape(source_url)) if source_url else ""
    footer = '<div style="border:1px solid #e8eefc;border-radius:12px;padding:14px 16px;background:#fbfdff;margin-top:24px"><p><span style="color:#004aad">🔗 Nguồn tham khảo:</span> Tổng hợp từ các nguồn chính thống về sức khỏe.{}.</p><p style="color:#667;font-size:14px">⚠️ <strong>Miễn trừ trách nhiệm:</strong> Nội dung chỉ tham khảo, không thay thế tư vấn y khoa.</p></div>'.format(ref)

    # Convert paragraphs
    body_html = "<p>{}</p>".format(html.escape(full_text).replace("\\n\\n","</p><p>").replace("\\n","<br>"))
    sum_html = html.escape(summary_text)

    html_doc = "<figure><img src='{}' style='width:100%;border-radius:14px;'><figcaption>{}</figcaption></figure>".format(hero_img, cap)
    html_doc += "<div style='background:linear-gradient(90deg,#eaf2ff,#f7fbff);border:1px solid #d9e7ff;border-radius:12px;padding:14px 16px;margin:16px 0'><strong style='color:#004aad'>🩺 Tóm tắt ngắn gọn:</strong> {}</div>".format(sum_html)
    html_doc += body_html + expert + footer
    if seo:
        html_doc += jsonld_article(cfg, seo.get("seo_title",title), seo.get("seo_desc",""), "", hero_img)
    return html_doc

# -------- WP --------
def wp_create_draft(title, content, tags, cfg, seo=None):
    wp = os.environ.get("WP_URL","").rstrip("/")
    u = os.environ.get("WP_USERNAME")
    pw = os.environ.get("WP_APP_PASSWORD")
    if not (wp and u and pw):
        print("Thiếu thông tin WordPress."); return None
    try:
        ids = []
        for t in tags:
            r=requests.get("{}/wp-json/wp/v2/tags".format(wp),params={"search":t,"per_page":1},auth=(u,pw),timeout=20)
            if r.ok and r.json(): ids.append(r.json()[0]["id"])
            else:
                cr=requests.post("{}/wp-json/wp/v2/tags".format(wp),json={"name":t},auth=(u,pw),timeout=20)
                if cr.ok: ids.append(cr.json()["id"])
        payload={"title": seo.get("seo_title",title) if seo else title,
                 "content": content,
                 "status": "draft",
                 "tags": ids}
        if seo:
            payload["excerpt"] = seo.get("seo_desc","")
            payload["slug"] = seo.get("seo_slug","")
        cat_id = cfg.get("category_id")
        if cat_id: payload["categories"] = [cat_id]
        c=requests.post("{}/wp-json/wp/v2/posts".format(wp),json=payload,auth=(u,pw),timeout=30)
        if c.ok: print("Đã tạo bản nháp ID:",c.json().get("id"))
        else: print("Lỗi tạo bài:",c.status_code,c.text[:300])
    except Exception as e: print("Lỗi WP:",e)

# -------- RSS --------
def fetch_rss(urls):
    try: import feedparser
    except: return []
    out=[]
    for u in urls:
        try:
            d=feedparser.parse(u)
            for e in d.entries[:10]:
                title=e.get("title","").strip()
                summary_html=e.get("summary","").strip()
                link=e.get("link","").strip()
                text=strip_html(summary_html) or title
                img=first_img_src(summary_html)
                out.append({"title":title,"content_text":text,"link":link,"rss_img":img})
        except Exception: pass
    return out

# -------- Main --------
def main():
    cfg=load_config()
    items=fetch_rss(cfg.get("rss_sources",[]))
    ok=[i for i in items if keyword_gate(i["title"]+" "+i["content_text"]) and ai_health_gate(i["title"]+" "+i["content_text"],cfg)]
    if not ok: print("Không có bài hợp lệ."); return
    c=random.choice(ok)
    hero_img=(c.get("rss_img") or cfg.get("default_hero_url"))
    # 1) Viết lại toàn bộ bài
    full_text=ai_compose_full_article(c["title"], c["content_text"])
    # 2) Tóm tắt ngắn gọn theo ngữ cảnh
    summary=ai_summary(c["title"], full_text)
    # 3) Nội liên kết + gợi ý chuyên gia theo nội dung đã viết
    rule=None
    for r in cfg.get("internal_links", []):
        if any(k in full_text.lower() for k in r.get("keywords", [])): rule=r; break
    expert_tip=ai_expert_tip_from_full(full_text, rule)
    # 4) SEO
    seo=gen_seo(c["title"], full_text)
    # 5) Build HTML (không có "Nguồn bài gốc"; link nằm trong "Nguồn tham khảo")
    html_doc=build_html(c["title"], summary, full_text, hero_img, cfg, expert_tip, rule, source_url=c.get("link"), seo=seo)
    # 6) Đăng nháp
    wp_create_draft(c["title"], html_doc, cfg.get("tags_by_name", []), cfg, seo=seo)

if __name__=="__main__": main()
