"""News analysis agent for CITS trading pipeline."""

import logging

from cits.core.agents.base_agent import BaseAgent


logger = logging.getLogger(__name__)


class NewsAnalyst(BaseAgent):
    """Analyses latest news events and macro-economic trends.

    Integrates with the voice tracker subsystem to incorporate statements
    from central banks (FOMC, BOJ) and key political figures affecting
    markets.  Produces a news score from -10 to +10 along with key events
    and a macro outlook summary.
    """

    SYSTEM_PROMPT = (
        "You are a macro-aware news analyst in a systematic trading fund.\n"
        "Your role is to evaluate the impact of breaking news, economic data "
        "releases, and central bank communications on specific securities "
        "and the broader market.\n\n"
        "## Reasoning Framework (ReAct)\n"
        "1. **Observation**: Identify the most market-moving news events.\n"
        "2. **Thought**: Assess each event's likely impact on asset prices, "
        "considering first-order effects and second-order ripple effects. "
        "Separate signal from noise.\n"
        "3. **Action**: Produce your final news assessment.\n\n"
        "## Voice Tracker Integration\n"
        "Pay special attention to statements from:\n"
        "- **FOMC / Federal Reserve**: Rate decisions, dot plots, Powell press "
        "conferences, governor speeches.\n"
        "- **BOJ / Bank of Japan**: YCC adjustments, Ueda press conferences, "
        "政策決定会合 minutes, 主な意見.\n"
        "- **Political figures**: Presidential statements on tariffs, trade "
        "policy, fiscal spending that move markets.\n"
        "- **MOF / 財務省**: FX intervention signals (口先介入), Kanda/Mimura "
        "comments on yen levels.\n\n"
        "## Japanese Market Awareness\n"
        "- Track 日銀短観 (Tankan), GDP, CPI, 機械受注, and other key JP data.\n"
        "- Note BOJ meeting schedule and 黒田/植田 communication patterns.\n"
        "- Consider US-Japan rate differential impact on USD/JPY and Nikkei.\n"
        "- Watch for 為替介入 signals and their equity market ripple effects.\n\n"
        "## Output\n"
        "Return ONLY a JSON object with these fields:\n"
        '  "news_score": integer from -10 to 10,\n'
        '  "key_events": list of objects with "event", "impact", "relevance",\n'
        '  "macro_outlook": string summarising the macro environment\n'
    )

    def __init__(self, llm_type: str = "quick_think"):
        super().__init__(
            name="news_analyst",
            role="News Analyst",
            llm_type=llm_type,
        )

    def analyze(self, context: dict) -> dict:
        """Analyse news and macro trends for a given ticker.

        Args:
            context: Must contain ``ticker``. May contain ``news_items``,
                     ``macro_data``, ``voice_tracker_events``,
                     ``economic_calendar``.

        Returns:
            dict with ``news_score``, ``key_events``, and ``macro_outlook``.
        """
        ticker = context.get("ticker", "UNKNOWN")
        self.logger.info("Running news analysis for %s", ticker)

        user_prompt_parts = [
            f"Analyse the latest news and macro environment for {ticker}.\n"
        ]

        if context.get("news_items"):
            user_prompt_parts.append(
                f"Recent news items:\n{context['news_items']}\n"
            )

        if context.get("macro_data"):
            user_prompt_parts.append(
                f"Macro-economic data:\n{context['macro_data']}\n"
            )

        if context.get("voice_tracker_events"):
            user_prompt_parts.append(
                "Voice tracker events (central bank & political statements):\n"
                f"{context['voice_tracker_events']}\n"
            )

        if context.get("economic_calendar"):
            user_prompt_parts.append(
                f"Upcoming economic calendar:\n{context['economic_calendar']}\n"
            )

        user_prompt = "\n".join(user_prompt_parts)
        response = self._call_llm(self.SYSTEM_PROMPT, user_prompt)
        result = self._parse_json_response(response)

        self.logger.info(
            "News analysis complete for %s: score=%s",
            ticker,
            result.get("news_score"),
        )
        return result
