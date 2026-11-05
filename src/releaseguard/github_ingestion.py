"""Convert read-only GitHub pull-request data into ReleaseGuard requests."""
from __future__ import annotations

from .github_client import GitHubClient
from .models import ChangedFile, ReleaseRequest, TestSummary


def _added_manifest_lines(patch: str) -> list[str]:
    lines = []
    for line in patch.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            candidate = line[1:].strip()
            if candidate and not candidate.startswith("#"):
                lines.append(candidate)
    return lines


def build_release_request(client: GitHubClient, owner: str, name: str, number: int) -> ReleaseRequest:
    pr = client.get_pull_request(owner, name, number)
    files = client.get_pull_request_files(owner, name, number)
    changed_files: list[ChangedFile] = []
    manifest_lines: list[str] = []

    for item in files:
        filename = str(item.get("filename", ""))
        patch = str(item.get("patch") or "")[:100_000]
        if not filename:
            continue
        changed_files.append(ChangedFile(path=filename, patch=patch))
        lower = filename.lower()
        if lower.endswith(("requirements.txt", "requirements-dev.txt")):
            manifest_lines.extend(_added_manifest_lines(patch))

    if not changed_files:
        # The domain request currently requires at least one file. Fail closed if GitHub has no diff.
        raise ValueError("GitHub returned no changed files for this pull request.")

    base = pr.get("base") or {}
    head = pr.get("head") or {}
    repository = pr.get("base", {}).get("repo", {}).get("full_name") or f"{owner}/{name}"
    return ReleaseRequest(
        repository=repository,
        pull_request=number,
        title=str(pr.get("title") or f"Pull request #{number}"),
        base_branch=str((base.get("ref") or "main")),
        head_branch=str((head.get("ref") or "feature")),
        changed_files=changed_files,
        dependency_manifest="\n".join(manifest_lines) or None,
        dependency_ecosystem="python",
        test_summary=TestSummary(),
        api_compatibility_score=50,
        metadata={
            "source": "github_read_only_api",
            "pull_request_url": pr.get("html_url"),
            "author": (pr.get("user") or {}).get("login"),
            "head_sha": (head.get("sha")),
            "base_sha": (base.get("sha")),
            "changed_file_count": len(changed_files),
        },
    )
