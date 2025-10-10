#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vietyen Bot v4.3.9
- FIX: Không lặp "Tóm tắt", bỏ lỗi \n\n; thân bài 700–1000 từ theo chủ đề.
- "Gợi ý từ chuyên gia" sinh riêng theo nội dung (không lặp câu mẫu).
- "Nguồn tham khảo": CHỈ còn link bài gốc.
- Miễn trừ: “Nội dung chỉ tham khảo, không thể thay thế tư vấn y khoa.”
- Tuỳ chọn làm đẹp tiêu đề bằng prefix (ví dụ: 🩺) qua config.
"""

import os, re, json, time, html, logging
from datetime import datetime, timezone
from typing import Any, Dict, List

import requests
import feedparser

WP_URL = os.getenv("WP_URL", "").rstrip("/")
WP_USER = os.getenv("WP_USERNAME", "")
WP_APP_PW = os.getenv("WP_APP_PASSWORD", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
session = requests.Session()
session.headers.update({"User-Agent": "VietyenBot/4.3.9"})

# ------------------- Utils -------------------

def load_config(path: str = "config.json") -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def slugify(text: str) -> str:
    text = re.sub(r"[\s\-]+", "-", re.sub(r"[^\w\s-]", "", text.lower())).strip("-")
    return text[:80]

def strip_tags(html_text: str) -> str:
    return re.sub(r"<[^>]+>", " ", html_text).replace("&nbsp;", " ").strip()

def word_count(html_text: str) -> int:
    return len(re.findall(r"\w+", strip_tags(html_text)))

# ------------------- OpenAI helper -------------------

def ai_chat(messages, model="gpt-4o-mini", max_tokens=1600, temperature=0.5) -> str:
    if not OPENAI_API_KEY:
        raise RuntimeError("Missing OPENAI_API_KEY")
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
    r = session.post(url, headers=headers, json=payload, timeout=60)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()

# ------------------- AI steps -------------------

def classify_health(title: str, cfg: Dict[str, Any]) -> float:
    """Return probability the topic is health-related."""
    ai_cfg = cfg.get("ai_check", {"enabled": True, "model": "gpt-4o-mini", "threshold": 0.6})
    if not ai_cfg.get("enabled", True):
        return 0.99
    prompt = (
        "Chấm điểm 0-1 bài viết sau có thuộc lĩnh vực y tế/sức khỏe (lâm sàng, dinh dưỡng, phòng bệnh) hay không. "
        "Chỉ trả về JSON hợp lệ dạng {\"p_health\": number}.\n"
        f"Tiêu đề: {title}"
    )
    raw = ai_chat([{"role": "user", "content": prompt}], model=ai_cfg.get("model", "gpt-4o-mini"), max_tokens=32, temperature=0)
    m = re.search(r'"p_health"\s*:\s*([0-9.]+)', raw)
    return float(m.group(1)) if m else 0.0

def generate_article_json(title: str, source_excerpt: str, source_url: str, cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ask AI to return strict JSON for: summary, body_html (~850 words), expert_tips (3–5).
    We fully control rendering to avoid duplicates and style issues.
    """
    sys = (
        "Bạn là biên tập viên trang tin y tế Việt Nam. Viết nghiêm túc, thân thiện, đúng chính tả."
        " Tuyệt đối KHÔNG chèn CSS/inline style."
    )
    user = (
        "Hãy viết lại nội dung theo cấu trúc JSON **duy nhất** như sau:\n"
        "{\n"
        "  \"summary\": \"60-90 từ, 1 đoạn, không xuống dòng, không chứa ký tự \\n\",\n"
        "  \"body_html\": \"bài viết 700-1000 từ về chủ đề, chia 4-7 đoạn <p>...</p>, KHÔNG lặp lại phần summary\",\n"
        "  \"expert_tips\": [\"gợi ý thực hành 1\", \"gợi ý 2\", \"gợi ý 3\"],\n"
        "  \"keywords\": [\"tối đa 6 từ khóa\"]\n"
        "}\n\n"
        f"Tiêu đề gốc: {title}\n\n"
        f"Trích nội dung nguồn: {source_excerpt[:2200]}\n\n"
        f"Link gốc: {source_url}\n"
        "- Lưu ý: 'expert_tips' phải liên quan trực tiếp tới chủ đề bài.\n"
        "- Không thêm lời mở đầu/ghi chú ngoài JSON. Trả về JSON hợp lệ duy nhất."
    )
    model = cfg.get("ai_check", {}).get("model", "gpt-4o-mini")
    raw = ai_chat([{"role": "system", "content": sys}, {"role": "user", "content": user}], model=model, max_tokens=1800, temperature=0.6)

    # Try to extract JSON robustly
    jtxt = raw
    m = re.search(r"\{.*\}", raw, flags=re.S)
    if m: jtxt = m.group(0)
    data = json.loads(jtxt)

    # Post-fix: sanitize summary \n and spaces
    data["summary"] = re.sub(r"\s+", " ", str(data.get("summary", "")).replace("\\n", " ")).strip()
    # Ensure body length target
    wc = word_count(data.get("body_html", ""))
    if wc < 700 or wc > 1100:
        target = 850
        adjust = "mở rộng" if wc < 700 else "rút gọn"
        fix_user = (
            f"Bài body hiện {wc} từ, hãy {adjust} thành khoảng {target} từ, giữ nguyên nội dung và cấu trúc đoạn.\n"
            "Trả về CHỈ phần body_html (HTML gồm <p>…</p>), không lặp lại summary hay expert_tips."
        )
        fixed = ai_chat(
            [{"role": "system", "content": "Bạn là biên tập viên y tế, chỉnh sửa độ dài nội dung."},
             {"role": "user", "content": strip_tags(data.get("body_html", "")) + "\n\n" + fix_user}],
            model=model, max_tokens=1400, temperature=0.5
        )
        # keep only paragraph HTML
        mm = re.findall(r"<p>.*?</p>", fixed, flags=re.S|re.I)
        if mm:
            data["body_html"] = "\n".join(mm)
    return data

