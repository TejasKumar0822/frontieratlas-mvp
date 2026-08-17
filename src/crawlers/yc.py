from __future__ import annotations

from datetime import datetime, timezone

from src.utils.http import AsyncHttp


YC_API = "https://yc-oss.github.io/api/companies/all.json"


class YCStartupCrawler:
    """
    Acquire YC startup records from the public YC company dataset.

    The dataset is derived from the YC company directory and provides
    structured company information without depending on the current
    YC directory HTML markup.
    """

    def __init__(
        self,
        http: AsyncHttp,
        base_url: str = "https://www.ycombinator.com/companies",
    ):
        self.http = http
        self.base_url = base_url

    async def crawl(self, limit: int = 1000):
        response = await self.http.get(YC_API)

        data = response.json()

        if not isinstance(data, list):
            raise ValueError("Unexpected YC API response format")

        rows = []
        seen = set()

        for company in data:

            name = (company.get("name") or "").strip()

            if not name:
                continue

            canonical_key = name.casefold()

            if canonical_key in seen:
                continue

            seen.add(canonical_key)

            company_url = (
                company.get("url")
                or f"{self.base_url}/{company.get('slug', '')}"
            )

            team_size = company.get("team_size")

            try:
                employee_count = (
                    int(team_size)
                    if team_size is not None
                    else None
                )
            except (TypeError, ValueError):
                employee_count = None

            collected_at = datetime.now(
                timezone.utc
            ).isoformat()

            rows.append(
                {
                    "schemaVersion": "1.0",
                    "recordType": "STARTUP",
                    "source": {
                        "name": "Y Combinator",
                        "url": self.base_url,
                    },
                    "content": {
                        "entityName": name[:200],
                        "employeeCount": employee_count,
                    },
                    "collectedAt": collected_at,
                    "source_url": company_url,
                }
            )

            if len(rows) >= limit:
                break

        print(
            f"YC processed: {len(rows)} startup records"
        )

        return rows