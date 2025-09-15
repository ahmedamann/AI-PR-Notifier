import os
from dotenv import load_dotenv
import logging
from typing import Tuple
import requests

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


def parse_repo_full_name(repo_full_name: str) -> Tuple[str, str]:
    if "/" not in repo_full_name:
        raise ValueError(f"Invalid repo full name: {repo_full_name}")
    owner, repo = repo_full_name.split("/", 1)
    return owner, repo


def fetch_pr_diff(repo_full_name: str, pr_number: int) -> str:
    """Fetch the diff of a pull request from GitHub."""
    url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}"
    headers = {
        "Accept": "application/vnd.github.v3.diff",
    }
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.text