# ------------------- WordPress REST -------------------

def wp_auth() -> Dict[str, str]:
    from base64 import b64encode
    token = b64encode(f"{WP_USER}:{WP_APP_PW}".encode()).decode()
    return {"Authorization": f"Basic {token}"}

def wp_find_similar(slug: str) -> List[str]:
    url = f"{WP_URL}/wp-json/wp/v2/posts?status=draft,pending,publish&search={slug}&per_page=5"
    r = session.get(url, headers=wp_auth(), timeout=20)
    if r.ok:
        try: return [p.get("slug", "") for p in r.json()]
        except Exception: return []
    return []

def wp_create_post(title: str, content: str, excerpt: str, categories=None, status="draft") -> Dict[str, Any]:
    payload = {"title": title, "content": content, "excerpt": excerpt, "status": status}
    if categories: payload["categories"] = categories
    url = f"{WP_URL}/wp-json/wp/v2/posts"
    r = session.post(url, headers={**wp_auth(), "Content-Type": "application/json"}, json=payload, timeout=45)
    r.raise_for_status()
    return r.json()

# ------------------- Compose HTML -------------------

def compose_html(data: Dict[str, Any], source_url: str, cfg: Dict[str, Any]) -> (str, str):
    """
    Build final HTML with sections:
    - Tóm tắt (once only)
    - Body (from AI JSON)
    - Gợi ý từ chuyên gia
    - Nguồn tham khảo (link only)
    - Miễn trừ trách nhiệm (fixed text)
    - JSON-LD (minimal)
    """
    summary = data.get("summary", "")
    body_html = data.get("body_html", "")
    tips = [t for t in data.get("expert_tips", []) if t.strip()]

    # 1) Summary block (only once)
    html_summary = (
        '<h2>Tóm tắt</h2>'
        f'<p>{html.escape(summary)}</p>'
    )

    # 2) Body (already HTML paragraphs). Ensure it does NOT echo summary:
    body_plain = strip_tags(body_html)
    if summary and summary[:80] in body_plain[: max(len(summary), 200)]:
        # remove first paragraph if duplicating summary
        body_html = re.sub(r"^<p>.*?</p>\s*", "", body_html, flags=re.S)

    # 3) Expert tips
    tips_li = "".join(f"<li>{html.escape(t)}</li>" for t in tips[:5])
    html_tips = f"<h2>Gợi ý từ chuyên gia</h2><ul>{tips_li}</ul>" if tips_li else ""

    # 4) Source + Disclaimer
    html_source = f"<h2>Nguồn tham khảo</h2><ul><li><a href=\"{source_url}\">{source_url}</a></li></ul>"
    html_disclaimer = "<p><em>Miễn trừ trách nhiệm: Nội dung chỉ tham khảo, không thể thay thế tư vấn y khoa.</em></p>"

    # 5) JSON-LD (minimal)
    json_ld = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": "",  # set later at create_post
        "datePublished": datetime.now(timezone.utc).isoformat(),
        "mainEntityOfPage": source_url,
        "publisher": {
            "@type": "Organization",
            "name": cfg.get("brand", {}).get("publisher", "Công ty TNHH Thương Mại Việt Yến"),
            "logo": {"@type": "ImageObject", "url": cfg.get("brand", {}).get("logo_url", "")}
        }
    }
    json_ld_tag = f"<script type=\"application/ld+json\">{json.dumps(json_ld, ensure_ascii=False)}</script>"

    final_html = "\n".join([html_summary, body_html, html_tips, html_source, html_disclaimer, json_ld_tag]).strip()
    excerpt = summary[:300]
    return final_html, excerpt

