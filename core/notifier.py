"""Notification module for LINE Notify and Slack."""

import os
import logging

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class Notifier:
    """Send notifications via LINE Notify and Slack webhook."""

    def __init__(self):
        self.line_token = os.getenv("LINE_NOTIFY_TOKEN", "")
        self.slack_webhook = os.getenv("SLACK_WEBHOOK_URL", "")

    def send_line(self, message: str) -> bool:
        """Send a LINE Notify message."""
        if not self.line_token:
            logger.warning("LINE_NOTIFY_TOKEN not set, skipping notification")
            return False
        try:
            resp = requests.post(
                "https://notify-api.line.me/api/notify",
                headers={"Authorization": f"Bearer {self.line_token}"},
                data={"message": f"\n{message}"},
                timeout=10,
            )
            resp.raise_for_status()
            logger.info("LINE notification sent")
            return True
        except Exception as e:
            logger.error("LINE notification failed: %s", e)
            return False

    def send_slack(self, message: str) -> bool:
        """Send a Slack webhook message."""
        if not self.slack_webhook:
            logger.warning("SLACK_WEBHOOK_URL not set, skipping notification")
            return False
        try:
            resp = requests.post(
                self.slack_webhook,
                json={"text": message},
                timeout=10,
            )
            resp.raise_for_status()
            logger.info("Slack notification sent")
            return True
        except Exception as e:
            logger.error("Slack notification failed: %s", e)
            return False

    def notify(self, message: str) -> None:
        """Send notification to all configured channels."""
        self.send_line(message)
        self.send_slack(message)
