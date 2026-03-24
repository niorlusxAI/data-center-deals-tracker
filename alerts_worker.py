import os
import smtplib
from email.mime.text import MIMEText
from datetime import datetime

import feedparser
import numpy as np
import pandas as pd
import re
from pathlib import Path

RSS_FEEDS = [
    "https://www.datacenterknowledge.com/rss.xml",
    "https://www.datacenterdynamics.com/en/rss/news/",
    "https://www.datacenterdynamics.com/en/rss/analysis/",
    "https://www.lightreading.com/rss_simple.asp?rss_section=Hyperscale-Data-Centers",
    "https://www.capacitymedia.com/rss/news",
]

DEAL_KEYWORDS = [
    "deal","acquisition","purchase","invest","investment","power",
    "sign","lands","lease","expansion","contract","secures","buy",
    "buys","bid","agreement","order","deploy","commit","award",
]

def fetch_deals():
    all_entries = []
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:15]:
                title = entry.get("title", "").strip()
                if not title or not any(w in title.lower() for w in DEAL_KEYWORDS):
                    continue
                published = entry.get("published_parsed")
                date_obj = datetime(*published[:6]) if published else datetime.utcnow()
                link = entry.get("link", "")
                all_entries.append({
                    "Date": date_obj.strftime("%Y-%m-%d %H:%M"),
                    "Title": title[:100] + "..." if len(title) > 100 else title,
                    "Link": link,
                })
        except Exception as e:
            print(f"Feed error {feed_url}: {e}")
    if not all_entries:
        return pd.DataFrame()
    return pd.DataFrame(all_entries).head(20)

def main():
    gmail_user = os.environ["GMAIL_USER"]
    gmail_pass = os.environ["GMAIL_PASS"]
    csv_path = Path("premium_emails.csv")
    if not csv_path.exists():
        print("No premium_emails.csv found.")
        return
    df_emails = pd.read_csv(csv_path)
    emails = df_emails["email"].dropna().astype(str).str.lower().tolist()
    deals = fetch_deals()
    if deals.empty:
        print("No deals today.")
        return
    table_md = deals.to_markdown(index=False)
    subject = f"Data Center Deals Daily Digest – {datetime.utcnow().strftime('%Y-%m-%d')}"
    for email in emails:
        msg = MIMEText("🚀 Latest AI / Cloud / Data Center deals:\n\n" + table_md)
        msg["Subject"] = subject
        msg["From"] = gmail_user
        msg["To"] = email
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(gmail_user, gmail_pass)
            server.send_message(msg)
        print(f"Sent digest to {email}")

if __name__ == "__main__":
    main()
