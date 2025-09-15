import logging
from typing import Tuple
import requests

from config import settings

logger = logging.getLogger(__name__)


def parse_repo_full_name(repo_full_name: str) -> Tuple[str, str]:
    if "/" not in repo_full_name:
        raise ValueError(f"Invalid repo full name: {repo_full_name}")
    owner, repo = repo_full_name.split("/", 1)
    return owner, repo


def fetch_pr_diff(repo_full_name: str, pr_number: int) -> str:
    owner, repo = parse_repo_full_name(repo_full_name)
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
    headers = {
        "Accept": "application/vnd.github.v3.diff",
        "Authorization": f"Bearer {settings.github_token}",
        "User-Agent": "pr-review-notifier/1.0",
    }

    logger.info("Fetching PR diff from GitHub", extra={"owner": owner, "repo": repo, "pr": pr_number})
    resp = requests.get(url, headers=headers, timeout=30)
    if resp.status_code != 200:
        logger.error("Failed to fetch PR diff", extra={"status": resp.status_code, "text": resp.text[:500]})
        resp.raise_for_status()

    return resp.text
