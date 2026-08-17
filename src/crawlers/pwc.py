from __future__ import annotations

import asyncio
import re
import xml.etree.ElementTree as ET

import httpx


ARXIV_API = "https://export.arxiv.org/api/query"

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}


def _extract_arxiv_id(url: str | None) -> str | None:
    if not url:
        return None

    match = re.search(r"arxiv\.org/(?:abs|pdf)/([^?#]+)", url)

    if not match:
        return None

    return match.group(1).replace(".pdf", "")


def _parse_feed(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)

    papers = []

    for entry in root.findall("atom:entry", NS):
        title = entry.findtext("atom:title", default="", namespaces=NS)
        published = entry.findtext("atom:published", default="", namespaces=NS)

        summary = entry.findtext("atom:summary", default="", namespaces=NS)

        authors = []

        for author in entry.findall("atom:author", NS):
            name = author.findtext("atom:name", default="", namespaces=NS)

            if name:
                authors.append(name.strip())

        paper_url = None

        for link in entry.findall("atom:link", NS):
            href = link.attrib.get("href")
            rel = link.attrib.get("rel")

            if rel == "alternate" and href:
                paper_url = href
                break

        if not paper_url:
            entry_id = entry.findtext("atom:id", default="", namespaces=NS)

            if entry_id:
                paper_url = entry_id.strip()

        arxiv_id = _extract_arxiv_id(paper_url)

        if not arxiv_id:
            continue

        papers.append(
            {
                "title": " ".join(title.split()),
                "authors": authors,
                "paper_url": paper_url,
                "published_date": published,
                "arxiv_id": arxiv_id,
                "summary": " ".join(summary.split()),
            }
        )

    return papers


async def fetch_pwc_papers(limit: int = 1000):
    """
    Research-paper adapter.

    The original Papers With Code API used by the first version of this
    project is no longer reliable. This implementation uses arXiv's public
    Atom API for paper metadata while preserving the project's existing
    RESEARCH_PAPER output schema.

    GitHub enrichment is intentionally left nullable when a repository
    cannot be reliably identified.
    """

    out = []

    batch_size = min(100, max(1, limit))
    start = 0

    query = "cat:cs.AI OR cat:cs.LG OR cat:cs.CV OR cat:cs.CL"

    headers = {
        "User-Agent": "FrontierAtlas-MVP/1.0 (research ingestion)"
    }

    async with httpx.AsyncClient(
        timeout=60,
        headers=headers,
        follow_redirects=True,
    ) as client:

        while len(out) < limit:

            params = {
                "search_query": query,
                "start": start,
                "max_results": batch_size,
                "sortBy": "submittedDate",
                "sortOrder": "descending",
            }

            response = await client.get(
                ARXIV_API,
                params=params,
            )

            response.raise_for_status()

            papers = _parse_feed(response.text)

            if not papers:
                break

            for paper in papers:

                out.append(
                    {
                        "schemaVersion": "1.0",
                        "recordType": "RESEARCH_PAPER",
                        "source": {
                            "name": "arXiv",
                            "url": paper["paper_url"],
                        },
                        "content": {
                            "title": paper["title"],
                            "authors": paper["authors"],
                            "paper_url": paper["paper_url"],
                            "github_url": None,
                            "github_stars": None,
                            "published_date": paper["published_date"],
                        },
                    }
                )

                if len(out) >= limit:
                    break

            start += len(papers)

            if len(papers) < batch_size:
                break

            # Be polite to arXiv between API requests.
            await asyncio.sleep(3)

    return out[:limit]