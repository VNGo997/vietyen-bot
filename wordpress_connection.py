import os, base64, time, json, requests
from dataclasses import dataclass

class WPClientError(Exception): pass

@dataclass
class WPClient:
    base_url: str
    username: str
    app_password: str

    def _headers(self):
        token = base64.b64encode(f"{self.username}:{self.app_password}".encode()).decode()
        return {
            "Authorization": f"Basic {token}",
            "Content-Type": "application/json"
        }

    def _url(self, path):
        return self.base_url.rstrip("/") + path

    def _req(self, method, path, **kwargs):
        url = self._url(path)
        for attempt in range(4):
            try:
                r = requests.request(method, url, headers=self._headers(), timeout=30, **kwargs)
                if 200 <= r.status_code < 300:
                    return r
                if r.status_code in (429, 500, 502, 503, 504):
                    time.sleep(2 + attempt)
                    continue
                raise WPClientError(f"{method} {url} -> {r.status_code} {r.text[:200]}")
            except requests.RequestException as e:
                if attempt == 3:
                    raise WPClientError(f"Network error on {method} {url}: {e}")
                time.sleep(2 + attempt)
        raise WPClientError("Unreachable")

    def upload_media_from_url(self, img_url, filename="image.jpg", retries=2):
        if not img_url:
            return None
        for attempt in range(retries+1):
            try:
                data = requests.get(img_url, timeout=30).content
                break
            except Exception as e:
                if attempt == retries:
                    raise WPClientError(f"Download failed: {e}")
                time.sleep(2+attempt)
        headers = self._headers()
        headers.update({"Content-Type": "image/jpeg", "Content-Disposition": f'attachment; filename="{filename}"'})
        r = self._req("POST", "/wp-json/wp/v2/media", data=data, headers=headers)
        return r.json().get("id")

    def create_or_get_tags(self, tag_names):
        ids = []
        if not tag_names: return ids
        existing = {}
        page = 1
        while True:
            r = self._req("GET", f"/wp-json/wp/v2/tags?per_page=100&page={page}")
            arr = r.json()
            if not arr: break
            for t in arr:
                existing[t["name"].lower()] = t["id"]
            if len(arr) < 100: break
            page += 1
        for name in tag_names:
            key = name.lower().strip()
            if key in existing:
                ids.append(existing[key])
            else:
                r = self._req("POST", "/wp-json/wp/v2/tags", json={"name": name})
                ids.append(r.json().get("id"))
        return ids

    def ensure_category(self, name):
        if not name: return None
        r = self._req("GET", f"/wp-json/wp/v2/categories?search={name}")
        arr = r.json()
        for c in arr:
            if c.get("name","").lower() == name.lower():
                return c["id"]
        r = self._req("POST", "/wp-json/wp/v2/categories", json={"name": name})
        return r.json().get("id")

    def post_article(self, title, content, status="draft", category_id=None, tag_ids=None, featured_media=None):
        payload = {
            "title": title,
            "content": content,
            "status": status
        }
        if category_id:
            payload["categories"] = [category_id]
        if tag_ids:
            payload["tags"] = tag_ids
        if featured_media:
            payload["featured_media"] = featured_media
        r = self._req("POST", "/wp-json/wp/v2/posts", json=payload)
        return r.json()

    def update_post_meta(self, post_id, meta: dict):
        payload = {"meta": meta}
        r = self._req("POST", f"/wp-json/wp/v2/posts/{post_id}", json=payload)
        return r.json()

def get_wp_from_env():
    base = os.getenv("WP_BASE_URL", "").strip()
    user = os.getenv("WP_USER", "").strip()
    pw   = os.getenv("WP_APP_PW", "").strip()
    if not base or not user or not pw:
        raise WPClientError("Missing env: WP_BASE_URL / WP_USER / WP_APP_PW")
    return WPClient(base, user, pw)
