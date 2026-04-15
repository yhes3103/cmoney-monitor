#!/usr/bin/env python3
"""
CMoney 用戶發文監控 - GitHub Actions 版本
直接呼叫 CMoney 內部 API 取得文章列表（非爬 HTML）
已通知的文章 ID 存在 GitHub Gist
"""

import requests
import json
import os
import smtplib
import sys
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# ==================== 設定區 ====================
MEMBER_ID = "7983967"
USER_NAME = "火火火奇門遁甲隱士發發發"

# CMoney API
API_URL = "https://www.cmoney.tw/api/mach/api/Article/GetChannelsArticleByWeight"
ARTICLE_BASE_URL = "https://www.cmoney.tw/forum/article"

GMAIL_SENDER = os.environ.get("GMAIL_SENDER", "")
GMAIL_PASSWORD = os.environ.get("GMAIL_PASSWORD", "")
EMAIL_RECEIVERS = ["yhes3103@gmail.com", "ygk1234w@gmail.com"]

GIST_TOKEN = os.environ.get("GIST_TOKEN", "")
GIST_ID = os.environ.get("GIST_ID", "")
GIST_FILENAME = "cmoney_seen_ids.json"
# ================================================


def fetch_articles(max_retries: int = 3) -> list:
    """透過 CMoney API 取得最新文章列表"""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Content-Type": "application/json",
        "Origin": "https://www.cmoney.tw",
        "Referer": f"https://www.cmoney.tw/forum/user/{MEMBER_ID}",
    }

    # startScore 用超大數字 = 從最新文章開始抓
    params = {
        "startScore": "9999999999999999",
        "count": "30",
    }
    payload = {
        "items": [f"Member-All.{MEMBER_ID}"]
    }

    for attempt in range(1, max_retries + 1):
        try:
            print(f"  第 {attempt} 次嘗試呼叫 API...")
            resp = requests.post(
                API_URL,
                headers=headers,
                params=params,
                json=payload,
                timeout=20,
            )
            print(f"  HTTP {resp.status_code}, 回應長度: {len(resp.text)} 字元")

            if resp.status_code != 200:
                print(f"  API 回傳非 200: {resp.text[:200]}")
                if attempt < max_retries:
                    time.sleep(5)
                continue

            data = resp.json()

            if not isinstance(data, list):
                print(f"  API 回傳格式不是 list: {type(data)}")
                if attempt < max_retries:
                    time.sleep(5)
                continue

            articles = []
            for item in data:
                article_id = str(item.get("id", ""))
                title = item.get("content", {}).get("title", "（無標題）")
                url = f"{ARTICLE_BASE_URL}/{article_id}"
                articles.append({
                    "id": article_id,
                    "title": title,
                    "url": url,
                })

            return articles

        except requests.exceptions.RequestException as e:
            print(f"  第 {attempt} 次失敗: {e}")
            if attempt < max_retries:
                time.sleep(5)

    return []


def gist_load() -> set:
    """從 GitHub Gist 載入已看過的文章 ID"""
    headers = {
        "Authorization": f"token {GIST_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    try:
        resp = requests.get(
            f"https://api.github.com/gists/{GIST_ID}",
            headers=headers, timeout=10,
        )
        if resp.status_code != 200:
            print(f"[Gist] 讀取失敗: {resp.status_code}")
            return set()
        files = resp.json().get("files", {})
        if GIST_FILENAME not in files:
            return set()
        content = files[GIST_FILENAME].get("content", "{}")
        return set(json.loads(content).get("seen_ids", []))
    except Exception as e:
        print(f"[Gist] 讀取異常: {e}")
        return set()


def gist_save(seen: set):
    """儲存已看過的文章 ID 到 GitHub Gist"""
    headers = {
        "Authorization": f"token {GIST_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    payload = {
        "files": {
            GIST_FILENAME: {
                "content": json.dumps(
                    {"seen_ids": list(seen), "updated": datetime.now().isoformat()},
                    ensure_ascii=False, indent=2,
                )
            }
        }
    }
    try:
        resp = requests.patch(
            f"https://api.github.com/gists/{GIST_ID}",
            headers=headers, json=payload, timeout=10,
        )
        if resp.status_code == 200:
            print(f"[Gist] 儲存成功 ({len(seen)} 篇)")
        else:
            print(f"[Gist] 儲存失敗: {resp.status_code}")
    except Exception as e:
        print(f"[Gist] 儲存異常: {e}")


def send_email(title: str, article_url: str):
    """寄送 email 通知"""
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"📢 {USER_NAME} 發新文章：{title}"
        msg["From"] = GMAIL_SENDER
        msg["To"] = ", ".join(EMAIL_RECEIVERS)

        body_text = (
            f"{USER_NAME} 剛剛發了新文章！\n\n"
            f"標題：{title}\n"
            f"連結：{article_url}"
        )
        body_html = f"""
        <div style="font-family:sans-serif;max-width:500px;margin:auto;padding:24px;
                    border:1px solid #eee;border-radius:8px;">
          <h2 style="color:#e53e3e;">📢 {USER_NAME} 發新文章！</h2>
          <p style="font-size:16px;"><b>標題：</b>{title}</p>
          <a href="{article_url}"
             style="display:inline-block;margin-top:12px;padding:10px 20px;
                    background:#3182ce;color:white;border-radius:6px;
                    text-decoration:none;">
            🔗 前往文章
          </a>
          <p style="margin-top:20px;color:#999;font-size:12px;">
            CMoney 發文監控自動通知
          </p>
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

    # 透過 API 抓取文章
    articles = fetch_articles()
    print(f"找到 {len(articles)} 篇文章")

    if not articles:
        print("警告：沒有抓到任何文章")
        sys.exit(1)

    for a in articles[:5]:
        print(f"  📄 [{a['id']}] {a['title'][:50]}")
    if len(articles) > 5:
        print(f"  ... 還有 {len(articles) - 5} 篇")

    # 載入已看過的 ID
    seen = gist_load()
    print(f"[Gist] 已記錄 {len(seen)} 篇文章")

    # 第一次執行：只初始化，不通知
    if not seen:
        print("首次執行，初始化文章清單（不發通知）")
        seen = {a["id"] for a in articles}
        gist_save(seen)
        print(f"已記錄 {len(seen)} 篇現有文章，之後只通知新文章")
        return

    # 比對新文章
    new = [a for a in articles if a["id"] not in seen]

    if not new:
        print("沒有新文章")
        return

    print(f"🔔 發現 {len(new)} 篇新文章！")
    for a in new:
        print(f"  → {a['title']}")
        send_email(a["title"], a["url"])
        seen.add(a["id"])

    gist_save(seen)
    print("完成！")


if __name__ == "__main__":
    main()
