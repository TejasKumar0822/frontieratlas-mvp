import os
import httpx
from datetime import datetime, timezone

QUERY = """
query($first:Int!, $after:String) {
  posts(first:$first, after:$after) {
    pageInfo { hasNextPage endCursor }
    edges { node {
      id name tagline url website createdAt
      topics { edges { node { name } } }
      user { name }
    }}
  }
}
"""

async def fetch_products(limit: int = 1000):
    token = os.getenv("PRODUCT_HUNT_TOKEN")
    if not token:
        raise RuntimeError("PRODUCT_HUNT_TOKEN is required for Product Hunt extraction. Create a public-scope token in the Product Hunt developer dashboard.")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    out, cursor = [], None
    async with httpx.AsyncClient(timeout=30, headers=headers) as client:
        while len(out) < limit:
            r = await client.post("https://api.producthunt.com/v2/api/graphql", json={"query": QUERY, "variables": {"first": min(50, limit-len(out)), "after": cursor}})
            r.raise_for_status()
            data = r.json()["data"]["posts"]
            for edge in data["edges"]:
                n = edge["node"]
                out.append({
                    "schemaVersion": "1.0",
                    "recordType": "PRODUCT",
                    "source": {"name": "Product Hunt", "url": n.get("url")},
                    "content": {
                        "startupName": n.get("user", {}).get("name"),
                        "pricingModel": None,
                        "productName": n.get("name"),
                        "tagline": n.get("tagline"),
                        "website": n.get("website"),
                    },
                    "collectedAt": datetime.now(timezone.utc).isoformat(),
                })
            if not data["pageInfo"]["hasNextPage"]:
                break
            cursor = data["pageInfo"]["endCursor"]
    return out
