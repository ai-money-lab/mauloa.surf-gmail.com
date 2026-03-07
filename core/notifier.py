"""Notification module for LINE Messaging API and Slack.

LINE Notify was shut down on 2025-03-31.
This module uses LINE Messaging API (push message) instead.

Required env vars:
  LINE_CHANNEL_ACCESS_TOKEN  — LINE Messaging API channel access token
  LINE_USER_ID               — Target user ID to receive push messages
"""

import os
import logging

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class Notifier:
    """Send notifications via LINE Messaging API and Slack webhook."""

    def __init__(self):
        self.line_channel_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
        self.line_user_id = os.getenv("LINE_USER_ID", "")
        self.slack_webhook = os.getenv("SLACK_WEBHOOK_URL", "")

    def send_line(self, message: str) -> bool:
        """Send a LINE push message via Messaging API."""
        if not self.line_channel_token or not self.line_user_id:
            logger.warning(
                "LINE_CHANNEL_ACCESS_TOKEN or LINE_USER_ID not set, skipping"
            )
            return False
        try:
            resp = requests.post(
                "https://api.line.me/v2/bot/message/push",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.line_channel_token}",
                },
                json={
                    "to": self.line_user_id,
                    "messages": [{"type": "text", "text": message}],
                },
                timeout=10,
            )
            resp.raise_for_status()
            logger.info("LINE push message sent")
            return True
        except Exception as e:
            logger.error("LINE push message failed: %s", e)
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
