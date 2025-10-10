import os
import base64
import requests

class WPClient:
    def __init__(self, base_url: str, username: str, app_password: str):
        self.base_url = base_url.rstrip('/')
        token = f"{username}:{app_password}".encode("utf-8")
        self.headers = {
            "Authorization": "Basic " + base64.b64encode(token).decode("utf-8"),
            "Content-Type": "application/json"
        }

    def post_article(self, title: str, content_html: str, status: str = "draft", category_id=None, tags=None):
        payload = {
            "title": title,
            "content": content_html,
            "status": status
        }
        if category_id is not None:
            payload["categories"] = [category_id] if isinstance(category_id, int) else category_id
        if tags:
            payload["tags"] = tags  # expects list of tag IDs; creating tags by name would require extra calls
        url = f"{self.base_url}/wp-json/wp/v2/posts"
        resp = requests.post(url, headers=self.headers, json=payload, timeout=60)
        if resp.status_code >= 400:
            raise RuntimeError(f"WP post failed: {resp.status_code} - {resp.text}")
        return resp.json()

def get_wp_from_env():
    base_url = os.getenv("WP_URL")
    username = os.getenv("WP_USERNAME")
    app_pw = os.getenv("WP_APP_PASSWORD")
    if not all([base_url, username, app_pw]):
        raise EnvironmentError("Missing WP_URL, WP_USERNAME or WP_APP_PASSWORD environment variables.")
    return WPClient(base_url, username, app_pw)
