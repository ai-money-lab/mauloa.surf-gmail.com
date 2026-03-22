"""Sentiment analysis agent for CITS trading pipeline."""

import logging

from cits.core.agents.base_agent import BaseAgent


logger = logging.getLogger(__name__)


class SentimentAnalyst(BaseAgent):
    """Analyses market sentiment from news headlines, social media, and forums.

    Produces a sentiment score from -10 (extreme fear / bearish consensus)
    to +10 (extreme greed / bullish consensus) together with reasoning and
    the sources that most influenced the score.
    """

    SYSTEM_PROMPT = (
        "You are a market sentiment analyst in a systematic trading fund.\n"
        "Your role is to gauge the overall mood of market participants by "
        "analysing news headlines, social media posts, financial forums, "
        "and analyst commentary.\n\n"
        "## Reasoning Framework (ReAct)\n"
        "1. **Observation**: List the sentiment signals you observe in the data.\n"
        "2. **Thought**: Weigh the signals by recency, source credibility, "
        "and potential market impact. Consider contrarian signals when "
        "sentiment is extreme.\n"
        "3. **Action**: Produce your final sentiment assessment.\n\n"
        "## Japanese Market Awareness\n"
        "- Monitor Japanese financial media (日経, ロイター日本語版, Bloomberg JP).\n"
        "- Track sentiment on Japanese platforms (Yahoo!ファイナンス掲示板, Twitter/X JP).\n"
        "- Consider cultural factors: Japanese retail investors (個人投資家) tend "
        "to be contrarian buyers on dips.\n"
        "- Note seasonal sentiment patterns around 配当落ち, SQ dates, and "
        "Golden Week / year-end positioning.\n\n"
        "## Output\n"
        "Return ONLY a JSON object with these fields:\n"
        '  "sentiment_score": integer from -10 to 10,\n'
        '  "reasoning": string explaining your analysis step by step,\n'
        '  "sources": list of strings identifying the most influential sources\n'
    )

    def __init__(self, llm_type: str = "quick_think"):
        super().__init__(
            name="sentiment_analyst",
            role="Sentiment Analyst",
            llm_type=llm_type,
        )

    def analyze(self, context: dict) -> dict:
        """Analyse sentiment for a given ticker or market.

        Args:
            context: Must contain ``ticker``. May contain ``news_headlines``,
                     ``social_posts``, ``analyst_ratings``.

        Returns:
            dict with ``sentiment_score``, ``reasoning``, and ``sources``.
        """
        ticker = context.get("ticker", "UNKNOWN")
        self.logger.info("Running sentiment analysis for %s", ticker)

        user_prompt_parts = [
            f"Analyse the current market sentiment for {ticker}.\n"
        ]

        if context.get("news_headlines"):
            user_prompt_parts.append(
                f"Recent news headlines:\n{context['news_headlines']}\n"
            )

        if context.get("social_posts"):
            user_prompt_parts.append(
                f"Social media posts:\n{context['social_posts']}\n"
            )

        if context.get("analyst_ratings"):
            user_prompt_parts.append(
                f"Analyst ratings and commentary:\n{context['analyst_ratings']}\n"
            )

        user_prompt = "\n".join(user_prompt_parts)
        response = self._call_llm(self.SYSTEM_PROMPT, user_prompt)
        result = self._validate_and_parse(
            response,
            required_fields={"sentiment_score": int, "reasoning": str, "sources": list},
            defaults={"sentiment_score": 0, "reasoning": "Analysis unavailable", "sources": []},
        )

        self.logger.info(
            "Sentiment analysis complete for %s: score=%s",
            ticker,
            result.get("sentiment_score"),
        )
        return result
