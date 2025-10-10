import os, json, argparse, datetime, re, requests
from urllib.parse import urlencode
from bs4 import BeautifulSoup
import feedparser
from wordpress_connection import get_wp_from_env

def load_config():
    with open("config.json", "r", encoding="utf-8") as f:
        return json.load(f)

def pick_post_type(config):
    cycle = config.get("post_cycle", ["news","news","share"])
    day_of_year = datetime.datetime.utcnow().timetuple().tm_yday
    return cycle[(day_of_year - 1) % len(cycle)]

def text_ok(text, words):
    t = (text or "").lower()
    return any(w.lower() in t for w in words)

def passes_filters(title, summary, cfg):
    # must include health-related keywords in title OR summary
    inc = cfg.get("include_keywords") or []
    exc = cfg.get("exclude_keywords") or []
    has_inc = text_ok(title, inc) or text_ok(summary, inc)
    has_exc = text_ok(title, exc) or text_ok(summary, exc)
    return has_inc and not has_exc

def fetch_candidates(sources, cfg):
    items = []
    for src in sources:
        rss = src.get("rss")
        name = src.get("name","source")
        if not rss: 
            continue
        try:
            feed = feedparser.parse(rss)
            for e in feed.get("entries", [])[:12]:
                title = e.get("title") or ""
                link = e.get("link") or ""
                summary = BeautifulSoup(e.get("summary",""), "html.parser").get_text(" ", strip=True) if e.get("summary") else ""
                if not (title and link):
                    continue
                if not passes_filters(title, summary, cfg):
                    continue
                items.append({"title": title.strip(), "link": link.strip(), "summary": summary.strip(), "source": name})
        except Exception as ex:
            print(f"[WARN] RSS fail {rss}: {ex}")
            continue
    # de-dup by link
    seen, uniq = set(), []
    for it in items:
        if it["link"] in seen: 
            continue
        seen.add(it["link"])
        uniq.append(it)
    return uniq

def scrape(url, max_paras=12):
    try:
        r = requests.get(url, timeout=25, headers={"User-Agent":"Mozilla/5.0"})
        r.raise_for_status()
    except Exception as ex:
        print(f"[WARN] fetch fail {url}: {ex}")
        return {"paras":[], "image":None}
    soup = BeautifulSoup(r.text, "html.parser")
    og = soup.find("meta", property="og:image")
    hero = og["content"].strip() if og and og.get("content") else None

    selectors = ["article", ".article", ".main-content", ".content-detail", ".detail__content", ".cms-body", ".box-content"]
    paragraphs = []
    for sel in selectors:
        node = soup.select_one(sel)
        if node:
            paragraphs = [p.get_text(" ", strip=True) for p in node.select("p") if p.get_text(strip=True)]
            if paragraphs:
                break
    if not paragraphs:
        paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p") if p.get_text(strip=True)]
    return {"paras": paragraphs[:max_paras], "image": hero}

def simple_rewrite(text):
    rules = [
        (r"\b(Theo|Theo đó|Bên cạnh đó|Ngoài ra)\b", "Ghi nhận gần đây cho thấy"),
        (r"\b(Khuyến cáo|Khuyên|Lưu ý)\b", "Gợi ý"),
        (r"\s{2,}", " ")
    ]
    out = text
    for pat, rep in rules:
        out = re.sub(pat, rep, out, flags=re.IGNORECASE)
    return out

def add_utm(url):
    try:
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}{urlencode({'utm_source':'vietyen-bot','utm_medium':'ref','utm_campaign':'health-news'})}"
    except Exception:
        return url

def build_html(title, paras, source_name, source_url, css_inline, post_type, hero_url, cta_html):
    body = "\n".join([f"<p>{simple_rewrite(p)}</p>" for p in paras])
    hero_html = f'<div class="vy-hero"><img src="{hero_url}" alt="featured" loading="lazy"/></div>' if hero_url else ""
    cta = f'<div class="vy-cta">{cta_html}</div>' if post_type == "share" and cta_html else ""
    html = f"""
<style>{css_inline}</style>
<article class="vy-article">
  <div class="vy-meta"><span class="vy-badge">Bản nháp tự động</span><span>{datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}</span></div>
  <h1>{title}</h1>
  {hero_html}
  <hr class="vy-sep"/>
  {body}
  {cta}
  <div class="vy-card"><strong>Nguồn bài viết:</strong> <a href="{add_utm(source_url)}" target="_blank" rel="nofollow noopener">{source_name}</a></div>
  <div class="vy-card"><strong>Miễn trừ trách nhiệm:</strong> Nội dung chỉ nhằm mục đích thông tin, không thay thế tư vấn, chẩn đoán hoặc điều trị y khoa.</div>
</article>
"""
    return html

def main(args):
    cfg = load_config()
    if cfg.get("bot_status","ON") != "ON":
        print("Bot is OFF in config.json — exit.")
        return

    wp = get_wp_from_env()
    post_type = pick_post_type(cfg)
    candidates = fetch_candidates(cfg.get("sources", []), cfg)
    if not candidates:
        print("No candidates after filtering.")
        return

    item = candidates[0]

    # De-dup by title
    found = wp.find_post_with_title(item["title"])
    if found:
        print("Skip: title already exists in WP:", item["title"])
        return

    scraped = scrape(item["link"])
    paras = [p for p in scraped["paras"] if len(p) > 40][:10] or [item.get("summary") or "Vui lòng xem liên kết nguồn để đọc đầy đủ nội dung."]

    css = open("style-template.css", "r", encoding="utf-8").read()
    hero = scraped.get("image") or cfg.get("default_hero_url")

    # Upload hero to WP and set as featured image
    featured_id = wp.upload_media_from_url(hero, filename="hero.jpg") if hero else None

    # Ensure tags by name
    tags = wp.create_or_get_tags(cfg.get("tags_by_name")) if cfg.get("tags_by_name") else None

    html = build_html(item["title"], paras, item.get("source","Nguồn"), item["link"], css, post_type, hero, cfg.get("cta_html"))
    res = wp.post_article(item["title"], html, status=cfg.get("post_status","draft"),
                          category_id=cfg.get("category_id"), tag_ids=tags, featured_media=featured_id)
    print("Posted draft:", res.get("link","(no link)"))

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true", help="Post a simple test draft without scraping.")  # kept for compatibility
    args = ap.parse_args()
    main(args)
