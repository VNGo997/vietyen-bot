import os, base64, requests

class WPClient:
    def __init__(self, base_url: str, username: str, app_password: str):
        self.base_url = base_url.rstrip('/')
        token = f"{username}:{app_password}".encode("utf-8")
        self.headers = {
            "Authorization": "Basic " + base64.b64encode(token).decode("utf-8")
        }

    def create_or_get_tags(self, tag_names):
        """Return list of tag IDs; create tag if not exists."""
        ids = []
        for name in (tag_names or []):
            # search
            r = requests.get(f"{self.base_url}/wp-json/wp/v2/tags", headers=self.headers, params={"search": name, "per_page": 5}, timeout=30)
            r.raise_for_status()
            data = r.json()
            tag_id = None
            for t in data:
                if t.get("name","").lower() == name.lower():
                    tag_id = t["id"]; break
            if tag_id is None:
                # create
                r2 = requests.post(f"{self.base_url}/wp-json/wp/v2/tags", headers={**self.headers, "Content-Type":"application/json"}, json={"name": name}, timeout=30)
                r2.raise_for_status()
                tag_id = r2.json()["id"]
            ids.append(tag_id)
        return ids

    def upload_media_from_url(self, image_url: str, filename: str = "hero.jpg"):
        """Download image and upload to WP Media; return media ID or None."""
        if not image_url:
            return None
        try:
            img = requests.get(image_url, timeout=30)
            img.raise_for_status()
        except Exception as e:
            print(f"[WARN] download image fail: {e}")
            return None
        headers = self.headers.copy()
        headers.update({
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "image/jpeg"
        })
        r = requests.post(f"{self.base_url}/wp-json/wp/v2/media", headers=headers, data=img.content, timeout=60)
        if r.status_code >= 400:
            print("[WARN] upload media fail:", r.status_code, r.text[:200])
            return None
        return r.json().get("id")

    def find_post_with_title(self, title: str):
        r = requests.get(f"{self.base_url}/wp-json/wp/v2/posts", headers=self.headers, params={"search": title, "per_page": 5}, timeout=30)
        if r.status_code >= 400:
            return None
        for p in r.json():
            if p.get("title",{}).get("rendered","").strip().lower() == title.strip().lower():
                return p
        return None

    def post_article(self, title: str, content_html: str, status: str = "draft", category_id=None, tag_ids=None, featured_media=None):
        payload = {
            "title": title,
            "content": content_html,
            "status": status
        }
        if category_id is not None:
            payload["categories"] = [category_id] if isinstance(category_id, int) else category_id
        if tag_ids:
            payload["tags"] = tag_ids
        if featured_media:
            payload["featured_media"] = featured_media
        r = requests.post(f"{self.base_url}/wp-json/wp/v2/posts", headers={**self.headers, "Content-Type":"application/json"}, json=payload, timeout=60)
        if r.status_code >= 400:
            raise RuntimeError(f"WP post failed: {r.status_code} - {r.text}")
        return r.json()

def get_wp_from_env():
    base_url = os.getenv("WP_URL")
    username = os.getenv("WP_USERNAME")
    app_pw = os.getenv("WP_APP_PASSWORD")
    if not all([base_url, username, app_pw]):
        raise EnvironmentError("Missing WP_URL, WP_USERNAME or WP_APP_PASSWORD environment variables.")
    return WPClient(base_url, username, app_pw)
