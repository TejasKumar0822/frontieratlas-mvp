# FrontierAtlas / GraphOne — AI Engineer Demo MVP

This repository implements a trial-sized version of the ingestion architecture described in the supplied AI Engineer Demo Task.

## What is implemented

- Async HTTP crawling with bounded concurrency.
- RSS ingestion for 5 AI news sources and 5 remote-job sources.
- 24-hour freshness filtering and relative-date normalization.
- arXiv research-paper acquisition.
- GitHub enrichment helper for current `stargazers_count`.
- Y Combinator startup directory adapter.
- Product Hunt GraphQL adapter (requires a public API token).
- Multi-provider LLM orchestrator: Gemini → Groq → DeepSeek.
- Semantic chunking to reduce 413/context-window failures.
- Retry/backoff handling for network errors and 429 responses.
- Deterministic entity normalization + fuzzy fallback + mapping log.
- SQLite trial storage with uniqueness constraints for deduplication.
- Excel/CSV export matching the requested six tabs.
- Architecture document explaining how to scale the same design to 500k+ records.

## Important integrity rule

The assignment warns that hallucinated data causes disqualification. This implementation therefore treats source pages as the source of truth. Missing values remain `null`; the LLM is not allowed to invent them. Every stored record keeps a source URL.

## Quick start

```bash
python -m venv .venv
# Windows
.venv\\Scripts\\activate
# Linux/macOS
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

For Playwright-based sources, install the browser runtime:

```bash
playwright install chromium
```

Set at least one LLM key if you plan to use LLM extraction. Product Hunt requires `PRODUCT_HUNT_TOKEN`. A GitHub token is optional but recommended for higher API limits.

Run a small smoke test first:

```bash
python -m src.main --startups 20 --products 20 --papers 20
```

Then run the trial-sized extraction:

```bash
python -m src.main --startups 1000 --products 1000 --papers 1000
```

Outputs are written under `data/export/`:

- `frontieratlas_output.xlsx`
- `startups.csv`
- `products.csv`
- `research_papers.csv`
- `jobs.csv`
- `news.csv`
- `entity_mapping_log.csv`

## Architecture

```text
Sources → Scheduler → Async Workers → Raw Content → Cleaning/Date Logic
                                              ↓
                                      LLM Orchestrator
                                  Gemini → Groq → DeepSeek
                                              ↓
                                    JSON Validation
                                              ↓
                                   Entity Resolution
                                              ↓
                                    Deduplication/DB
                                      ↙          ↘
                                SQL Store      Graph/Vector (prod)
                                      ↓
                                Export / Sheets
```

The trial uses SQLite to minimize setup. The architecture document recommends PostgreSQL as the production system of record, object storage for raw HTML, a queue for distributed workers, and graph/vector stores for relationship and semantic workloads.

## Source choices

The source list is configurable in `config/sources.yaml`. RSS/API sources are preferred where available because they are machine-readable and reduce unnecessary page crawling. For blocked or JavaScript-heavy sources, the architecture calls for permitted browser rendering through Playwright rather than attempting to defeat security controls.

## 500k+ scaling plan

The code is organized so the crawling, extraction, entity resolution and persistence stages can be separated behind queues. To scale:

1. Replace the in-process scheduler with Kafka/SQS/Pub/Sub.
2. Run many stateless crawler workers.
3. Use a shared idempotency store and database uniqueness constraints.
4. Put raw HTML in object storage instead of local disk.
5. Add a rate-limit-aware LLM worker pool per provider.
6. Keep exponential backoff + jitter and provider fallback.
7. Partition work by source/entity type and autoscale workers.
8. Replace SQLite with PostgreSQL; add Redis for distributed locks/cache.
9. Add a graph database for relationships and a vector database for semantic retrieval.
10. Add metrics/tracing for throughput, failure rate, freshness lag, 429/413 rate, and extraction validity.

No application rewrite should be required; scaling is primarily an infrastructure and worker-count change.
