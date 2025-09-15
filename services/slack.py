import logging
import time
from typing import Optional

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from config import settings

logger = logging.getLogger(__name__)


class SlackNotifier:
    def __init__(self) -> None:
        if not settings.slack_bot_token:
            logger.warning("SLACK_BOT_TOKEN not configured; Slack notifications disabled.")
        self.client = WebClient(token=settings.slack_bot_token) if settings.slack_bot_token else None
        self.channel_id = settings.slack_channel_id

    def post_pr_summary(
        self,
        title: str,
        author: str,
        summary: str,
        url: str,
        opened_time_str: str,
    ) -> Optional[str]:
        if not self.client or not self.channel_id:
            logger.info("Slack client not initialized; skipping send.")
            return None

        text = (
            "🚀 New Pull Request\n"
            f"Title: {title}\n"
            f"Author: @{author}\n"
            f"Summary: {summary}\n"
            f"Link: {url}\n"
            f"Opened: {opened_time_str}"
        )

        backoff_seconds = 1.0
        for attempt in range(5):
            try:
                result = self.client.chat_postMessage(channel=self.channel_id, text=text)
                ts = result["ts"] if result and "ts" in result else None
                logger.info("Posted Slack message", extra={"ts": ts})
                return ts
            except SlackApiError as e:
                logger.error("Slack post failed: %s", e.response["error"] if e.response else str(e))
            except Exception as e:
                logger.exception("Slack post error: %s", e)

            time.sleep(backoff_seconds)
            backoff_seconds = min(backoff_seconds * 2, 16)
        return None
