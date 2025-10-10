#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Vietyen Bot v4.3.7
# - Daily health-only draft posts from selected RSS.
# - AI classify -> rewrite -> enrich (summary + expert tips).
# - JSON-LD Article, internal links injection, category mapping.
# - WordPress REST (Application Password). Draft-only.

import os, re, json, time, hashlib, html
import logging
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests
import feedparser

WP_URL = os.getenv("WP_URL", "").rstrip("/")
WP_USER = os.getenv("WP_USERNAME", "")
WP_APP_PW = os.getenv("WP_APP_PASSWORD", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
session = requests.Session()
session.headers.update({"User-Agent": "VietyenBot/4.3.7"})

# ---------- Utils ----------

def load_config(path="config.json"):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def http_get(url, timeout=20):
    for i in range(3):
        try:
            r = session.get(url, timeout=timeout)
            if r.ok:
                return r.text
        except Exception as e:
            logging.warning(f"GET retry {i+1}/3: {e}")
        time.sleep(1.2 * (i + 1))
    return None


def slugify(text):
    text = re.sub(r"[\s\-]+", "-", re.sub(r"[^\w\s-]", "", text.lower())).strip("-")
    return text[:80]


def hash_of(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


# ---------- OpenAI helpers ----------
def ai_chat(messages, model="gpt-4o-mini", max_tokens=1200, temperature=0.4):
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY missing")
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    r = session.post(url, headers=headers, json=payload, timeout=45)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


def classify_health(topic, cfg):
    if not cfg.get("ai_check", {}).get("enabled", False):
        return 0.99
    model = cfg["ai_check"].get("model", "gpt-4o-mini")
    prompt = (
        "Bạn là bộ phân loại chủ đề. Trả lời một số thực giữa 0-1 theo dạng JSON {\"p_health\": float}.\n"
        "Câu hỏi: Bài viết sau có thuộc lĩnh vực y tế/sức khoẻ cộng đồng, lâm sàng, dinh dưỡng, phòng bệnh không?\n"
        f"Tiêu đề: {topic}\n"
        "Chỉ trả về JSON hợp lệ."
    )
    msg = [{"role": "user", "content": prompt}]
    try:
        raw = ai_chat(msg, model=model, max_tokens=20, temperature=0)
        m = re.search(r"\{\s*\\"p_health\\"\s*:\s*([0-9.]+)\s*\}", raw)
        return float(m.group(1)) if m else 0.0
    except Exception as e:
        logging.warning(f"Classifier error: {e}")
        return 0.0


def rewrite_and_enrich(title, body, source_url, cfg):
    brand = cfg.get("brand", {})
    author = brand.get("author", "Vietyen Health Desk")
    publisher = brand.get("publisher", "Vietyen")

    sys = (
        "Viết lại bài báo y tế bằng tiếng Việt tự nhiên, tránh trùng lặp, cấu trúc rõ ràng.\n"
        "Yêu cầu bắt buộc:\n- 1 đoạn tóm tắt ngắn (50–80 từ) mở đầu dưới tiêu đề phụ 'Tóm tắt'.\n"
        "- Thân bài 3–6 đoạn, mượt, không liệt kê khô cứng.\n- Mục 'Gợi ý từ chuyên gia' 3–5 gạch đầu dòng, thực hành được.\n"
        "- Cuối bài có mục 'Nguồn tham khảo' chứa liên kết bài gốc.\n"
        "- Không thêm khuyến nghị điều trị thay thế tư vấn bác sĩ.\n"
        "Trả về HTML thuần (không style inline)."
    )
    user = (
        f"Tiêu đề gốc: {title}\n\n"
        f"Nội dung gốc (rút trích):\n{body[:2500]}\n\n"
        f"Liên kết bài gốc: {source_url}\n"
    )
    messages = [
        {"role": "system", "content": sys},
        {"role": "user", "content": user}
    ]
    html_body = ai_chat(messages, model=cfg.get("ai_check", {}).get("model", "gpt-4o-mini"), max_tokens=1300)

    # Inject internal links (simple rule-based)
    html_body = inject_internal_links(html_body, cfg)

    # Build JSON-LD
    json_ld = build_jsonld(title, source_url, cfg)

    # Compose final content
    final_html = f"{html_body}\n\n<script type=\"application/ld+json\">{json_ld}</script>"
    # Extract excerpt from Tóm tắt block for WP excerpt
    excerpt = extract_excerpt(html_body)
    return final_html, excerpt, author, publisher


def extract_excerpt(html_body):
    m = re.search(r"<h2[^>]*>\s*Tóm\s*tắt\s*</h2>\s*<p>(.*?)</p>", html_body, flags=re.I|re.S)
    if m:
        text = re.sub(r"<[^>]+>", "", m.group(1))
        return text.strip()[:300]
    # Fallback: first paragraph
    m = re.search(r"<p>(.*?)</p>", html_body, flags=re.S)
    return re.sub(r"<[^>]+>", "", m.group(1)).strip()[:300] if m else ""


def inject_internal_links(html_body, cfg):
    links = cfg.get("internal_links", [])
    max_total = cfg.get("post", {}).get("max_internal_links", 3)
    used = 0
    for item in links:
        if used >= max_total: break
        kw = item.get("keyword")
        url = item.get("url")
        limit = int(item.get("max_per_post", 1))
        # replace first occurrences outside headings
        def repl(match, _url=url):
            nonlocal used
            if used >= max_total: return match.group(0)
            used += 1
            return f"<a href=\"{_url}\" rel=\"noopener internal\">{match.group(0)}</a>"
        html_body = re.sub(rf"(?i)(?<![\w>])({re.escape(kw)})", repl, html_body, count=limit)
    return html_body


def build_jsonld(headline, source_url, cfg):
    brand = cfg.get("brand", {})
    logo = brand.get("logo_url", "")
    publisher = brand.get("publisher", "Vietyen")
    now_iso = datetime.now(timezone.utc).isoformat()
    data = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": headline[:110],
        "image": cfg.get("default_hero_url"),
        "datePublished": now_iso,
        "dateModified": now_iso",
        "mainEntityOfPage": source_url,
        "publisher": {
            "@type": "Organization",
            "name": publisher,
            "logo": {"@type": "ImageObject", "url": logo}
        }
    }
    return json.dumps(data, ensure_ascii=False)


# ---------- WordPress REST ----------
def wp_auth():
    from base64 import b64encode
    token = b64encode(f"{WP_USER}:{WP_APP_PW}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def wp_find_similar(slug):
    url = f"{WP_URL}/wp-json/wp/v2/posts?status=draft,pending,publish&search={slug}&per_page=5"
    r = session.get(url, headers=wp_auth(), timeout=20)
    if r.ok:
        try:
            return [p.get("slug", "") for p in r.json()]
        except Exception:
            return []
    return []


def wp_create_post(title, content, excerpt, categories=None, featured_media=None, status="draft"):
    payload = {
        "title": title,
        "content": content,
        "excerpt": excerpt,
        "status": status
    }
    if categories:
        payload["categories"] = categories
    if featured_media:
        payload["featured_media"] = featured_media
    url = f"{WP_URL}/wp-json/wp/v2/posts"
    r = session.post(url, headers={**wp_auth(), "Content-Type": "application/json"}, json=payload, timeout=30)
    r.raise_for_status()
    return r.json()


# ---------- Category mapping ----------
def map_categories(title, cfg):
    cats = cfg.get("categories", [])
    selected = []
    t = title.lower()
    for c in cats:
        for kw in c.get("keywords", []):
            if kw.lower() in t:
                if c.get("id"): selected.append(int(c["id"]))
                break
    return list(dict.fromkeys(selected))[:3] or None


# ---------- Main run ----------
def run():
    cfg = load_config()
    assert WP_URL and WP_USER and WP_APP_PW, "Missing WP_* secrets"

    feeds = cfg.get("rss_sources", [])
    if not feeds:
        logging.error("No RSS sources configured.")
        return

    picked_item = None
    picked_feed = None

    for feed_url in feeds:
        logging.info(f"Parse RSS: {feed_url}")
        d = feedparser.parse(feed_url)
        for e in d.entries[:10]:
            title = html.unescape(getattr(e, "title", "").strip())
            link = getattr(e, "link", "").strip()
            summary = html.unescape(getattr(e, "summary", getattr(e, "description", "")).strip())
            if not (title and link):
                continue
            # Health classifier
            p = classify_health(title, cfg)
            if p < float(cfg.get("ai_check", {}).get("threshold", 0.6)):
                logging.info(f"Skip non-health: {title} (p={p:.2f})")
                continue
            picked_item = (title, link, summary)
            picked_feed = feed_url
            break
        if picked_item:
            break

    if not picked_item:
        logging.warning("No suitable item found today.")
        return

    title, link, summary = picked_item
    slug = slugify(title)

    # Deduplicate by search
    similars = wp_find_similar(slug)
    if slug in similars:
        logging.info("Similar post exists. Abort.")
        return

    # Rewrite & enrich
    content_html, excerpt, author, publisher = rewrite_and_enrich(title, summary, link, cfg)

    # Ensure Nguồn tham khảo block exists
    if "Nguồn tham khảo" not in content_html:
        content_html += f"\n\n<h2>Nguồn tham khảo</h2><ul><li><a href=\"{link}\">{link}</a></li></ul>"

    # Featured image (keep simple: use default hero)
    featured_media = None  # (Có thể upload ảnh qua media endpoint nếu cần)

    # Category mapping
    cat_ids = map_categories(title, cfg)

    post = wp_create_post(
        title=title,
        content=content_html,
        excerpt=excerpt,
        categories=cat_ids,
        featured_media=featured_media,
        status=cfg.get("post", {}).get("status", "draft")
    )

    logging.info(f"Created draft post ID: {post.get('id')} — {post.get('link')}")


if __name__ == "__main__":
    try:
        run()
    except Exception as ex:
        logging.exception(ex)
        raise
