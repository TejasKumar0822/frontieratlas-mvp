# FrontierAtlas / GraphOne — Technical Architecture

## 1. Objective

Build a resilient ingestion platform that can acquire startup, product and research-paper entities at bulk scale, while continuously ingesting fresh AI news and jobs. The trial targets 1,000 startups, 1,000 products and 1,000 research papers, plus all qualifying fresh jobs/news; the architecture is designed to scale to 500,000+ records by adding infrastructure rather than rewriting business logic.

## 2. Logical architecture

```text
                    SOURCE REGISTRY
       ┌──────────────┬───────────────┬───────────────┐
       ▼              ▼               ▼               ▼
   Directories       APIs            RSS           Browser
       │              │               │             Render
       └──────────────┴───────────────┴───────────────┘
                              │
                         URL Scheduler
                              │
                    ┌─────────▼─────────┐
                    │ Async Crawl Pool  │
                    │ aiohttp/httpx     │
                    │ Playwright Async  │
                    └─────────┬─────────┘
                              │
                       Raw HTML / JSON
                              │
                    ┌─────────▼─────────┐
                    │ Content Cleaner   │
                    │ Date Normalizer   │
                    └─────────┬─────────┘
                              │
                    Freshness + Idempotency
                              │
                    ┌─────────▼─────────┐
                    │ LLM Orchestrator  │
                    │ Gemini → Groq     │
                    │        → DeepSeek│
                    └─────────┬─────────┘
                              │
                   413-aware chunking
                   429 retry + jitter
                              │
                    ┌─────────▼─────────┐
                    │ Schema Validator  │
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │ Entity Resolver   │
                    │ Normalize/Fuzzy   │
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │ Primary SQL Store │
                    └─────────┬─────────┘
                              │
              ┌───────────────┼────────────────┐
              ▼               ▼                ▼
          Raw Object       Graph DB         Vector DB
           Storage       relationships    semantic search
                              │
                              ▼
                       Sheets / Analytics
```

## 3. Trial implementation

The MVP uses SQLite to keep setup small and portable. The source registry is YAML. Async HTTP is bounded with a semaphore. RSS/API sources are preferred where available. A Playwright adapter can be added for permitted JavaScript-rendered sources.

### Source set

News: TechCrunch AI, VentureBeat AI, The Verge AI, Hugging Face Blog, MarkTechPost.

Jobs: RemoteFirstJobs AI, Jobicy, Himalayas, Remote OK, RemoteYeah.

Startups: Y Combinator public directory.

Products: Product Hunt GraphQL API, requiring a public API token.

Research: arXiv API, with optional GitHub repository enrichment.

## 4. LLM orchestration

The LLM layer is not the source of truth. It only converts source content into the canonical JSON shape. Missing values are null. The source URL is stored with every record.

Fallback order:

1. Gemini Flash
2. Groq Llama
3. DeepSeek

### 429 handling

- Bound concurrency per provider.
- Retry transient 429/5xx responses.
- Exponential delay with random jitter.
- Fall back to the next provider after provider-level exhaustion.

### 413 handling

- Strip scripts, navigation, forms and other low-value HTML.
- Convert remaining HTML to text.
- Split text into semantic chunks.
- Start with the densest first six chunks.
- If a provider returns 413, retry with fewer chunks.
- Never invent omitted fields.

## 5. Freshness and duplicate processing

Every news/job item is normalized to an absolute timestamp. Items older than the configured 24-hour cutoff are discarded.

For distributed production operation, every work item receives a stable idempotency key such as a normalized URL hash. The queue claims the key; the database also enforces a unique constraint. This gives defense in depth against two crawler nodes processing the same URL.

## 6. Entity resolution

Raw names are normalized by:

- lowercasing;
- punctuation normalization;
- whitespace removal;
- legal suffix removal;
- exact canonical lookup;
- fuzzy matching only above a conservative threshold.

Every decision is written to the Entity Mapping Log. Ambiguous matches remain unresolved instead of being silently merged.

## 7. Storage strategy

### Trial

SQLite for zero-setup development and reproducibility.

### Production

PostgreSQL should be the primary system of record because entities, source provenance, uniqueness constraints and transactional writes are structured. Raw HTML belongs in object storage. Redis can provide caching and distributed locks.

A graph database is appropriate for relationships such as Startup → Product, Founder → Startup, Paper → Repository, and News → Entity. A vector store is useful for semantic search over descriptions, paper abstracts and news content.

## 8. Scaling to 500k+

The core scaling move is to make each stage stateless and queue-driven:

```text
Source registry
      ↓
Message queue
      ↓
Crawler workers  × N
      ↓
Extraction queue
      ↓
LLM workers      × N
      ↓
Resolution queue
      ↓
Persistence workers × N
```

Workers can be horizontally scaled by increasing replicas. Partitioning can be by source, entity type or hash of URL. Rate limits are controlled independently for each provider and source domain.

At 500k+, the system should add:

- Kafka/SQS/Pub/Sub for durable queues;
- PostgreSQL with appropriate indexes/partitions;
- object storage for raw pages;
- Redis for idempotency/cache/locks;
- autoscaling worker pools;
- centralized logs and metrics;
- distributed tracing;
- dead-letter queues for permanently failed records;
- periodic reprocessing of DLQ items;
- provider-level budgets and circuit breakers.

No entity-specific business logic needs to change; infrastructure and worker counts change.

## 9. Anti-bot strategy

Use official APIs or public feeds first. Respect robots.txt, terms of service and rate limits. For sources that legitimately require JavaScript rendering, use Playwright Async with bounded concurrency and caching. Do not attempt to defeat CAPTCHAs or security controls; if a source blocks permitted automation, route to an official API or alternative legitimate source.

## 10. Observability

Track at minimum:

- URLs discovered / fetched / failed;
- HTTP status distribution;
- 429 count and retry count;
- 413 count and chunk reductions;
- LLM provider success/failure rate;
- JSON validation failure rate;
- entity resolution match rate;
- duplicate rate;
- freshness lag;
- throughput per worker;
- end-to-end processing latency.

## 11. Integrity controls

Every record must trace back to a legitimate source URL. The pipeline should never fabricate missing values. Source content, extracted JSON, timestamps, model/provider used and validation result should be auditable in production.
