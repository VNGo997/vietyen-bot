import os, sys, json, argparse, datetime, re, requests
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

def fetch_candidates(sources):
    items = []
    for src in sources:
        rss = src.get("rss")
        name = src.get("name","source")
        if not rss:
            continue
        try:
            feed = feedparser.parse(rss)
            for e in feed.get("entries", [])[:6]:
                title = e.get("title") or ""
                link = e.get("link") or ""
                summary = BeautifulSoup(e.get("summary",""), "html.parser").get_text(" ", strip=True) if e.get("summary") else ""
                if title and link:
                    items.append({"title": title, "link": link, "summary": summary, "source": name})
        except Exception as ex:
            print(f"[WARN] RSS fail {rss}: {ex}")
            continue
    # de-dup
    seen, uniq = set(), []
    for it in items:
        if it["link"] in seen: 
            continue
        seen.add(it["link"])
        uniq.append(it)
    return uniq

def scrape_article_text(url, max_paras=12):
    try:
        r = requests.get(url, timeout=20, headers={"User-Agent":"Mozilla/5.0"})
        r.raise_for_status()
    except Exception as ex:
        print(f"[WARN] fetch fail {url}: {ex}")
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    selectors = ["article", ".article", ".main-content", ".content-detail", ".detail__content", ".cms-body", ".box-content"]
    for sel in selectors:
        node = soup.select_one(sel)
        if node:
            paragraphs = [p.get_text(" ", strip=True) for p in node.select("p") if p.get_text(strip=True)]
            if paragraphs:
                return paragraphs[:max_paras]
    paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p") if p.get_text(strip=True)]
    return paragraphs[:max_paras]

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

def build_html(title, body_paras, source_name, source_url, css_inline, post_type):
    body = "\n".join([f"<p>{simple_rewrite(p)}</p>" for p in body_paras])
    product_hint = ""
    if post_type == "share":
        product_hint = """
        <div class="vy-product-hint">
          <strong>Gợi ý nhẹ:</strong> Nếu bạn quan tâm đến chăm sóc mắt hằng ngày,
          hãy tham khảo các sản phẩm tại <a href="https://vietyenltd.com/san-pham/" target="_blank" rel="noopener">VietYenLTD</a>.
        </div>
        """
    html = f"""
<style>{css_inline}</style>
<article class="vy-article">
  <h1>{title}</h1>
  <div class="vy-meta">Bản nháp tự động • {datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}</div>
  <hr class="vy-sep"/>
  {body}
  {product_hint}
  <div class="vy-source"><strong>Nguồn bài viết:</strong> <a href="{source_url}" target="_blank" rel="nofollow noopener">{source_name}</a></div>
  <div class="vy-disclaimer"><strong>Miễn trừ trách nhiệm:</strong> Thông tin chỉ mang tính tham khảo, không thay thế tư vấn y khoa.</div>
</article>
"""
    return html

def main(args):
    cfg = load_config()
    if cfg.get("bot_status","ON") != "ON":
        print("Bot is OFF in config.json — exit.")
        return

    post_type = pick_post_type(cfg)
    sources = cfg.get("sources", [])
    candidates = fetch_candidates(sources)

    if args.test:
        title = f"[TEST] Kết nối bot WordPress {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}"
        css = open("style-template.css", "r", encoding="utf-8").read()
        html = build_html(title, ["Đây là bài kiểm tra kết nối. Nếu thấy bài này trong mục Bản nháp, kết nối OK."], "VietYenLTD", "https://vietyenltd.com", css, post_type="share")
        wp = get_wp_from_env()
        res = wp.post_article(title, html, status=cfg.get("post_status","draft"), category_id=cff(cfg, "category_id"), tags=None)
        print("Posted test draft:", res.get("link","(no link)"))
        return

    if not candidates:
        print("No candidates fetched; nothing to post.")
        return

    item = candidates[0]
    paras = scrape_article_text(item["link"])
    if not paras:
        paras = [item.get("summary") or "Vui lòng xem liên kết nguồn để đọc đầy đủ nội dung."]
    paras = [p for p in paras if len(p) > 40][:10]
    if not paras:
        print("No usable content after filtering; skip.")
        return

    css = open("style-template.css", "r", encoding="utf-8").read()
    title = item["title"]
    html = build_html(title, paras, item.get("source","Nguồn"), item["link"], css, post_type)

    wp = get_wp_from_env()
    res = wp.post_article(title, html, status=cfg.get("post_status","draft"), category_id=cff(cfg, "category_id"), tags=None)
    print("Posted draft:", res.get("link","(no link)"))

def cff(cfg, key):
    # convenience: returns cfg[key] if key exists else None
    return cfg.get(key, None)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true", help="Post a simple test draft without scraping.")
    args = ap.parse_args()
    main(args)
