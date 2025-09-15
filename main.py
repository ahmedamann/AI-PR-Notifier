import hashlib
import hmac
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from services.github import fetch_pr_diff
from services.llm import LlmClient
from services.slack import SlackNotifier

# Load environment variables
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="PR Review Notifier", version="1.0.0")

llm_client = LlmClient()
slack = SlackNotifier()

# Simple in-memory cooldown per PR id
_last_post_time: Dict[str, float] = {}


def verify_signature(secret: str, signature_header: Optional[str], body: bytes) -> bool:
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    sig = signature_header.split("=", 1)[1]
    mac = hmac.new(secret.encode("utf-8"), msg=body, digestmod=hashlib.sha256)
    digest = mac.hexdigest()
    return hmac.compare_digest(digest, sig)


@app.get("/")
async def root():
    return {"message": "Welcome to AI-PR-Notifier!"}


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/")
async def root_post(
    request: Request,
    x_github_event: str | None = Header(default=None, alias="X-GitHub-Event"),
    x_hub_signature_256: str | None = Header(default=None, alias="X-Hub-Signature-256"),
) -> JSONResponse:
    # Reuse the same webhook logic
    return await handle_webhook(request, x_github_event, x_hub_signature_256)


# Centralized logic for POST webhook handling
async def handle_webhook(
    request: Request,
    x_github_event: str | None,
    x_hub_signature_256: str | None,
) -> JSONResponse:
    body = await request.body()

    if not os.getenv("GITHUB_WEBHOOK_SECRET"):
        logger.warning("No webhook secret configured; rejecting for safety.")
        raise HTTPException(status_code=401, detail="Webhook secret not configured")

    if not verify_signature(os.getenv("GITHUB_WEBHOOK_SECRET"), x_hub_signature_256, body):
        raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        payload = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # Only react to opened pull requests
    if x_github_event != "pull_request":
        return JSONResponse(content={"ignored": True, "reason": "event_not_pull_request"}, status_code=202)

    if payload.get("action") != "opened":
        return JSONResponse(content={"ignored": True, "reason": "action_not_opened"}, status_code=202)

    # Extract PR/repo metadata
    pr = payload.get("pull_request", {})
    repo = payload.get("repository", {})
    repo_full_name = repo.get("full_name")
    pr_number = pr.get("number")
    title = pr.get("title", "")
    url = pr.get("html_url", "")
    created_at = pr.get("created_at", "")
    author = pr.get("user", {}).get("login", "")

    if not repo_full_name or not pr_number:
        raise HTTPException(status_code=400, detail="Missing repository or PR number")

    # Cooldown logic
    key = f"{repo_full_name}#{pr_number}"
    now = time.time()
    last = _last_post_time.get(key, 0)
    if now - last < int(os.getenv("COOLDOWN_SECONDS", 60)):
        return JSONResponse(content={"ignored": True, "reason": "cooldown"}, status_code=202)

    # Fetch PR diff
    try:
        diff_text = fetch_pr_diff(repo_full_name, int(pr_number))
    except Exception as e:
        logger.exception("Failed to fetch PR diff: %s", e)
        raise HTTPException(status_code=502, detail="Failed to fetch PR diff")

    # Summarize with LLM
    try:
        summary = llm_client.summarize(diff_text)
    except Exception as e:
        logger.exception("LLM summarization error: %s", e)
        summary = "(Failed to generate summary)"

    # Format opened time
    opened_dt_str = created_at
    try:
        if created_at:
            dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            opened_dt_str = dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        pass

    # Send Slack notification
    try:
        ts = slack.post_pr_summary(
            title=title,
            author=author,
            summary=summary,
            url=url,
            opened_time_str=opened_dt_str,
        )
        if ts is not None:
            _last_post_time[key] = now
    except Exception as e:
        logger.exception("Slack notification failed: %s", e)
        raise HTTPException(status_code=502, detail="Slack notification failed")

    return JSONResponse(content={"ok": True})
