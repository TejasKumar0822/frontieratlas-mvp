from __future__ import annotations

import argparse
import asyncio
import json
import os

import yaml
from dotenv import load_dotenv

from src.utils.http import AsyncHttp
from src.crawlers.rss import fetch_feed
from src.crawlers.pwc import fetch_pwc_papers
from src.crawlers.yc import YCStartupCrawler
from src.crawlers.product_hunt import fetch_products
from src.storage.db import upsert_record
from src.export import export_all
from src.llm.orchestrator import LLMOrchestrator


load_dotenv()


# ============================================================
# LLM EXTRACTION
# ============================================================

async def extract_with_llm(
    llm,
    llm_sem,
    source_data,
    schema,
    label,
):
    """
    Run one LLM extraction while respecting the
    configured concurrency limit.
    """

    if llm is None:
        return source_data

    async with llm_sem:

        try:

            extracted = await llm.extract(
                json.dumps(
                    source_data,
                    ensure_ascii=False,
                ),
                schema,
            )

            if not isinstance(
                extracted,
                dict,
            ):
                print(
                    f"{label} LLM returned invalid structure"
                )
                return source_data

            extracted_content = extracted.get(
                "content"
            )

            if isinstance(
                extracted_content,
                dict,
            ):
                source_data.update(
                    extracted_content
                )

            return source_data

        except Exception as e:

            print(
                f"{label} LLM extraction failed: {e}"
            )

            # Keep original source data if the LLM
            # fails. The source remains the truth.
            return source_data


# ============================================================
# CONCURRENT LLM PROCESSING
# ============================================================

async def process_llm_records(
    records,
    llm,
    llm_sem,
    schema,
    label,
):
    """
    Process records concurrently.

    The semaphore controls the maximum number of
    simultaneous LLM requests.
    """

    if not records:
        return records

    if llm is None:
        return records

    tasks = [
        asyncio.create_task(
            extract_with_llm(
                llm=llm,
                llm_sem=llm_sem,
                source_data=record,
                schema=schema,
                label=label,
            )
        )
        for record in records
    ]

    return await asyncio.gather(
        *tasks
    )


# ============================================================
# MAIN PIPELINE
# ============================================================

