# VietYen Bot v4.3 — Optimized
import os, json, time, re, datetime, traceback
from pathlib import Path
from wordpress_connection import get_wp_from_env, WPClientError

def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def read_text(path):
    return Path(path).read_text(encoding="utf-8")

def safe_log(msg):
    print("[" + datetime.datetime.now().isoformat(sep=" ", timespec="seconds") + "] " + msg)

def detect_topic(title, cfg):
    for t in cfg.get("topics", []):
        if any(k.lower() in title.lower() for k in t.get("match", [])):
            return t
    return {}

def build_html(title, tpl, css, bullets, hero, mid):
    bullets_html = "".join("<li>"+b+"</li>" for b in bullets)
    return (tpl
        .replace("{{STYLE}}", css)
        .replace("{{TITLE}}", title)
        .replace("{{BULLETS}}", bullets_html)
        .replace("{{HERO}}", hero or "")
        .replace("{{MID}}", ('<div class="vy-mid"><img src="'+mid+'" alt="mid image"></div>') if mid else "")
    )

def render_expert_tip(cfg):
    ex = cfg.get("expert_tip", {})
    if not ex.get("enabled", False):
        return ""
    product_name = ex.get("product_name", "Gạc vệ sinh bờ mi Visionary")
    product_url  = ex.get("product_url",  "https://vietyenltd.com/san-pham/gac-ve-sinh-bo-mi-visionary/")
    tip_text = ex.get("text") or (
        "Nếu bạn thường xuyên dùng máy tính và thấy mắt khô, cay nhẹ, hãy duy trì vệ sinh bờ mi mỗi ngày. "
        + "Một giải pháp đơn giản là dùng <a href=\\"" + product_url + "\\" target=\\"_blank\\" rel=\\"nofollow noopener\\">" + product_name + "</a> trước và sau khi ngủ để làm sạch bụi bẩn và bã nhờn quanh mí."
    )
    return (
        '<div class="vy-expert-tip">'
        '<div class="vy-expert-badge">Gợi ý từ chuyên gia</div>'
        '<p>'+tip_text+'</p>'
        '</div>'
    )

def inject_expert_tip(html, tip_block, position="after_bullets"):
    if not tip_block:
        return html
    if position == "after_bullets" and "</ul>" in html:
        return html.replace("</ul>", "</ul>\\n" + tip_block, 1)
    if position == "before_faq":
        m = re.search(r"<h2[^>]*>Hỏi &amp; Đáp", html)
        if m:
            idx = m.start()
            return html[:idx] + tip_block + html[idx:]
    return html + tip_block

def build_bullets(cfg):
    return cfg.get("bullets") or [
        "Khoảng <strong>80%</strong> người làm việc máy tính &gt;4 giờ/ngày có dấu hiệu khô/mỏi mắt.",
        "Không khí điều hòa làm giảm độ ẩm, dễ gây khô rát và kích ứng.",
        "Tần suất chớp mắt giảm mạnh khi nhìn màn hình tập trung.",
        "Nghỉ mắt 20-20-20, chớp mắt thường xuyên và vệ sinh bờ mi giúp mắt khỏe hơn."
    ]

def main():
    cfg = load_json("config.json")
    tpl = read_text("templates/article.html")
    css = read_text("style-template.css")

    title = cfg.get("demo_title", "Chăm sóc mắt khi dùng màn hình nhiều (demo)")
    topic = detect_topic(title, cfg)
    fallbacks = topic.get("fallback_images", [])
    hero = cfg.get("images",{}).get("hero") or (fallbacks[0] if fallbacks else cfg.get("default_hero_url",""))
    mid  = cfg.get("images",{}).get("mid")  or (fallbacks[1] if len(fallbacks) > 1 else None)

    html = build_html(title, tpl, css, build_bullets(cfg), hero, mid)
    html = inject_expert_tip(html, render_expert_tip(cfg), cfg.get("expert_tip",{}).get("position","after_bullets"))

    safe_log("HTML built. demo_mode=%s" % cfg.get("demo_mode", True))
    if cfg.get("demo_mode", True):
        print(html[:800] + ("\n...\n" if len(html)>800 else ""))
        return

    try:
        wp = get_wp_from_env()
        featured_id = None
        if hero:
            safe_log("Uploading hero image...")
            featured_id = wp.upload_media_from_url(hero, filename="hero.jpg", retries=3)
            safe_log("Hero uploaded: media_id=%s" % featured_id)
        tag_ids = wp.create_or_get_tags(cfg.get("tags_by_name"))
        cat_id = wp.ensure_category(cfg.get("category_name")) if cfg.get("category_name") else cfg.get("category_id")

        safe_log("Posting draft...")
        res = wp.post_article(title, html, status=cfg.get("post_status","draft"),
                              category_id=cat_id, tag_ids=tag_ids, featured_media=featured_id)
        post_id = res.get("id")
        safe_log("Draft posted: id=%s, link=%s" % (post_id, res.get("link")))

        seo = cfg.get("seo", {})
        if seo.get("yoast_title") or seo.get("yoast_description"):
            safe_log("Attempting Yoast meta via REST...")
            try:
                wp.update_post_meta(post_id, {
                    "yoast_wpseo_title": seo.get("yoast_title"),
                    "yoast_wpseo_metadesc": seo.get("yoast_description")
                })
                safe_log("Yoast meta updated (if permitted).")
            except Exception as e:
                safe_log("Yoast meta skipped: %s" % e)

        print("Posted draft:", res.get("link","(no link)"))
    except Exception as e:
        safe_log("Error: " + str(e))
        raise

if __name__ == "__main__":
    main()
