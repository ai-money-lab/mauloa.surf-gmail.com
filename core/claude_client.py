"""Claude APIクライアント"""

import json
import logging
import os
import re
import time
from pathlib import Path

import anthropic
import yaml
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent.parent / "config" / "config.yaml"


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class ClaudeClient:
    """Claude APIとの通信を管理するクライアント"""

    def __init__(self, model: str | None = None):
        self.client = anthropic.Anthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY"),
        )
        config = load_config()
        self.model = model or config["quality_checker"]["default_model"]
        self.max_retries = 3

    def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> str:
        """テキスト生成"""
        for attempt in range(self.max_retries):
            try:
                messages = [{"role": "user", "content": prompt}]
                kwargs = {
                    "model": self.model,
                    "max_tokens": max_tokens,
                    "messages": messages,
                    "temperature": temperature,
                }
                if system_prompt:
                    kwargs["system"] = system_prompt

                response = self.client.messages.create(**kwargs)
                return response.content[0].text

            except anthropic.RateLimitError:
                wait = 2 ** (attempt + 1)
                logger.warning(f"Rate limit hit, waiting {wait}s (attempt {attempt + 1})")
                time.sleep(wait)
            except anthropic.APIError as e:
                logger.error(f"API error: {e}")
                if attempt == self.max_retries - 1:
                    raise
                time.sleep(1)

        raise RuntimeError("Max retries exceeded for Claude API call")

    def generate_json(
        self,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.3,
    ) -> dict:
        """JSON形式で生成（複数JSONブロックや余分なテキストにも対応）"""
        raw = self.generate(prompt, system_prompt, max_tokens, temperature)
        cleaned = raw.strip()

        # ```json ... ``` ブロックを抽出（最初のブロックを使用）
        json_block = re.search(r"```json\s*(.*?)```", cleaned, re.DOTALL)
        if json_block:
            cleaned = json_block.group(1).strip()
        else:
            # ``` ... ``` ブロックを抽出
            code_block = re.search(r"```\s*(.*?)```", cleaned, re.DOTALL)
            if code_block:
                cleaned = code_block.group(1).strip()

        # まずそのままパース
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # { ... } の最外側ブロックを抽出
        brace_match = re.search(r"\{", cleaned)
        if brace_match:
            start = brace_match.start()
            depth = 0
            for i in range(start, len(cleaned)):
                if cleaned[i] == "{":
                    depth += 1
                elif cleaned[i] == "}":
                    depth -= 1
                    if depth == 0:
                        return json.loads(cleaned[start:i + 1])

        raise json.JSONDecodeError("No valid JSON found in response", cleaned, 0)

    def load_prompt(self, prompt_file: str, **kwargs) -> str:
        """promptsディレクトリからプロンプトを読み込み、変数を置換"""
        prompt_path = Path(__file__).parent.parent / "prompts" / prompt_file
        with open(prompt_path, "r", encoding="utf-8") as f:
            template = f.read()
        for key, value in kwargs.items():
            template = template.replace(f"{{{key}}}", str(value))
        return template
