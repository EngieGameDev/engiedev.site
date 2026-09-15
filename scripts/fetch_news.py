#!/usr/bin/env python3
"""
Скрипт сбора новостей для EngieDEV Team
- Telegram (@gd_engie) -> лента на русском языке (RU)
- Bluesky (engiedev.bsky.social) -> лента на английском языке (EN)
Без API-ключей, ботов и токенов — только публичные ленты.
"""

import urllib.request
import json
import re
import html
from datetime import datetime, timezone
import os

TELEGRAM_CHANNEL = "gd_engie"
BLUESKY_HANDLE = "engiedev.bsky.social"
MAX_POSTS = 8

def fetch_bluesky_news():
    posts = []
    url = f"https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed?actor={BLUESKY_HANDLE}&limit={MAX_POSTS}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "EngieDEV-News-Bot/1.0"})
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            for item in data.get("feed", []):
                post = item.get("post", {})
                rec = post.get("record", {})
                
                # Игнорируем ответы на чужие твиты (если это реплай), оставляем только основные посты и девлоги
                if rec.get("reply"):
                    continue

                uri = post.get("uri", "")
                rkey = uri.split("/")[-1] if uri else ""
                post_url = f"https://bsky.app/profile/{BLUESKY_HANDLE}/post/{rkey}" if rkey else f"https://bsky.app/profile/{BLUESKY_HANDLE}"
                
                text = rec.get("text", "").strip()
                if not text:
                    continue

                date_str = rec.get("createdAt", "")
                
                # Извлекаем картинку, если есть
                image_url = None
                embed = post.get("embed", {})
                if "images" in embed and embed["images"]:
                    image_url = embed["images"][0].get("thumb") or embed["images"][0].get("fullsize")
                elif "media" in embed and "images" in embed["media"] and embed["media"]["images"]:
                    image_url = embed["media"]["images"][0].get("thumb") or embed["media"]["images"][0].get("fullsize")

                posts.append({
                    "id": f"bsky_{rkey}",
                    "source": "bluesky",
                    "source_name": "Bluesky",
                    "channel": f"@{BLUESKY_HANDLE}",
                    "url": post_url,
                    "date": date_str,
                    "text": text,
                    "image": image_url
                })
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
                text_match = re.search(r'class="tgme_widget_message_text[^>]*>(.*?)</div>', chunk, re.DOTALL)
                if not text_match:
                    continue
                raw_text = text_match.group(1)
                
                # Преобразуем <br> и ссылки в читаемый вид
                clean_text = re.sub(r'<br\s*/?>', '\n', raw_text)
                clean_text = re.sub(r'<[^>]+>', '', clean_text)
                clean_text = html.unescape(clean_text).strip()
                
                if not clean_text:
                    continue
                
                # Картинка (если прикреплена)
                image_url = None
                img_match = re.search(r'tgme_widget_message_photo_wrap"[^>]*style="[^"]*background-image:url\(\'([^\']+)\'\)', chunk)
                if img_match:
                    image_url = img_match.group(1)
                
                posts.append({
                    "id": f"tg_{post_num}",
                    "source": "telegram",
                    "source_name": "Telegram",
                    "channel": f"@{TELEGRAM_CHANNEL}",
                    "url": post_url,
                    "date": date_str,
                    "text": clean_text,
                    "image": image_url
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
