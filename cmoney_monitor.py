#!/usr/bin/env python3
"""
CMoney 用戶發文監控 - GitHub Actions 版本
每次執行只跑一次，由 GitHub Actions 定時觸發
已通知的文章 ID 存在 GitHub Gist
"""

import requests
import json
import os
import re
import smtplib
import sys
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# ==================== 設定區 ====================
USER_URL = "https://www.cmoney.tw/forum/user/7983967"
USER_NAME = "火火火奇門遁甲隱士發發發"

GMAIL_SENDER   = os.environ.get("GMAIL_SENDER", "")
GMAIL_PASSWORD = os.environ.get("GMAIL_PASSWORD", "")
EMAIL_RECEIVERS = ["yhes3103@gmail.com", "ygk1234w@gmail.com"]

GIST_TOKEN    = os.environ.get("GIST_TOKEN", "")
GIST_ID       = os.environ.get("GIST_ID", "")
GIST_FILENAME = "cmoney_seen_ids.json"
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


def gist_load() -> set:
    headers = {
        "Authorization": f"token {GIST_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    resp = requests.get(f"https://api.github.com/gists/{GIST_ID}", headers=headers, timeout=10)
    if resp.status_code != 200:
        print(f"[Gist] 讀取失敗: {resp.status_code}")
        return set()
    files = resp.json().get("files", {})
    if GIST_FILENAME not in files:
        return set()
    content = files[GIST_FILENAME].get("content", "{}")
    return set(json.loads(content).get("seen_ids", []))


def gist_save(seen: set):
    headers = {
        "Authorization": f"token {GIST_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    payload = {
        "files": {
            GIST_FILENAME: {
                "content": json.dumps(
                    {"seen_ids": list(seen), "updated": datetime.now().isoformat()},
                    ensure_ascii=False, indent=2
                )
            }
        }
    }
    resp = requests.patch(
        f"https://api.github.com/gists/{GIST_ID}",
        headers=headers, json=payload, timeout=10
    )
    print(f"[Gist] {'儲存成功' if resp.status_code == 200 else f'儲存失敗 {resp.status_code}'}")


def send_email(title: str, article_url: str):
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"📢 {USER_NAME} 發新文章：{title}"
        msg["From"] = GMAIL_SENDER
        msg["To"] = ", ".join(EMAIL_RECEIVERS)

        body_text = f"{USER_NAME} 剛剛發了新文章！\n\n標題：{title}\n連結：{article_url}"
        body_html = f"""
        <div style="font-family:sans-serif;max-width:500px;margin:auto;padding:24px;border:1px solid #eee;border-radius:8px;">
            <h2 style="color:#e53e3e;">📢 {USER_NAME} 發新文章！</h2>
            <p style="font-size:16px;"><b>標題：</b>{title}</p>
            <a href="{article_url}" style="display:inline-block;margin-top:12px;padding:10px 20px;background:#3182ce;color:white;border-radius:6px;text-decoration:none;">
                🔗 前往文章
            </a>
            <p style="margin-top:20px;color:#999;font-size:12px;">CMoney 發文監控自動通知</p>
        </div>
        """
        msg.attach(MIMEText(body_text, "plain", "utf-8"))
        msg.attach(MIMEText(body_html, "html", "utf-8"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_SENDER, GMAIL_PASSWORD)
            server.sendmail(GMAIL_SENDER, EMAIL_RECEIVERS, msg.as_string())

        print(f"  [Email] ✓ 已寄出通知")
    except Exception as e:
        print(f"  [Email] ✗ 寄送失敗: {e}")


def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 開始檢查...")

    if not all([GMAIL_SENDER, GMAIL_PASSWORD, GIST_TOKEN, GIST_ID]):
        print("錯誤：請確認所有環境變數都已設定")
        sys.exit(1)

    try:
        articles = fetch_articles()
        print(f"找到 {len(articles)} 篇文章")
    except Exception as e:
        print(f"抓取失敗: {e}")
        sys.exit(1)

    seen = gist_load()

    # 第一次執行：只初始化，不通知
    if not seen:
        print("首次執行，初始化文章清單（不發通知）")
        seen = {a["id"] for a in articles}
        gist_save(seen)
        print(f"已記錄 {len(seen)} 篇現有文章，之後只通知新文章")
        return

    new = [a for a in articles if a["id"] not in seen]

    if not new:
        print("沒有新文章")
        return

    print(f"發現 {len(new)} 篇新文章！")
    for a in new:
        print(f"  → {a['title']}")
        send_email(a["title"], a["url"])
        seen.add(a["id"])

    gist_save(seen)
    print("完成！")


if __name__ == "__main__":
    main()
