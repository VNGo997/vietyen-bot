# vietyen-bot v4.2
# Tự động đăng bài sức khỏe với ảnh minh họa từ Unsplash

import requests, random, json
from bs4 import BeautifulSoup

def detect_topic(title, cfg):
    for t in cfg.get("topics", []):
        if any(k.lower() in title.lower() for k in t.get("match", [])):
            return t
    return None

def collect_inline_images(soup):
    imgs = []
    for im in soup.select("article img, .article img, .content-detail img, .detail__content img"):
        src = im.get("data-src") or im.get("src")
        if src and src.startswith("http"):
            imgs.append(src)
    seen, out = set(), []
    for u in imgs:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out[:4]

def scrape(url):
    r = requests.get(url, timeout=10)
    soup = BeautifulSoup(r.text, "html.parser")
    paragraphs = [p.get_text().strip() for p in soup.select("p") if len(p.get_text().strip()) > 30]
    og_img = soup.find("meta", property="og:image")
    hero = og_img["content"] if og_img else None
    inline_imgs = collect_inline_images(soup)
    return {"paras": paragraphs[:6], "image": hero, "images": inline_imgs}

def main():
    with open("config.json", "r", encoding="utf-8") as f:
        cfg = json.load(f)
    test_title = "Chăm sóc mắt và phòng ngừa khô mắt ở người dùng máy tính"
    topic = detect_topic(test_title, cfg)
    fallbacks = (topic or {}).get("fallback_images", []) or [cfg.get("default_hero_url")]
    hero = fallbacks[0]
    mid = fallbacks[1] if len(fallbacks) > 1 else None
    print("Ảnh hero:", hero)
    print("Ảnh giữa bài:", mid)

if __name__ == "__main__":
    main()
