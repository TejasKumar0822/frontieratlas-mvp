from __future__ import annotations
from datetime import datetime, timedelta, timezone
import re
from email.utils import parsedate_to_datetime
from bs4 import BeautifulSoup

RELATIVE = re.compile(r"(?P<n>\d+)\s*(?P<u>minute|minutes|min|mins|hour|hours|hr|hrs|day|days)\s*ago", re.I)


def parse_date(value: str | None, now: datetime | None = None) -> datetime | None:
    if not value:
        return None
    now = now or datetime.now(timezone.utc)
    text = value.strip()
    m = RELATIVE.search(text)
    if m:
        n = int(m.group("n"))
        unit = m.group("u").lower()
        if unit.startswith("minute") or unit.startswith("min"):
            return now - timedelta(minutes=n)
        if unit.startswith("hour") or unit.startswith("hr"):
            return now - timedelta(hours=n)
        return now - timedelta(days=n)
    try:
        dt = parsedate_to_datetime(text)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d", "%b %d, %Y", "%B %d, %Y"):
        try:
            dt = datetime.strptime(text, fmt)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def extract_page_date(html: str) -> datetime | None:
    soup = BeautifulSoup(html, "html.parser")
    candidates = []
    for attrs in [
        {"property": "article:published_time"},
        {"property": "og:published_time"},
        {"name": "date"},
        {"name": "pubdate"},
        {"itemprop": "datePublished"},
    ]:
        tag = soup.find("meta", attrs=attrs)
        if tag and tag.get("content"):
            candidates.append(tag["content"])
    for tag in soup.find_all("time"):
        if tag.get("datetime"):
            candidates.append(tag["datetime"])
        if tag.get_text(strip=True):
            candidates.append(tag.get_text(" ", strip=True))
    for c in candidates:
        dt = parse_date(c)
        if dt:
            return dt
    return None
