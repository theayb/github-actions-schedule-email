"""Fetch daily AI news from free RSS feeds and email via Gmail SMTP.

Env vars (set as GitHub Secrets):
  GMAIL_USERNAME: full Gmail address (sender, e.g. you@gmail.com)
  GMAIL_APP_PASSWORD: 16-char Gmail App Password (not your login password)
  TO_EMAIL: recipient address (defaults to GMAIL_USERNAME if unset)

Stdlib only - no pip install needed.
"""
import html
import os
import smtplib
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

FEEDS = [
    (
        "Google News - AI",
        "https://news.google.com/rss/search?q=%22artificial%20intelligence%22%20OR%20%22AI%22%20when%3A1d&hl=en-US&gl=US&ceid=US%3Aen",
    ),
    (
        "MIT Technology Review",
        "https://www.technologyreview.com/feed/",
    ),
]

MAX_PER_FEED = 7
MAX_TOTAL = 10


def fetch_feed(name, url):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "github-actions-schedule-email/1.0"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = resp.read()
    root = ET.fromstring(data)
    items = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        source = (item.findtext("source") or "").strip()
        if title and link:
            items.append(
                {"feed": name, "title": title, "link": link, "pub": pub, "source": source}
            )
        if len(items) >= MAX_PER_FEED:
            break
    return items


def build_email_body(all_items, date_str):
    text_lines = [f"Daily AI News - {date_str}", "", f"{len(all_items)} stories:", ""]
    html_parts = [
        f"<h2>Daily AI News - {html.escape(date_str)}</h2>",
        f"<p>{len(all_items)} stories from free RSS feeds.</p>",
        "<ol>",
    ]
    for it in all_items:
        meta = it["feed"]
        if it["source"]:
            meta += f" via {it['source']}"
        if it["pub"]:
            meta += f" - {it['pub']}"
        text_lines.append(f"- {it['title']}\n  {it['link']}\n  ({meta})\n")
        html_parts.append(
            f"<li><a href='{html.escape(it['link'], quote=True)}'>"
            f"{html.escape(it['title'])}</a><br>"
            f"<small>{html.escape(meta)}</small></li>"
        )
    html_parts.append("</ol>")
    text_lines.append("\nSent by github-actions-schedule-email.")
    return "\n".join(text_lines), "\n".join(html_parts)


def main():
    gmail_user = os.environ.get("GMAIL_USERNAME", "").strip()
    gmail_pass = os.environ.get("GMAIL_APP_PASSWORD", "").strip()
    to_email = os.environ.get("TO_EMAIL", "").strip() or gmail_user

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    all_items = []
    for name, url in FEEDS:
        try:
            found = fetch_feed(name, url)
            print(f"Fetched {len(found)} items from {name}")
            all_items.extend(found)
        except Exception as e:
            print(f"WARNING: failed to fetch {name}: {e}", file=sys.stderr)
        if len(all_items) >= MAX_TOTAL:
            break
    all_items = all_items[:MAX_TOTAL]

    if not all_items:
        print("ERROR: no news items fetched, aborting.", file=sys.stderr)
        sys.exit(1)

    text_body, html_body = build_email_body(all_items, date_str)
    subject = f"Daily AI News - {date_str} ({len(all_items)} stories)"

    # Dry run when credentials are missing (useful for testing without secrets)
    if not gmail_user or not gmail_pass:
        print("INFO: Gmail secrets missing, printing preview instead of sending.\n")
        print(f"Subject: {subject}\n")
        print(text_body)
        return 0

    msg = MIMEMultipart("alternative")
    msg["From"] = gmail_user
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_user, gmail_pass)
        server.sendmail(gmail_user, [to_email], msg.as_string())

    print(f"Sent '{subject}' to {to_email}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
