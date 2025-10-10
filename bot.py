
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vietyen-bot v4.3.4
- Thêm SEO: title rút gọn, meta description, keywords, slug, JSON-LD (Article)
- Giữ: AI check, Expert Tip AI, 1 bài/ngày, UI Visionary, draft mode
"""
import os, re, json, html, random, requests, datetime, unicodedata
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
            "phòng bệnh","vaccine","dinh dưỡng","tim mạch","da liễu","nhi khoa"]
    return any(k in t for k in keys)

def ai_health_gate(text, cfg):
    s = cfg.get("ai_check", {})
    if not s.get("enabled"): return True
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key: return keyword_gate(text)
    try:
        r = requests.post("https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
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

def ai_expert_tip(title, text, cfg, link_rule):
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key: return fallback_tip(link_rule)
    try:
        cta = "Sản phẩm gợi ý: {}".format(link_rule.get('title')) if link_rule else ""
        prompt = "Bạn là chuyên gia y tế, viết 3–5 câu khuyên ngắn thực tế, tiếng Việt, dễ hiểu. {}\\n\\nTiêu đề: {}\\n\\nNội dung: {}".format(cta, title, text[:1200])
        r = requests.post("https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": cfg.get("ai_check",{}).get("model","gpt-4o-mini"),
                "messages":[{"role":"user","content":prompt}],
                "temperature":0.4
            },timeout=30)
        return html.escape(r.json()["choices"][0]["message"]["content"].strip())
    except Exception:
        return fallback_tip(link_rule)

def fallback_tip(rule):
    t = "Duy trì lối sống điều độ, theo dõi triệu chứng và ưu tiên chăm sóc tại nhà. Nếu không cải thiện, hãy liên hệ bác sĩ."
    if rule: t += " Sản phẩm hỗ trợ như {} có thể giúp cải thiện hiệu quả.".format(html.escape(rule.get('title')))
    return t

def pick_images(cfg, text, rss_img=None):
    if rss_img: return [rss_img]
    t = text.lower()
    for tp in cfg.get("topics", []):
        if any(k in t for k in tp.get("match", [])): return tp.get("fallback_images", [])
    return [cfg.get("default_hero_url")]

def find_link_rule(cfg, text):
    t = text.lower()
    for r in cfg.get("internal_links", []):
        if any(k in t for k in r.get("keywords", [])): return r
    return None

# -------- SEO helpers --------
def slugify(value: str) -> str:
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^a-zA-Z0-9\\-\\s]', '', value).strip().lower()
    value = re.sub(r'[\\s\\-]+', '-', value)
    return value[:80].strip('-') or 'bai-viet-suc-khoe'

def gen_seo(title: str, body: str) -> Dict[str, str]:
    # title <= 60 chars, desc <= 160
    base_title = title.strip()
    if len(base_title) > 60:
        base_title = base_title[:57].rstrip() + "..."
    # simple description from first sentence
    sentences = re.split(r'[\\.!?]\\s', body)
    first = (sentences[0] or "").strip()
    if len(first) < 50 and len(sentences) > 1:
        first += ". " + sentences[1].strip()
    desc = first[:157].rstrip() + "..." if len(first) > 160 else first
    # keywords: pick top nouns-ish by simple heuristics
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

# -------- UI --------
def build_html(title, body_text, imgs, cfg, tip_html, rule, source_url=None, seo=None):
    hero = imgs[0] if imgs else cfg.get("default_hero_url")
    cap = "Ảnh minh hoạ: Unsplash"
    bullets = re.findall(r"^[\\-\\–•]\\s*(.+)$", body_text, flags=re.M)
    li = ''.join(["<li>✅ {}</li>".format(html.escape(b)) for b in bullets[:6]]) if bullets else ""
    expert = '<div style="margin:26px 0;background:linear-gradient(135deg,#004aad,#0b73d5);color:#fff;border-radius:12px;padding:18px;"><div style="font-size:18px;font-weight:700;margin-bottom:6px">💬 Gợi ý từ chuyên gia</div><div style="line-height:1.7">{}</div>'.format(tip_html)
    if rule:
        expert += '<div style="margin-top:10px">🌐 Tham khảo: <a href="{}" style="color:#ffe07a;text-decoration:underline">{}</a></div>'.format(html.escape(rule["url"]), html.escape(rule["title"]))
    expert += '</div>'
    footer = '<div style="border:1px solid #e8eefc;border-radius:12px;padding:14px 16px;background:#fbfdff;margin-top:24px"><p><span style="color:#004aad">🔗 Nguồn tham khảo:</span> Tổng hợp từ các nguồn chính thống về sức khỏe.</p><p style="color:#667;font-size:14px">⚠️ <strong>Miễn trừ trách nhiệm:</strong> Nội dung chỉ tham khảo, không thay thế tư vấn y khoa.</p></div>'
    if source_url:
        footer = '<p style="margin-top:14px">📎 Nguồn bài gốc: <a href="{}" target="_blank" rel="noopener">Xem tại đây</a></p>'.format(html.escape(source_url)) + footer

    body_html = "<p>{}</p>".format(html.escape(body_text).replace("\\n\\n","</p><p>").replace("\\n","<br>"))
    html_doc = "<figure><img src='{}' style='width:100%;border-radius:14px;'><figcaption>{}</figcaption></figure>".format(hero, cap)
    html_doc += "<div style='background:linear-gradient(90deg,#eaf2ff,#f7fbff);border:1px solid #d9e7ff;border-radius:12px;padding:14px 16px;margin:16px 0'><strong style='color:#004aad'>🩺 Tóm tắt ngắn gọn:</strong> Bài viết sức khỏe biên tập theo chuẩn Visionary.</div>"
    if li:
        html_doc += "<h2>💡 Điều bạn cần lưu ý</h2><ul style='list-style:none;padding-left:0'>{}</ul>".format(li)
    html_doc += body_html + expert + footer
    # Append JSON-LD
    if seo:
        html_doc += jsonld_article(cfg, seo.get("seo_title",title), seo.get("seo_desc",""), "", hero)
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
    imgs=pick_images(cfg,c["content_text"],rss_img=c.get("rss_img"))
    rule=find_link_rule(cfg,c["content_text"])
    tip=ai_expert_tip(c["title"],c["content_text"],cfg,rule)
    seo=gen_seo(c["title"], c["content_text"])
    html_doc=build_html(c["title"],c["content_text"],imgs,cfg,tip,rule,source_url=c.get("link"),seo=seo)
    wp_create_draft(c["title"],html_doc,cfg.get("tags_by_name",[]),cfg,seo=seo)

if __name__=="__main__": main()