# ------------------- Category mapping -------------------

def map_categories(title: str, cfg: Dict[str, Any]):
    cats = cfg.get("categories", [])
    t = title.lower()
    selected = []
    for c in cats:
        for kw in c.get("keywords", []):
            if kw.lower() in t:
                if c.get("id"): selected.append(int(c["id"]))
                break
    # unique keep order
    out, seen = [], set()
    for x in selected:
        if x not in seen:
            out.append(x); seen.add(x)
    return out[:3] or None

# ------------------- Main -------------------

def run():
    assert WP_URL and WP_USER and WP_APP_PW, "Missing WP_* secrets"
    cfg = load_config()
    feeds = cfg.get("rss_sources", [])
    if not feeds:
        logging.error("No RSS sources configured.")
        return

    picked = None
    for feed_url in feeds:
        d = feedparser.parse(feed_url)
        for e in d.entries[:10]:
            title = html.unescape(e.get("title", "").strip())
            link = e.get("link", "").strip()
            summary = html.unescape(e.get("summary", e.get("description", "")).strip())
            if not (title and link): continue
            if classify_health(title, cfg) < float(cfg.get("ai_check", {}).get("threshold", 0.6)): 
                continue
            picked = (title, summary, link); break
        if picked: break

    if not picked:
        logging.warning("No suitable item today.")
        return

    title, src_excerpt, link = picked
    slug = slugify(title)
    if slug in wp_find_similar(slug):
        logging.info("Similar post exists. Abort.")
        return

    # ---- Generate JSON article and compose HTML
    data = generate_article_json(title, src_excerpt, link, cfg)
    content_html, excerpt = compose_html(data, link, cfg)

    # ---- Title handling (keep original by default; optional pretty prefix)
    pretty_prefix = cfg.get("title_style", {}).get("prefix", "")  # e.g., "🩺 "
    mode = cfg.get("title_style", {}).get("mode", "original")     # "original" | "prefixed"
    final_title = (pretty_prefix + title) if (pretty_prefix and mode == "prefixed") else title

    # ---- Category mapping
    cat_ids = map_categories(title, cfg)

    # ---- Create draft post
    post = wp_create_post(final_title, content_html, excerpt, categories=cat_ids, status=cfg.get("post", {}).get("status", "draft"))
    logging.info(f"Draft created: {post.get('link')} (ID {post.get('id')})")

# -------------------

def wp_create_post(title: str, content: str, excerpt: str, categories=None, status="draft") -> Dict[str, Any]:
    payload = {"title": title, "content": content, "excerpt": excerpt, "status": status}
    if categories: payload["categories"] = categories
    url = f"{WP_URL}/wp-json/wp/v2/posts"
    r = session.post(url, headers={**wp_auth(), "Content-Type": "application/json"}, json=payload, timeout=45)
    r.raise_for_status()
    return r.json()

def wp_auth() -> Dict[str, str]:
    from base64 import b64encode
    token = b64encode(f"{WP_USER}:{WP_APP_PW}".encode()).decode()
    return {"Authorization": f"Basic {token}"}

if __name__ == "__main__":
    try:
        run()
    except Exception as ex:
        logging.exception(ex)
        raise
