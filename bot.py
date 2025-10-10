import os, json, argparse, datetime, re, requests
from urllib.parse import urlencode
from bs4 import BeautifulSoup
import feedparser
from wordpress_connection import get_wp_from_env

def load_config():
    with open("config.json", "r", encoding="utf-8") as f:
        return json.load(f)

def pick_post_type(config):
    cycle = config.get("post_cycle", ["news","share","news"])
    day_of_year = datetime.datetime.utcnow().timetuple().tm_yday
    return cycle[(day_of_year - 1) % len(cycle)]

def text_ok(text, words):
    t = (text or "").lower()
    return any(w.lower() in t for w in words)

def passes_filters(title, summary, cfg):
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
        if not rss: continue
        try:
            feed = feedparser.parse(rss)
            for e in feed.get("entries", [])[:12]:
                title = (e.get("title") or "").strip()
                link = (e.get("link") or "").strip()
                summary = BeautifulSoup(e.get("summary",""), "html.parser").get_text(" ", strip=True) if e.get("summary") else ""
                if not (title and link): continue
                if not passes_filters(title, summary, cfg): continue
                items.append({"title": title, "link": link, "summary": summary, "source": name})
        except Exception as ex:
            print(f"[WARN] RSS fail {rss}: {ex}")
            continue
    seen, uniq = set(), []
    for it in items:
        if it["link"] in seen: continue
        seen.add(it["link"]); uniq.append(it)
    return uniq

def scrape(url, max_paras=12):
    try:
        r = requests.get(url, timeout=25, headers={"User-Agent":"Mozilla/5.0"}); r.raise_for_status()
    except Exception as ex:
        print(f"[WARN] fetch fail {url}: {ex}"); return {"paras":[], "image":None}
    soup = BeautifulSoup(r.text, "html.parser")
    og = soup.find("meta", property="og:image")
    hero = og["content"].strip() if og and og.get("content") else None
    selectors = ["article",".article",".main-content",".content-detail",".detail__content",".cms-body",".box-content"]
    paragraphs = []
    for sel in selectors:
        node = soup.select_one(sel)
        if node:
            paragraphs = [p.get_text(" ", strip=True) for p in node.select("p") if p.get_text(strip=True)]
            if paragraphs: break
    if not paragraphs:
        paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p") if p.get_text(strip=True)]
    return {"paras": paragraphs[:max_paras], "image": hero}

def simple_rewrite(text):
    rules = [(r"\b(Theo|Theo đó|Bên cạnh đó|Ngoài ra)\b","Ghi nhận gần đây cho thấy"),
             (r"\b(Khuyến cáo|Khuyên|Lưu ý)\b","Gợi ý"),
             (r"\s{2,}"," ")]
    out = text
    for pat, rep in rules: out = re.sub(pat, rep, out, flags=re.IGNORECASE)
    return out

def key_points(paras, n=5):
    text = " ".join(paras)
    sentences = re.split(r"(?<=[.!?…])\s+", text)
    # choose first n informative sentences (length between 60 and 200 chars)
    cand = [s.strip() for s in sentences if 60 <= len(s.strip()) <= 200]
    return cand[:n]

def extract_sections(paras):
    # heuristic: collect sentences mentioning these cues
    cues = {
        "Triệu chứng": ["triệu chứng","dấu hiệu"],
        "Nguyên nhân": ["nguyên nhân","yếu tố nguy cơ","nguy cơ"],
        "Phòng ngừa": ["phòng ngừa","dự phòng","cách phòng","lối sống"],
        "Điều trị": ["điều trị","chăm sóc","khuyến nghị","gợi ý"]
    }
    sections = {k: [] for k in cues}
    for p in paras:
        pl = p.lower()
        for k, words in cues.items():
            if any(w in pl for w in words):
                sections[k].append(p)
    # shorten each section to 2-3 bullet items (split sentences)
    out = {}
    for k, texts in sections.items():
        sents = []
        for t in texts:
            sents += re.split(r"(?<=[.!?…])\s+", t)
        sents = [s.strip() for s in sents if 35 <= len(s.strip()) <= 180][:3]
        if sents:
            out[k] = sents
    return out

def add_utm(url):
    try:
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}{urlencode({'utm_source':'vietyen-bot','utm_medium':'ref','utm_campaign':'health-news'})}"
    except Exception:
        return url

