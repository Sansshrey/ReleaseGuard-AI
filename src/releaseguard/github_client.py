"""Read-only GitHub REST API client for pull-request metadata and diffs."""
from __future__ import annotations

import os
import re
from urllib.parse import quote

import httpx

GITHUB_API = "https://api.github.com"
_REPO_PART = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")


class GitHubIntegrationError(RuntimeError):
    """A safe, user-facing GitHub integration error."""


class GitHubClient:
    def __init__(self, token: str | None = None, timeout: float = 15.0) -> None:
        self.token = token if token is not None else os.getenv("GITHUB_TOKEN")
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "ReleaseGuard-AI",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    @staticmethod
    def validate_repository(owner: str, name: str) -> str:
        if not _REPO_PART.fullmatch(owner) or not _REPO_PART.fullmatch(name):
            raise GitHubIntegrationError("Invalid GitHub owner or repository name.")
        return f"{owner}/{name}"

    def _get(self, url: str, params: dict | None = None):
        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=False) as client:
                response = client.get(url, headers=self._headers(), params=params)
        except httpx.TimeoutException as exc:
            raise GitHubIntegrationError("GitHub API request timed out.") from exc
        except httpx.HTTPError as exc:
            raise GitHubIntegrationError("Could not connect to the GitHub API.") from exc

        if response.status_code == 404:
            raise GitHubIntegrationError("Pull request or repository was not found or is not accessible.")
        if response.status_code in (401, 403):
            raise GitHubIntegrationError("GitHub denied access. Check token permissions and API rate limits.")
        if response.status_code == 422:
            raise GitHubIntegrationError("GitHub could not process this pull-request request.")
        if response.status_code >= 400:
            raise GitHubIntegrationError(f"GitHub API returned HTTP {response.status_code}.")
        try:
            return response.json()
        except ValueError as exc:
            raise GitHubIntegrationError("GitHub returned an invalid response.") from exc

    def get_pull_request(self, owner: str, name: str, number: int) -> dict:
        repository = self.validate_repository(owner, name)
        if number < 1:
            raise GitHubIntegrationError("Pull request number must be positive.")
        url = f"{GITHUB_API}/repos/{quote(repository, safe='/')}/pulls/{number}"
        data = self._get(url)
        if data.get("state") != "open":
            raise GitHubIntegrationError("Only open pull requests can be analysed in this MVP.")
        return data

    def get_pull_request_files(self, owner: str, name: str, number: int, max_files: int = 500) -> list[dict]:
        repository = self.validate_repository(owner, name)
        collected: list[dict] = []
        for page in range(1, 6):
            url = f"{GITHUB_API}/repos/{quote(repository, safe='/')}/pulls/{number}/files"
            batch = self._get(url, {"per_page": 100, "page": page})
            if not isinstance(batch, list):
                raise GitHubIntegrationError("GitHub returned an unexpected pull-request files response.")
            collected.extend(batch)
            if len(collected) > max_files:
                raise GitHubIntegrationError(f"Pull request exceeds the {max_files}-file analysis limit.")
            if len(batch) < 100:
                break
        return collected
