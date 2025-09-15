
import logging
import time
from typing import Optional
import requests
from config import settings

logger = logging.getLogger(__name__)


class SlackNotifier:
    def __init__(self) -> None:
        self.webhook_url = settings.slack_webhook_url
        if not self.webhook_url and not settings.slack_bot_token:
            logger.warning("No Slack webhook or bot token configured; Slack notifications disabled.")
        self.client = None
        self.channel_id = None
        if settings.slack_bot_token:
            try:
                from slack_sdk import WebClient
                self.client = WebClient(token=settings.slack_bot_token)
                self.channel_id = settings.slack_channel_id
            except ImportError:
                logger.warning("slack_sdk not installed; cannot use bot token.")

    def post_pr_summary(
        self,
        title: str,
        author: str,
        summary: str,
        url: str,
        opened_time_str: str,
    ) -> Optional[str]:
        text = (
            "🚀 New Pull Request\n"
            f"Title: {title}\n"
            f"Author: @{author}\n"
            f"Summary: {summary}\n"
            f"Link: {url}\n"
            f"Opened: {opened_time_str}"
        )

        # Prefer webhook if available
        if self.webhook_url:
            payload = {"text": text}
            backoff_seconds = 1.0
            for attempt in range(5):
                try:
                    resp = requests.post(self.webhook_url, json=payload, timeout=5)
                    if resp.status_code == 200:
                        logger.info("Posted Slack message via webhook")
                        return "webhook"
                    else:
                        logger.error(f"Slack webhook failed: {resp.status_code} {resp.text}")
                except Exception as e:
                    logger.exception("Slack webhook post error: %s", e)
                time.sleep(backoff_seconds)
                backoff_seconds = min(backoff_seconds * 2, 16)
            return None

        # Fallback to Slack SDK if available
        if self.client and self.channel_id:
            backoff_seconds = 1.0
            for attempt in range(5):
                try:
                    result = self.client.chat_postMessage(channel=self.channel_id, text=text)
                    ts = result["ts"] if result and "ts" in result else None
                    logger.info("Posted Slack message", extra={"ts": ts})
                    return ts
                except Exception as e:
                    logger.exception("Slack post error: %s", e)
                time.sleep(backoff_seconds)
                backoff_seconds = min(backoff_seconds * 2, 16)
            return None

        logger.info("No Slack method configured; skipping send.")
        return None
