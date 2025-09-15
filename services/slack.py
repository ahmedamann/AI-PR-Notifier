import logging
import time
from typing import Optional
import requests
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class SlackNotifier:
    def __init__(self) -> None:
        self.webhook_url = os.getenv("SLACK_WEBHOOK_URL")
        if not self.webhook_url and not os.getenv("SLACK_BOT_TOKEN"):
            logger.warning("No Slack webhook or bot token configured; Slack notifications disabled.")
        self.client = None
        self.channel_id = None
        if os.getenv("SLACK_BOT_TOKEN"):
            try:
                from slack_sdk import WebClient
                self.client = WebClient(token=os.getenv("SLACK_BOT_TOKEN"))
                self.channel_id = os.getenv("SLACK_CHANNEL_ID")
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
