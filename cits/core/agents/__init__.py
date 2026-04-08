"""CITS multi-agent trading pipeline.

Exports all agent classes used in the TradingAgents-inspired pipeline:

  Analysts (quick_think):
    FundamentalAnalyst, SentimentAnalyst, NewsAnalyst, TechnicalAnalyst

  Researchers (quick_think):
    BullResearcher, BearResearcher

  Decision Makers (deep_think):
    Trader, RiskManager, FundManager
"""

from cits.core.agents.base_agent import BaseAgent
from cits.core.agents.bear_researcher import BearResearcher
from cits.core.agents.bull_researcher import BullResearcher
from cits.core.agents.fund_manager import FundManager
from cits.core.agents.fundamental import FundamentalAnalyst
from cits.core.agents.news import NewsAnalyst
from cits.core.agents.risk_manager import RiskManager
from cits.core.agents.sentiment import SentimentAnalyst
from cits.core.agents.technical import TechnicalAnalyst
from cits.core.agents.trader import Trader

__all__ = [
    "BaseAgent",
    "BearResearcher",
    "BullResearcher",
    "FundManager",
    "FundamentalAnalyst",
    "NewsAnalyst",
    "RiskManager",
    "SentimentAnalyst",
    "TechnicalAnalyst",
    "Trader",
]
