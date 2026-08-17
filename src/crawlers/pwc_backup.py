from __future__ import annotations
import httpx

BASE = "https://paperswithcode.com/api/v1"

async def fetch_pwc_papers(limit: int = 1000):
    """Fetch ML papers and their linked repositories from the public Papers With Code API."""
    out = []
    page = 1
    async with httpx.AsyncClient(timeout=30, headers={"User-Agent": "FrontierAtlas-MVP/1.0"}) as client:
        while len(out) < limit:
            r = await client.get(f"{BASE}/papers/", params={"page": page, "items_per_page": min(100, limit-len(out)), "ordering": "-published"})
            r.raise_for_status()
            data = r.json()
            results = data.get("results", [])
            if not results:
                break
            for paper in results:
                paper_id = paper.get("id")
                repos = []
                if paper_id:
                    rr = await client.get(f"{BASE}/papers/{paper_id}/repositories/")
                    if rr.status_code == 200:
                        repos = rr.json().get("results", [])
                repos = sorted(repos, key=lambda x: x.get("stars") or 0, reverse=True)
                top = repos[0] if repos else {}
                out.append({
                    "schemaVersion": "1.0",
                    "recordType": "RESEARCH_PAPER",
                    "content": {
                        "title": paper.get("title"),
                        "authors": paper.get("authors", []),
                        "paper_url": paper.get("url_abs") or paper.get("url_pdf"),
                        "github_url": top.get("url"),
                        "github_stars": top.get("stars"),
                        "published_date": paper.get("published"),
                    }
                })
                if len(out) >= limit:
                    break
            if not data.get("next"):
                break
            page += 1
    return out
