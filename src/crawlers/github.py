import os
import httpx


async def repo_metrics(repo_url: str):
    if not repo_url or "github.com/" not in repo_url:
        return None
    parts = repo_url.rstrip("/").split("github.com/")[-1].split("/")
    if len(parts) < 2:
        return None
    owner, repo = parts[0], parts[1].replace(".git", "")
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2026-03-10"}
    if os.getenv("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {os.getenv('GITHUB_TOKEN')}"
    async with httpx.AsyncClient(timeout=20, headers=headers) as client:
        r = await client.get(f"https://api.github.com/repos/{owner}/{repo}")
        if r.status_code != 200:
            return None
        data = r.json()
        return {"github_stars": data.get("stargazers_count"), "github_url": data.get("html_url")}