async def run(
    limit_startups=1000,
    limit_products=1000,
    limit_papers=1000,
    limit_news=1000,
    limit_jobs=1000,
    freshness_hours=24,
):

    # --------------------------------------------------------
    # Load configuration
    # --------------------------------------------------------

    with open(
        "config/sources.yaml",
        "r",
        encoding="utf-8",
    ) as f:

        cfg = yaml.safe_load(f)

    # --------------------------------------------------------
    # HTTP client
    # --------------------------------------------------------

    http = AsyncHttp(
        int(
            os.getenv(
                "CRAWL_CONCURRENCY",
                "20",
            )
        )
    )

    # --------------------------------------------------------
    # LLM
    # --------------------------------------------------------

    use_llm = (
        os.getenv(
            "USE_LLM",
            "false",
        ).lower()
        == "true"
    )

    llm = (
        LLMOrchestrator()
        if use_llm
        else None
    )

    llm_concurrency = int(
        os.getenv(
            "LLM_CONCURRENCY",
            "5",
        )
    )

    llm_sem = asyncio.Semaphore(
        llm_concurrency
    )

    if llm:

        print(
            f"LLM: enabled "
            f"(concurrency={llm_concurrency})"
        )

    else:

        print("LLM: disabled")

    try:

        # ====================================================
        # STARTUPS
        # ====================================================

        print(
            "\n========== STARTUPS =========="
        )

        startups = []

        try:

            startups = await YCStartupCrawler(
                http,
                cfg["startup"][
                    "ycombinator_directory"
                ],
            ).crawl(
                limit_startups
            )

            print(
                f"YC processed: "
                f"{len(startups)} startup records"
            )

        except Exception as e:

            print(
                f"YC crawler failed: {e}"
            )

        startup_schema = {
            "recordType": "STARTUP",
            "content": {
                "entityName": "string or null",
                "employeeCount": "integer or null",
            },
        }

        # Process startup content concurrently.
        if llm and startups:

            startup_contents = [
                r.get(
                    "content",
                    {},
                )
                for r in startups
            ]

            startup_contents = (
                await process_llm_records(
                    records=startup_contents,
                    llm=llm,
                    llm_sem=llm_sem,
                    schema=startup_schema,
                    label="STARTUP",
                )
            )

            for record, content in zip(
                startups,
                startup_contents,
            ):

                record["content"] = content

        startup_count = 0

        for r in startups:

            content = r.get(
                "content",
                {},
            )

            entity_name = (
                content.get(
                    "entityName"
                )
                or "unknown"
            )

            upsert_record(
                "STARTUP",
                r.get(
                    "source_url"
                ),
                entity_name.lower(),
                r,
                r.get(
                    "collectedAt"
                ),
            )

            startup_count += 1

        print(
            f"STARTUPS stored: {startup_count}"
        )

        # ====================================================
        # PRODUCTS
        # ====================================================

        print(
            "\n========== PRODUCTS =========="
        )

        product_count = 0

        try:

            products = await fetch_products(
                limit_products
            )

            product_schema = {
                "recordType": "PRODUCT",
                "content": {
                    "startupName": (
                        "string or null"
                    ),
                    "pricingModel": (
                        "FREE|FREEMIUM|PAID|"
                        "ENTERPRISE|null"
                    ),
                    "productName": (
                        "string or null"
                    ),
                },
            }

            if llm and products:

                product_contents = [
                    r.get(
                        "content",
                        {},
                    )
                    for r in products
                ]

                product_contents = (
                    await process_llm_records(
                        records=product_contents,
                        llm=llm,
                        llm_sem=llm_sem,
                        schema=product_schema,
                        label="PRODUCT",
                    )
                )

                for record, content in zip(
                    products,
                    product_contents,
                ):

                    record["content"] = content

            for r in products:

                content = r.get(
                    "content",
                    {},
                )

                product_name = (
                    content.get(
                        "productName"
                    )
                    or "unknown"
                )

                source_url = (
                    r.get(
                        "source",
                        {},
                    ).get(
                        "url"
                    )
                    or r.get(
                        "source_url"
                    )
                    or "unknown"
                )

                upsert_record(
                    "PRODUCT",
                    source_url,
                    product_name.lower(),
                    r,
                    r.get(
                        "collectedAt"
                    ),
                )

                product_count += 1

            print(
                f"PRODUCTS stored: "
                f"{product_count}"
            )

        except Exception as e:

            print(
                f"PRODUCTS skipped: {e}"
            )

        # ====================================================
        # RESEARCH PAPERS
        # ====================================================

        print(
            "\n========== RESEARCH PAPERS =========="
        )

        paper_count = 0

        try:

            papers = await fetch_pwc_papers(
                limit_papers
            )

            for r in papers:

                content = r.get(
                    "content",
                    {},
                )

                key = (
                    content.get(
                        "paper_url"
                    )
                    or content.get(
                        "title"
                    )
                    or "unknown"
                )

                upsert_record(
                    "RESEARCH_PAPER",
                    key,
                    key,
                    r,
                    content.get(
                        "published_date"
                    ),
                )

                paper_count += 1

            print(
                f"PAPERS stored: {paper_count}"
            )

        except Exception as e:

            print(
                f"PAPERS skipped: {e}"
            )

        # ====================================================
        # NEWS
        # ====================================================

        print(
            "\n========== NEWS =========="
        )

        news_count = 0

        news_schema = {
            "recordType": "NEWS",
            "content": {
                "title": "string or null",
                "published_date": (
                    "ISO-8601 timestamp or null"
                ),
                "body": "string or null",
            },
        }

        for source in cfg.get(
            "news",
            [],
        ):

            try:

                rows = await fetch_feed(
                    http,
                    source["name"],
                    source["url"],
                    freshness_hours,
                )

                # IMPORTANT:
                # Limit the total records used for this
                # smoke test.
                remaining = (
                    limit_news - news_count
                )

                if remaining <= 0:
                    break

                rows = rows[:remaining]

                print(
                    f"RSS processed: "
                    f"{source['name']} -> "
                    f"{len(rows)} fresh records"
                )

                if llm and rows:

                    rows = await process_llm_records(
                        records=rows,
                        llm=llm,
                        llm_sem=llm_sem,
                        schema=news_schema,
                        label="NEWS",
                    )

                for row in rows:

                    payload = {
                        "schemaVersion": "1.0",
                        "recordType": "NEWS",
                        "content": row,
                    }

                    key = (
                        row.get("url")
                        or row.get("title")
                        or "unknown"
                    )

                    upsert_record(
                        "NEWS",
                        key,
                        key,
                        payload,
                        row.get(
                            "published_date"
                        ),
                    )

                    news_count += 1

            except Exception as e:

                print(
                    f"RSS skipped: "
                    f"{source.get('name')} "
                    f"failed: {e}"
                )

        print(
            f"NEWS stored: {news_count}"
        )

        # ====================================================
        # JOBS
        # ====================================================

        print(
            "\n========== JOBS =========="
        )

        job_count = 0

        job_schema = {
            "recordType": "JOB",
            "content": {
                "company": (
                    "string or null"
                ),
                "date": (
                    "ISO-8601 timestamp or null"
                ),
                "is_remote": (
                    "boolean or null"
                ),
                "role_family": (
                    "string or null"
                ),
            },
        }

        for source in cfg.get(
            "jobs",
            [],
        ):

            try:

                rows = await fetch_feed(
                    http,
                    source["name"],
                    source["url"],
                    freshness_hours,
                )

                # IMPORTANT:
                # Limit total job records across all
                # sources during the smoke test.
                remaining = (
                    limit_jobs - job_count
                )

                if remaining <= 0:
                    break

                rows = rows[:remaining]

                print(
                    f"RSS processed: "
                    f"{source['name']} -> "
                    f"{len(rows)} fresh records"
                )

                if llm and rows:

                    rows = await process_llm_records(
                        records=rows,
                        llm=llm,
                        llm_sem=llm_sem,
                        schema=job_schema,
                        label="JOB",
                    )

                for row in rows:

                    payload = {
                        "schemaVersion": "1.0",
                        "recordType": "JOB",
                        "content": row,
                    }

                    key = (
                        row.get("url")
                        or row.get("title")
                        or "unknown"
                    )

                    upsert_record(
                        "JOB",
                        key,
                        key,
                        payload,
                        row.get(
                            "published_date"
                        ),
                    )

                    job_count += 1

            except Exception as e:

                print(
                    f"RSS skipped: "
                    f"{source.get('name')} "
                    f"failed: {e}"
                )

        print(
            f"JOBS stored: {job_count}"
        )

    finally:

        await http.close()

    # ========================================================
    # EXPORT
    # ========================================================

    print(
        "\n========== EXPORT =========="
    )

    try:

        output = export_all()

        print(
            f"Export completed: {output}"
        )

    except Exception as e:

        print(
            f"Export failed: {e}"
        )


