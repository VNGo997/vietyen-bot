#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vietyen-bot v4.3.3
- Giữ nguyên workflow 4.2b
- Có AI check + Expert Tip AI + 1 bài/ngày + Visionary UI
- Có wordpress_connection.py tương thích
"""
import os, re, json, html, random, requests
from typing import List, Dict, Any, Optional

try:
    import feedparser
except Exception:
    pass

CONFIG_PATH = os.environ.get("BOT_CONFIG_PATH", "config.json")

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
                    {"role": "user", "content": s.get("prompt","") + "\n\n" + text[:6000]}
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
        cta = f"Sản phẩm gợi ý: {link_rule.get('title')}" if link_rule else ""
        prompt = f"Bạn là chuyên gia y tế, viết 3–5 câu khuyên ngắn thực tế, tiếng Việt, dễ hiểu. {cta}\n\nTiêu đề: {title}\n\nNội dung: {text[:1200]}"
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
    if rule: t += f" Sản phẩm hỗ trợ như {html.escape(rule.get('title'))} có thể giúp cải thiện hiệu quả."
    return t

def pick_images(cfg, text):
    t = text.lower()
    for tp in cfg.get("topics", []):
        if any(k in t for k in tp.get("match", [])): return tp["fallback_images"]
    return [cfg.get("default_hero_url")]

def find_link_rule(cfg, text):
    t = text.lower()
    for r in cfg.get("internal_links", []):
        if any(k in t for k in r.get("keywords", [])): return r
    return None

def build_html(title, body, imgs, cfg, tip_html, rule):
    hero = imgs[0] if imgs else cfg.get("default_hero_url")
    mid = imgs[1] if len(imgs)>1 else None
    cap = "Ảnh minh hoạ: Unsplash"
    bullets = re.findall(r"^[\-–•]\s*(.+)$", body, flags=re.M)
    li = ''.join([f"<li>✅ {html.escape(b)}</li>" for b in bullets[:6]]) if bullets else ""
    mid_html = f'<figure><img src="{mid}" style="width:100%;border-radius:14px;"><figcaption>{cap}</figcaption></figure>' if mid else ""
    expert = f'<div style="margin:26px 0;background:linear-gradient(135deg,#004aad,#0b73d5);color:#fff;border-radius:12px;padding:18px;"><div style="font-size:18px;font-weight:700;margin-bottom:6px">💬 Gợi ý từ chuyên gia</div><div style="line-height:1.7">{tip_html}</div>'
    if rule:
        expert += f'<div style="margin-top:10px">🌐 Tham khảo: <a href="{html.escape(rule["url"])}" style="color:#ffe07a;text-decoration:underline">{html.escape(rule["title"])}</a></div>'
    expert += '</div>'
    footer = '<div style="border:1px solid #e8eefc;border-radius:12px;padding:14px 16px;background:#fbfdff;margin-top:24px"><p><span style="color:#004aad">🔗 Nguồn tham khảo:</span> Tổng hợp từ các nguồn chính thống về sức khỏe.</p><p style="color:#667;font-size:14px">⚠️ <strong>Miễn trừ trách nhiệm:</strong> Nội dung chỉ tham khảo, không thay thế tư vấn y khoa.</p></div>'
    html_doc = f'''<figure><img src="{hero}" style="width:100%;border-radius:14px;"><figcaption>{cap}</figcaption></figure>
<div style="background:linear-gradient(90deg,#eaf2ff,#f7fbff);border:1px solid #d9e7ff;border-radius:12px;padding:14px 16px;margin:16px 0"><strong style="color:#004aad">🩺 Tóm tắt ngắn gọn:</strong> Bài viết sức khỏe biên tập theo chuẩn Visionary.</div>
{('<h2>💡 Điều bạn cần lưu ý</h2><ul>'+li+'</ul>') if li else ''}
{mid_html}<div>{html.escape(body).replace("\n","<br>")}</div>{expert}{footer}'''
    return html_doc

def wp_create_draft(title, content, tags, cfg):
    wp = os.environ.get("WP_URL","").rstrip("/")
    u = os.environ.get("WP_USERNAME")
    pw = os.environ.get("WP_APP_PASSWORD")
    if not (wp and u and pw):
        print("Thiếu thông tin WordPress."); return None
    try:
        ids = []
        for t in tags:
            r=requests.get(f"{wp}/wp-json/wp/v2/tags",params={"search":t,"per_page":1},auth=(u,pw))
            if r.ok and r.json(): ids.append(r.json()[0]["id"])
            else:
                cr=requests.post(f"{wp}/wp-json/wp/v2/tags",json={"name":t},auth=(u,pw))
                if cr.ok: ids.append(cr.json()["id"])
        p={"title":title,"content":content,"status":"draft","tags":ids}
        c=requests.post(f"{wp}/wp-json/wp/v2/posts",json=p,auth=(u,pw))
        if c.ok: print("Đã tạo bản nháp ID:",c.json()["id"])
        else: print("Lỗi tạo bài:",c.status_code,c.text[:300])
    except Exception as e: print("Lỗi WP:",e)

def fetch_rss(urls):
    try: import feedparser
    except: return []
    out=[]
    for u in urls:
        try:
            d=feedparser.parse(u)
            for e in d.entries[:10]:
                t=e.get("title","").strip(); s=e.get("summary","").strip(); l=e.get("link","").strip()
                out.append({"title":t,"content":s or t,"link":l})
        except Exception: pass
    return out

def main():
    cfg=load_config()
    items=fetch_rss(cfg.get("rss_sources",[]))
    ok=[i for i in items if keyword_gate(i["title"]+" "+i["content"]) and ai_health_gate(i["title"]+" "+i["content"],cfg)]
    if not ok: print("Không có bài hợp lệ."); return
    c=random.choice(ok)
    imgs=pick_images(cfg,c["content"]); rule=find_link_rule(cfg,c["content"])
    tip=ai_expert_tip(c["title"],c["content"],cfg,rule)
    html_doc=build_html(c["title"],c["content"],imgs,cfg,tip,rule)
    wp_create_draft(c["title"],html_doc,cfg.get("tags_by_name",[]),cfg)

if __name__=="__main__": main()