def build_html(title, paras, source_name, source_url, css_inline, post_type, hero_url, cta_html, cfg):
    # enforce length limits
    char_count = 0
    pruned = []
    for p in paras:
        if char_count + len(p) > cfg.get("max_chars", 3500): break
        pruned.append(p); char_count += len(p)
    paras = pruned[: cfg.get("max_paragraphs", 8) ]

    kp = key_points(paras, n=cfg.get("keypoints_n",5))
    secs = extract_sections(paras)

    # Build optional TOC
    toc_html = ""
    if cfg.get("enable_toc", True):
        items = ["<li><a href='#kp'>Điểm chính</a></li>"]
        for name in ["Triệu chứng","Nguyên nhân","Phòng ngừa","Điều trị"]:
            if name in secs: items.append(f"<li><a href='#{name}'>{name}</a></li>")
        toc_html = f"<div class='vy-toc'><h3>Mục lục</h3><ol>{''.join(items)}</ol></div>" if items else ""

    body_html = "\n".join([f"<p>{simple_rewrite(p)}</p>" for p in paras])

    # Icons via emoji for simplicity
    kp_icon = "🩺"
    src_icon = "🔗"
    dis_icon = "⚠️"

    # Sections to HTML
    sec_blocks = []
    for name, bullets in secs.items():
        lis = "".join([f"<li>{simple_rewrite(b)}</li>" for b in bullets])
        sec_blocks.append(f"<h2 id='{name}'>{name}</h2><div class='vy-card'><ul>{lis}</ul></div>")
    sec_html = "\n".join(sec_blocks)

    hero_html = f'<div class="vy-hero"><img src="{hero_url}" alt="featured" loading="lazy"/></div>' if hero_url else ""
    cta = f'<div class="vy-cta">{cta_html}</div>' if post_type == "share" and cta_html else ""

    html = f"""
<style>{css_inline}</style>
<article class="vy-article">
  <div class="vy-meta"><span class="vy-badge">Bản nháp tự động</span><span>{datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}</span></div>
  <h1>{title}</h1>
  {hero_html}
  {toc_html}
  <div id="kp" class="vy-kp"><h3>{kp_icon} Điểm chính</h3><ul>{''.join([f'<li>{simple_rewrite(x)}</li>' for x in kp])}</ul></div>
  <hr class="vy-sep"/>
  {body_html}
  {sec_html}
  {cta}
  <div class="vy-footer">
    <div class="vy-card vy-source"><strong>{src_icon} Nguồn bài viết:</strong><br/><a class="btn" href="{add_utm(source_url)}" target="_blank" rel="nofollow noopener">{source_name} — mở bài gốc</a></div>
    <div class="vy-card vy-disclaimer"><strong>{dis_icon} Miễn trừ trách nhiệm:</strong><br/>Thông tin chỉ nhằm mục đích tham khảo, không thay thế tư vấn, chẩn đoán hoặc điều trị y khoa.</div>
  </div>
</article>
"""
    return html

from wordpress_connection import get_wp_from_env

def main(args):
    cfg = load_config()
    if cfg.get("bot_status","ON") != "ON": print("Bot OFF"); return

    # setup
    wp = get_wp_from_env()
    post_type = pick_post_type(cfg)

    # choose candidate
    candidates = fetch_candidates(cfg.get("sources", []), cfg)
    if not candidates: print("No candidates"); return
    item = candidates[0]

    # dedup
    if wp.find_post_with_title(item["title"]): print("Skip duplicate title"); return

    # scrape
    scraped = scrape(item["link"])
    paras = [p for p in scraped["paras"] if len(p) > 40] or [item.get("summary") or "Vui lòng xem liên kết nguồn để đọc đầy đủ."]
    css = open("style-template.css","r",encoding="utf-8").read()
    hero = scraped.get("image") or cfg.get("default_hero_url")

    # upload hero & tags
    featured_id = wp.upload_media_from_url(hero, filename="hero.jpg") if hero else None
    tags = wp.create_or_get_tags(cfg.get("tags_by_name")) if cfg.get("tags_by_name") else None

    html = build_html(item["title"], paras, item.get("source","Nguồn"), item["link"], css, post_type, hero, cfg.get("cta_html"), cfg)
    res = wp.post_article(item["title"], html, status=cfg.get("post_status","draft"),
                          category_id=cfg.get("category_id"), tag_ids=tags, featured_media=featured_id)
    print("Posted draft:", res.get("link","(no link)"))

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true")
    args = ap.parse_args()
    main(args)
