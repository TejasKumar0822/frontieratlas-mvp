import asyncio
import os
import random
from typing import Any
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential_jitter, retry_if_exception_type

TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "30"))

class AsyncHttp:
    def __init__(self, concurrency: int = 20):
        self.sem = asyncio.Semaphore(concurrency)
        self.client = httpx.AsyncClient(
            timeout=TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": "FrontierAtlas-MVP/1.0 (+research demo)"},
        )

    async def close(self):
        await self.client.aclose()

    @retry(
        stop=stop_after_attempt(int(os.getenv("MAX_RETRIES", "4"))),
        wait=wait_exponential_jitter(initial=1, max=20),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
        reraise=True,
    )
    async def get(self, url: str, **kwargs) -> httpx.Response:
        async with self.sem:
            response = await self.client.get(url, **kwargs)
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                await asyncio.sleep(float(retry_after) if retry_after else random.uniform(1, 3))
                raise httpx.NetworkError("429 rate limited")
            response.raise_for_status()
            return response
