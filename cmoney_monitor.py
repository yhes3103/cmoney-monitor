#!/usr/bin/env python3
"""
CMoney 用戶發文監控 - Render.com 版本
每 30 秒檢查一次，有新文章時寄 Email 通知
"""

import requests
import json
import os
import re
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# ==================== 設定區 ====================
USER_URL = "https://www.cmoney.tw/forum/user/7983967"
USER_NAME = "火火火奇門遁甲隱士發發發"
POLL_INTERVAL = 30
STATE_FILE = "/tmp/seen_ids.json"

# 從環境變數讀取（Render 後台設定）
GMAIL_SENDER = os.environ.get("GMAIL_SENDER", "")      # 寄件信箱
GMAIL_PASSWORD = os.environ.get("GMAIL_PASSWORD", "")  # 應用程式密碼
EMAIL_RECEIVER = os.environ.get("EMAIL_RECEIVER", "")  # 收件信箱
# ================================================


def fetch_articles() -> list:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "zh-TW,zh;q=0.9",
    }
    resp = requests.get(USER_URL, headers=headers, timeout=15)
    resp.raise_for_status()

    articles = []
    seen = set()
    for full_url, article_id in re.findall(
        r'href="(https://www\.cmoney\.tw/forum/article/(\d+))"', resp.text
    ):
        if article_id in seen:
            continue
        seen.add(article_id)

        title = "（無標題）"
        m = re.search(
            rf'article/{article_id}.*?<h3[^>]*>(.*?)</h3>', resp.text, re.DOTALL
        )
        if m:
            title = re.sub(r"<[^>]+>", "", m.group(1)).strip()

        articles.append({"id": article_id, "title": title, "url": full_url})

    return articles


def load_seen() -> set:
    try:
        with open(STATE_FILE, "r") as f:
            return set(json.load(f).get("ids", []))
    except Exception:
        return set()


def save_seen(seen: set):
    with open(STATE_FILE, "w") as f:
        json.dump({"ids": list(seen)}, f)


def send_email(title: str, article_url: str):
    try:
        msg = MIMEMultipart("alternative")
        receivers = [r.strip() for r in EMAIL_RECEIVER.split(",")]
        msg["Subject"] = f"📢 {USER_NAME} 發新文章：{title}"
        msg["From"] = GMAIL_SENDER
        msg["To"] = ", ".join(receivers)

        body_text = f"{USER_NAME} 剛剛發了新文章！\n\n標題：{title}\n連結：{article_url}"
        body_html = f"""
        <div style="font-family: sans-serif; max-width: 500px; margin: auto; padding: 24px; border: 1px solid #eee; border-radius: 8px;">
            <h2 style="color: #e53e3e;">📢 {USER_NAME} 發新文章！</h2>
            <p style="font-size: 16px;"><b>標題：</b>{title}</p>
            <a href="{article_url}" style="display: inline-block; margin-top: 12px; padding: 10px 20px; background: #3182ce; color: white; border-radius: 6px; text-decoration: none;">
                🔗 前往文章
            </a>
            <p style="margin-top: 20px; color: #999; font-size: 12px;">CMoney 發文監控自動通知</p>
        </div>
        """

        msg.attach(MIMEText(body_text, "plain", "utf-8"))
        msg.attach(MIMEText(body_html, "html", "utf-8"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_SENDER, GMAIL_PASSWORD)
            server.sendmail(GMAIL_SENDER, receivers, msg.as_string())

        print(f"  [Email] ✓ 已寄出通知")
    except Exception as e:
        print(f"  [Email] ✗ 寄送失敗: {e}")


def main():
    print("=" * 50)
    print(f"CMoney 監控啟動 - {USER_NAME}")
    print(f"寄件：{GMAIL_SENDER} → 收件：{EMAIL_RECEIVER}")
    print(f"輪詢間隔：{POLL_INTERVAL} 秒")
    print("=" * 50)

    if not GMAIL_SENDER or not GMAIL_PASSWORD or not EMAIL_RECEIVER:
        print("錯誤：請設定 GMAIL_SENDER / GMAIL_PASSWORD / EMAIL_RECEIVER")
        return

    initialized = False

    while True:
        now = datetime.now().strftime("%H:%M:%S")
        try:
            articles = fetch_articles()
            seen = load_seen()

            if not initialized and not seen:
                seen = {a["id"] for a in articles}
                save_seen(seen)
                initialized = True
                print(f"[{now}] 初始化完成，已記錄 {len(seen)} 篇文章，開始監控...")
                time.sleep(POLL_INTERVAL)
                continue

            initialized = True
            new = [a for a in articles if a["id"] not in seen]

            if new:
                print(f"[{now}] 發現 {len(new)} 篇新文章！")
                for a in new:
                    print(f"  → {a['title']}")
                    send_email(a["title"], a["url"])
                    seen.add(a["id"])
                save_seen(seen)
            else:
                print(f"[{now}] 無新文章")

        except Exception as e:
            print(f"[{now}] 錯誤: {e}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
