from releaseguard.github_ingestion import build_release_request


class FakeGitHubClient:
    def get_pull_request(self, owner, name, number):
        return {
            "state": "open",
            "title": "Update payment dependencies",
            "html_url": "https://github.com/acme/payments/pull/12",
            "user": {"login": "contributor"},
            "base": {"ref": "main", "sha": "base123", "repo": {"full_name": "acme/payments"}},
            "head": {"ref": "deps/update", "sha": "head456"},
        }

    def get_pull_request_files(self, owner, name, number):
        return [
            {"filename": "requirements.txt", "patch": "@@ -1 +1,2 @@\n-fastapi\n+fastapi==0.115.0\n+requests"},
            {"filename": "src/auth.py", "patch": "@@ -1 +1 @@\n-old\n+verify = False"},
        ]


def test_build_release_request_maps_pr_and_added_manifest_lines():
    request = build_release_request(FakeGitHubClient(), "acme", "payments", 12)
    assert request.repository == "acme/payments"
    assert request.pull_request == 12
    assert request.base_branch == "main"
    assert request.head_branch == "deps/update"
    assert len(request.changed_files) == 2
    assert request.dependency_manifest == "fastapi==0.115.0\nrequests"
    assert request.metadata["head_sha"] == "head456"


def test_manifest_patch_does_not_include_removed_lines():
    request = build_release_request(FakeGitHubClient(), "acme", "payments", 12)
    assert "fastapi\n" not in request.dependency_manifest
