from __future__ import annotations

import os
import re
from typing import Any

import httpx

_GITHUB_API = "https://api.github.com"
_USER_AGENT = "HolmiumAI/1.0"


def _headers() -> dict[str, str]:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        try:
            with open("/etc/holmium/secrets.env") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("GITHUB_TOKEN="):
                        token = line.split("=", 1)[1].strip("\"'")
                        break
        except (FileNotFoundError, OSError):
            pass

    h = {
        "User-Agent": _USER_AGENT,
        "Accept": "application/vnd.github.v3+json",
    }
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def scrape_github(query: str, repo: str | None = None) -> dict[str, Any]:
    client = httpx.Client(headers=_headers(), timeout=15.0)

    try:
        if repo:
            return _scrape_repo(client, repo)

        search_resp = client.get(
            f"{_GITHUB_API}/search/repositories",
            params={"q": query, "per_page": 5, "sort": "stars", "order": "desc"},
        )
        search_resp.raise_for_status()
        search_data = search_resp.json()

        repos = []
        for item in search_data.get("items", [])[:5]:
            full_name = item.get("full_name", "")
            repos.append({
                "name": item.get("name", ""),
                "full_name": full_name,
                "description": item.get("description", ""),
                "url": item.get("html_url", ""),
                "stars": item.get("stargazers_count", 0),
                "forks": item.get("forks_count", 0),
                "language": item.get("language"),
                "topics": item.get("topics", []),
            })

        return {"repositories": repos}

    except httpx.HTTPError as e:
        return {"error": f"GitHub API error: {e}"}
    finally:
        client.close()


def _scrape_repo(client: httpx.Client, repo: str) -> dict[str, Any]:
    info_resp = client.get(f"{_GITHUB_API}/repos/{repo}")
    if info_resp.status_code == 404:
        return {"error": f"Repository not found: {repo}"}
    info_resp.raise_for_status()
    info = info_resp.json()

    readme_text = ""
    try:
        readme_resp = client.get(
            f"{_GITHUB_API}/repos/{repo}/readme",
            headers={"Accept": "application/vnd.github.v3.raw"},
        )
        if readme_resp.status_code == 200:
            raw = readme_resp.text
            readme_text = raw[:2000]
    except httpx.HTTPError:
        pass

    issues = []
    try:
        issues_resp = client.get(
            f"{_GITHUB_API}/repos/{repo}/issues",
            params={"state": "open", "per_page": 10, "sort": "created", "direction": "desc"},
        )
        if issues_resp.status_code == 200:
            for issue in issues_resp.json():
                issues.append({
                    "number": issue.get("number"),
                    "title": issue.get("title", ""),
                    "state": issue.get("state", ""),
                    "url": issue.get("html_url", ""),
                    "created_at": issue.get("created_at", ""),
                })
    except httpx.HTTPError:
        pass

    return {
        "name": info.get("full_name", repo),
        "description": info.get("description", ""),
        "stars": info.get("stargazers_count", 0),
        "forks": info.get("forks_count", 0),
        "language": info.get("language"),
        "topics": info.get("topics", []),
        "license": info.get("license", {}).get("spdx_id") if info.get("license") else None,
        "url": info.get("html_url", ""),
        "readme_preview": readme_text[:2000],
        "open_issues": issues[:10],
    }


def register_search_tools(registry: Any) -> None:
    registry.register(
        name="scrape_github",
        description="Search GitHub repositories or get details about a specific repo (README preview, open issues). Requires GITHUB_TOKEN in /etc/holmium/secrets.env for higher rate limits.",
        params_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query for repositories",
                },
                "repo": {
                    "type": "string",
                    "description": "Specific repository in format 'owner/repo' (e.g. 'nospc/holmium'). If provided, shows repo details instead of search results.",
                },
            },
            "required": ["query"],
        },
        handler=scrape_github,
    )
