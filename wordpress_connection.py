import os, base64, requests

class WPClient:
    def __init__(self, base_url, username, app_password):
        self.base_url = base_url.rstrip('/')
        token = f"{username}:{app_password}".encode('utf-8')
        self.headers = {"Authorization": "Basic " + base64.b64encode(token).decode('utf-8')}
    def upload_media_from_url(self, image_url, filename='hero.jpg'):
        try:
            resp = requests.get(image_url, timeout=30); resp.raise_for_status()
            headers = self.headers.copy(); headers.update({"Content-Disposition": f'attachment; filename="{filename}"', "Content-Type": "image/jpeg"})
            r = requests.post(f"{self.base_url}/wp-json/wp/v2/media", headers=headers, data=resp.content, timeout=60)
            if r.status_code >= 400: print('[WARN] upload fail', r.status_code, r.text[:200]); return None
            return r.json().get('id')
        except Exception as e:
            print('[WARN] media error', e); return None
    def create_or_get_tags(self, tag_names):
        ids=[]
        for name in (tag_names or []):
            try:
                q=requests.get(f"{self.base_url}/wp-json/wp/v2/tags", headers=self.headers, params={"search":name,"per_page":10}, timeout=30)
                if q.status_code<300:
                    found=[t for t in q.json() if t.get('name','').lower()==name.lower()]
                    if found: ids.append(found[0]['id']); continue
                c=requests.post(f"{self.base_url}/wp-json/wp/v2/tags", headers={**self.headers, "Content-Type":"application/json"}, json={"name":name}, timeout=30)
                if c.status_code<300: ids.append(c.json()['id'])
            except Exception as e:
                print('[WARN] tag error', e)
        return ids
    def post_article(self, title, content_html, status='draft', category_id=None, tag_ids=None, featured_media=None):
        payload={"title":title,"content":content_html,"status":status}
        if category_id is not None: payload["categories"]= [category_id] if isinstance(category_id,int) else category_id
        if tag_ids: payload["tags"]=tag_ids
        if featured_media: payload["featured_media"]=featured_media
        r=requests.post(f"{self.base_url}/wp-json/wp/v2/posts", headers={**self.headers, "Content-Type":"application/json"}, json=payload, timeout=60)
        if r.status_code>=400: raise RuntimeError(f"WP post failed: {r.status_code} - {r.text[:200]}")
        return r.json()

def get_wp_from_env():
    base=os.getenv('WP_URL'); user=os.getenv('WP_USERNAME'); pw=os.getenv('WP_APP_PASSWORD')
    if not all([base,user,pw]): raise EnvironmentError('Missing WP_URL, WP_USERNAME or WP_APP_PASSWORD')
    return WPClient(base,user,pw)
