# wordpress_connection.py — tương thích v4.2b
import os
from bot import wp_create_draft

def create_post_to_wordpress(title, content, tags, status, cfg):
    """Giữ nguyên giao thức gọi từ workflow cũ."""
    if status != "draft": status = "draft"
    return wp_create_draft(title, content, tags, cfg)
