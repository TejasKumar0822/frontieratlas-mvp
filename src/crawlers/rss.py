import asyncio
from datetime import datetime, timezone, timedelta

import feedparser
import httpx

from src.utils.dates import parse_date
from src.utils.http import AsyncHttp


async def fetch_feed(
    http: AsyncHttp,
    name: str,
    url: str,
    freshness_hours: int = 24,
):
    """
    Fetch one RSS/Atom feed.

    A single unavailable/blocked source must not terminate the
    complete ingestion pipeline.
    """

    try:
        response = await http.get(url)

    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code if exc.response else "unknown"

        print(
            f"RSS skipped: {name} returned HTTP {status} "
            f"({url})"
        )

        return []

    except Exception as exc:
        print(
            f"RSS skipped: {name} failed with "
            f"{type(exc).__name__}: {exc}"
        )

        return []

    except BaseException:
        print(f"RSS skipped: {name} failed unexpectedly ({url})")
        return []

    feed = feedparser.parse(response.text)

    if getattr(feed, "bozo", False) and not feed.entries:
        print(f"RSS skipped: {name} returned an invalid/empty feed.")
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(
        hours=freshness_hours
    )

    rows = []

    for entry in feed.entries:
        raw_date = (
            entry.get("published")
            or entry.get("updated")
            or entry.get("pubDate")
        )

        dt = parse_date(raw_date)

        # The assignment requires strict freshness.
        if not dt or dt < cutoff:
            continue

        rows.append(
            {
                "source": name,
                "source_url": url,
                "url": entry.get("link"),
                "title": entry.get("title", "").strip(),
                "description": entry.get("summary", ""),
                "published_date": dt.isoformat(),
            }
        )

    print(
        f"RSS processed: {name} -> "
        f"{len(rows)} fresh records"
    )

    return rows