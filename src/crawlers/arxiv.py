import httpx
import feedparser
from datetime import datetime, timezone


async def fetch_arxiv(limit: int = 1000):
    url = "https://export.arxiv.org/api/query"
    params = {
        "search_query": "cat:cs.AI OR cat:cs.LG OR cat:cs.CL OR cat:cs.CV",
        "start": 0,
        "max_results": min(limit, 2000),
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
    feed = feedparser.parse(r.text)
    papers = []
    for e in feed.entries:
        papers.append({
            "schemaVersion": "1.0",
            "recordType": "RESEARCH_PAPER",
            "content": {
                "title": e.get("title", "").strip(),
                "authors": [a.get("name", "") for a in e.get("authors", [])],
                "paper_url": e.get("link"),
                "github_url": None,
                "github_stars": None,
                "published_date": e.get("published"),
            }
        })
    return papers
