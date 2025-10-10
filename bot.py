
import json, datetime
from wordpress_connection import get_wp_from_env

HTML_TEMPLATE = """
<style>{CSS}</style>
<article class="vy-article">
  <div class="vy-meta"><span class="vy-badge">Ban nhap tu dong</span>{NOW}</div>
  <h1>{TITLE}</h1>
  <figure class="vy-hero"><img src="{HERO}" alt="Anh minh hoa y te"></figure>

  <div class="vy-note"><strong>Tom tat ngan gon:</strong> Lam viec truoc man hinh lau co the khien mat kho, moi va mo thoang qua.</div>

  <h2>Dieu ban can luu y</h2>
  <ul style="list-style:none;padding-left:0;line-height:1.75;margin:10px 0 22px">{BULLETS}</ul>

  {MIDBLOCK}

  <h2>Vi sao ban de gap tinh trang nay?</h2>
  <p>Thoi quen nhin man hinh lien tuc khien mang nuoc mat bay hoi nhanh, lam kho giac mac va tao cam giac rat hoac nhuc moi.</p>

  <h2>Cach cham soc va phong ngua hieu qua</h2>
  <div class="vy-card">
    <ol style="margin:0 0 0 18px;line-height:1.7">
      <li><strong>Quy tac 20-20-20:</strong> Sau moi 20 phut, nhin xa 6m trong it nhat 20 giay.</li>
      <li><strong>Giu do am phong:</strong> 50-60 phan tram, tranh luong gio thoi truc tiep vao mat.</li>
      <li><strong>Ve sinh bo mi:</strong> Dung gac ve sinh vo trung, nhe diu moi ngay.</li>
      <li><strong>Anh sang hop ly:</strong> Tranh man hinh qua choi hoac phong qua toi.</li>
    </ol>
  </div>

  {EXPERT}

  <div class="vy-card" style="border-style:solid">
    <strong>Nguon tham khao:</strong> 
    <a href="https://suckhoedoisong.vn" target="_blank" rel="nofollow noopener">Suc Khoe & Doi Song</a><br>
    <strong>Mien tru trach nhiem:</strong> Noi dung chi tham khao, khong thay the tu van, chan doan hoac dieu tri y khoa.
  </div>
</article>
"""

def detect_topic(title, cfg):
    for t in cfg.get("topics", []):
        if any(k.lower() in title.lower() for k in t.get("match", [])):
            return t
    return None

def render_expert_advice(topic_name, cfg):
    advice_cfg = (cfg.get("expert_advice", {}) or {}).get(topic_name) or (cfg.get("expert_advice", {}) or {}).get("default", {})
    title = advice_cfg.get("title", "Goi y tu chuyen gia")
    lead  = advice_cfg.get("lead", "Bac si khuyen duy tri ve sinh, nghi ngoi va loi song lanh manh moi ngay.")
    label = advice_cfg.get("product_label", "Xem them san pham")
    url   = advice_cfg.get("product_url", "https://vietyenltd.com/san-pham/")
    return f'<h2>{title}</h2><div class="vy-cta"><p style="font-size:17px;margin-bottom:12px"><strong>Khuyen dung:</strong> {lead}</p><p style="margin:0">Tham khao: <a href="{url}" target="_blank" rel="noopener">{label}</a></p></div>'

def main():
    cfg = json.load(open("config.json","r",encoding="utf-8"))
    css = open("style-template.css","r",encoding="utf-8").read()
    title = "Cham soc mat va phong ngua kho mat o nguoi dung may tinh"
    topic = detect_topic(title, cfg) or {}
    topic_name = topic.get("name")
    imgs = topic.get("fallback_images", []) or [cfg.get("default_hero_url")]
    hero = imgs[0]
    mid = imgs[1] if len(imgs)>1 else None

    bullets = "".join(f"<li>&bull; {b}</li>" for b in [
        "Khoang 80% nguoi lam viec may tinh tren 4 gio/ngay gap trieu chung kho hoac moi mat.",
        "Khong khi dieu hoa lam giam do am, de gay kho rat va kich ung.",
        "Tan suat chop mat giam manh khi nhin man hinh tap trung.",
        "Nghi mat 20-20-20, chop mat thuong xuyen va ve sinh bo mi giup mat khoe hon."
    ])

    midblock = f'<figure class="vy-hero"><img src="{mid}" alt="Anh minh hoa y te"><figcaption style="text-align:center;color:#667;font-size:13px;margin-top:6px">Anh minh hoa: Unsplash</figcaption></figure>' if mid else ""

    expert = render_expert_advice(topic_name, cfg)

    html = HTML_TEMPLATE.format(CSS=css, NOW=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                                TITLE=title, HERO=hero, BULLETS=bullets, MIDBLOCK=midblock, EXPERT=expert)

    wp = get_wp_from_env()
    featured_id = wp.upload_media_from_url(hero, filename="hero.jpg")
    tags = wp.create_or_get_tags(cfg.get("tags_by_name"))
    res = wp.post_article(title, html, status=cfg.get("post_status","draft"),
                          category_id=cfg.get("category_id"), tag_ids=tags, featured_media=featured_id)
    print("Draft created:", res.get("link","(no link)"))

if __name__ == "__main__":
    main()