# ============================================================
# COMMAND LINE
# ============================================================

if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description=(
            "FrontierAtlas AI Engineer Demo MVP"
        )
    )

    parser.add_argument(
        "--startups",
        type=int,
        default=int(
            os.getenv(
                "STARTUP_LIMIT",
                "1000",
            )
        ),
    )

    parser.add_argument(
        "--products",
        type=int,
        default=int(
            os.getenv(
                "PRODUCT_LIMIT",
                "1000",
            )
        ),
    )

    parser.add_argument(
        "--papers",
        type=int,
        default=int(
            os.getenv(
                "PAPER_LIMIT",
                "1000",
            )
        ),
    )

    parser.add_argument(
        "--news",
        type=int,
        default=int(
            os.getenv(
                "NEWS_LIMIT",
                "1000",
            )
        ),
    )

    parser.add_argument(
        "--jobs",
        type=int,
        default=int(
            os.getenv(
                "JOB_LIMIT",
                "1000",
            )
        ),
    )

    parser.add_argument(
        "--freshness-hours",
        type=int,
        default=int(
            os.getenv(
                "FRESHNESS_HOURS",
                "24",
            )
        ),
    )

    args = parser.parse_args()

    asyncio.run(
        run(
            limit_startups=args.startups,
            limit_products=args.products,
            limit_papers=args.papers,
            limit_news=args.news,
            limit_jobs=args.jobs,
            freshness_hours=args.freshness_hours,
        )
    )