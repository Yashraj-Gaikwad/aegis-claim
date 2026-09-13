import os
from pathlib import Path
from urllib.parse import quote

import httpx


class GitHubPolicyTool:
    def __init__(
        self,
        twin_mode: bool | None = None,
        repository: str | None = None,
        policy_path: str = "policies/cms_cardiology_policy.md",
        client: httpx.Client | None = None,
    ) -> None:
        self.twin_mode = (
            os.getenv("TWIN_MODE", "true").strip().lower() == "true"
            if twin_mode is None
            else twin_mode
        )
        self.repository = repository or os.getenv("GITHUB_REPOSITORY")
        self.policy_path = policy_path
        self.token = os.getenv("GITHUB_TOKEN")
        self.client = client or httpx.Client(timeout=15.0)
        self._policy_commit_sha: str | None = None

    def fetch_policy(self, cpt_code: str) -> str:
        if self.twin_mode:
            policy_file = Path(__file__).resolve().parents[2] / self.policy_path
            return policy_file.read_text(encoding="utf-8")

        response = self.client.get(
            f"{self._repository_url()}/contents/{quote(self.policy_path)}",
            headers={**self._headers(), "Accept": "application/vnd.github.raw+json"},
            params={"ref": os.getenv("GITHUB_REF", "main")},
        )
        response.raise_for_status()
        return response.text

    def get_policy_commit_sha(self) -> str:
        if self.twin_mode:
            return "sha_c9f482a"
        if self._policy_commit_sha:
            return self._policy_commit_sha

        response = self.client.get(
            f"{self._repository_url()}/commits",
            headers=self._headers(),
            params={"path": self.policy_path, "sha": os.getenv("GITHUB_REF", "main"), "per_page": 1},
        )
        response.raise_for_status()
        commits = response.json()
        if not commits:
            raise LookupError(f"No GitHub commit found for {self.policy_path}")
        self._policy_commit_sha = commits[0]["sha"]
        return self._policy_commit_sha

    def _repository_url(self) -> str:
        if not self.repository:
            raise ValueError("GITHUB_REPOSITORY is required when TWIN_MODE=false")
        return f"https://api.github.com/repos/{self.repository}"

    def _headers(self) -> dict[str, str]:
        if not self.token:
            raise ValueError("GITHUB_TOKEN is required when TWIN_MODE=false")
        return {
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }
