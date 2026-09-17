#!/usr/bin/env python3
"""
Скрипт сбора новостей и медиа для EngieDEV Team
- Telegram (@gd_engie) -> лента RU с картинками и превью видео
- Bluesky (engiedev.bsky.social) -> лента EN с картинками и превью видео
Без API-ключей и ботов — прямо из публичных лент.
"""

import urllib.request
import json
import re
import html
from datetime import datetime, timezone
import os

TELEGRAM_CHANNEL = "gd_engie"
BLUESKY_HANDLE = "engiedev.bsky.social"
MAX_POSTS = 12

def fetch_bluesky_news():
    posts = []
    url = f"https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed?actor={BLUESKY_HANDLE}&limit={MAX_POSTS + 5}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "EngieDEV-News-Bot/1.0"})
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            for item in data.get("feed", []):
                post = item.get("post", {})
                rec = post.get("record", {})
                
                # Игнорируем ответы другим пользователям
                if rec.get("reply"):
                    continue

                uri = post.get("uri", "")
                rkey = uri.split("/")[-1] if uri else ""
                post_url = f"https://bsky.app/profile/{BLUESKY_HANDLE}/post/{rkey}" if rkey else f"https://bsky.app/profile/{BLUESKY_HANDLE}"
                
                text = rec.get("text", "").strip()
                if not text and not post.get("embed"):
                    continue

                date_str = rec.get("createdAt", "")
                
                # Извлекаем медиа (видео, картинки, превью ссылок)
                media_type = None
                media_url = None
                embed = post.get("embed", {})
                
                # 1. Прикреплённые картинки
                if "images" in embed and embed["images"]:
                    media_type = "image"
                    media_url = embed["images"][0].get("thumb") or embed["images"][0].get("fullsize")
                # 2. Видео (в Bluesky превью лежит в embed.thumbnail)
                elif "thumbnail" in embed and embed["thumbnail"]:
                    media_type = "video"
                    media_url = embed["thumbnail"]
                # 3. Внешние ссылки (например, трейлер на YouTube)
                elif "external" in embed and embed["external"]:
                    ext = embed["external"]
                    if ext.get("thumb"):
                        ext_uri = ext.get("uri", "").lower()
                        media_type = "video" if ("youtu" in ext_uri or "vimeo" in ext_uri) else "link"
                        media_url = ext.get("thumb")

                posts.append({
                    "id": f"bsky_{rkey}",
                    "source": "bluesky",
                    "source_name": "Bluesky",
                    "channel": f"@{BLUESKY_HANDLE}",
                    "url": post_url,
                    "date": date_str,
                    "text": text,
                    "image": media_url,
                    "media_type": media_type
                })
                
                if len(posts) >= MAX_POSTS:
                    break
    except Exception as e:
        print(f"[!] Ошибка загрузки Bluesky: {e}")
    return posts[:MAX_POSTS]

def fetch_telegram_news():
    posts = []
    url = f"https://t.me/s/{TELEGRAM_CHANNEL}"
    try:
        req = urllib.request.Request(
            url, 
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            content = resp.read().decode("utf-8", errors="ignore")
            chunks = content.split('class="tgme_widget_message ')
            
            # Обходим сообщения в обратном порядке (от свежих к старым)
            for chunk in reversed(chunks[1:]):
                post_match = re.search(r'data-post="([^"]+)"', chunk)
                if not post_match:
                    continue
                post_id_full = post_match.group(1)
                post_num = post_id_full.split("/")[-1]
                post_url = f"https://t.me/{post_id_full}"
                
                # Дата
                time_match = re.search(r'<time[^>]*datetime="([^"]+)"', chunk)
                date_str = time_match.group(1) if time_match else datetime.now(timezone.utc).isoformat()
                
                # Текст поста
                clean_text = ""
                text_match = re.search(r'class="tgme_widget_message_text[^>]*>(.*?)</div>', chunk, re.DOTALL)
                if text_match:
                    raw_text = text_match.group(1)
                    clean_text = re.sub(r'<br\s*/?>', '\n', raw_text)
                    clean_text = re.sub(r'<[^>]+>', '', clean_text)
                    clean_text = html.unescape(clean_text).strip()
                
                # Медиа: видео, фото или превью ссылки
                media_type = None
                media_url = None
                
                # 1. Видео превью (tgme_widget_message_video_thumb)
                v_thumb = re.search(r'tgme_widget_message_video_thumb"[^>]*style="[^"]*background-image:url\(\'([^\']+)\'\)', chunk)
                # 2. Фото (tgme_widget_message_photo_wrap)
                p_thumb = re.search(r'tgme_widget_message_photo_wrap"[^>]*style="[^"]*background-image:url\(\'([^\']+)\'\)', chunk)
                # 3. Превью ссылки (например, YouTube)
                l_thumb = re.search(r'link_preview_image"[^>]*style="[^"]*background-image:url\(\'([^\']+)\'\)', chunk)
                if not l_thumb:
                    l_thumb = re.search(r'tgme_widget_message_link_preview"[^>]*style="[^"]*background-image:url\(\'([^\']+)\'\)', chunk)

                if v_thumb:
                    media_type = "video"
                    media_url = v_thumb.group(1)
                elif p_thumb:
                    media_type = "image"
                    media_url = p_thumb.group(1)
                elif l_thumb:
                    media_type = "link"
                    media_url = l_thumb.group(1)

                if not clean_text and not media_url:
                    continue

                posts.append({
                    "id": f"tg_{post_num}",
                    "source": "telegram",
                    "source_name": "Telegram",
                    "channel": f"@{TELEGRAM_CHANNEL}",
                    "url": post_url,
                    "date": date_str,
                    "text": clean_text,
                    "image": media_url,
                    "media_type": media_type
                })
                
                if len(posts) >= MAX_POSTS:
                    break
    except Exception as e:
        print(f"[!] Ошибка загрузки Telegram: {e}")
    return posts

def main():
    os.makedirs("data", exist_ok=True)
    
    print("[*] Загрузка новостей из Bluesky (EN)...")
    bsky_posts = fetch_bluesky_news()
    print(f"[+] Получено {len(bsky_posts)} постов из Bluesky")
    
    print("[*] Загрузка новостей из Telegram (RU)...")
    tg_posts = fetch_telegram_news()
    print(f"[+] Получено {len(tg_posts)} постов из Telegram")
    
    news_data = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "ru": tg_posts,
        "en": bsky_posts
    }
    
    out_path = "data/news.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(news_data, f, ensure_ascii=False, indent=2)
    
    print(f"[✓] Успешно сохранено в {out_path}")

if __name__ == "__main__":
    main()
