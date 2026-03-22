"""Tests for the TradingGraph pipeline orchestrator."""

from unittest.mock import MagicMock, patch

from cits.core.graph.trading_graph import DEFAULT_CONFIG, TradingGraph


def _mock_agent():
    """Return a mock agent with an analyze method returning a dict."""
    agent = MagicMock()
    agent.analyze.return_value = {"summary": "mock analysis", "score": 5}
    return agent


def _patch_all_agents():
    """Patch all agent constructors so TradingGraph.__init__ succeeds without LLM."""
    agents = [
        "cits.core.graph.trading_graph.FundamentalAnalyst",
        "cits.core.graph.trading_graph.SentimentAnalyst",
        "cits.core.graph.trading_graph.NewsAnalyst",
        "cits.core.graph.trading_graph.TechnicalAnalyst",
        "cits.core.graph.trading_graph.BullResearcher",
        "cits.core.graph.trading_graph.BearResearcher",
        "cits.core.graph.trading_graph.Trader",
        "cits.core.graph.trading_graph.RiskManager",
        "cits.core.graph.trading_graph.FundManager",
        "cits.core.graph.trading_graph.DebateEngine",
    ]
    return [patch(name, side_effect=lambda *a, **kw: _mock_agent()) for name in agents]


# ----- Tests -----

def test_default_config_keys():
    """DEFAULT_CONFIG contains all expected keys."""
    expected = {
        "llm_provider", "deep_think_llm", "quick_think_llm",
        "max_debate_rounds", "paper_mode", "log_dir",
        "analyst_temperature", "debate_temperature", "trader_temperature",
    }
    assert expected == set(DEFAULT_CONFIG.keys())


def test_init_default_config():
    """TradingGraph with no config uses defaults."""
    patches = _patch_all_agents()
    for p in patches:
        p.start()
    try:
        graph = TradingGraph()
        assert graph.config["paper_mode"] is False
        assert graph.config["max_debate_rounds"] == 2
    finally:
        for p in patches:
            p.stop()


def test_init_custom_config():
    """TradingGraph merges custom config over defaults."""
    patches = _patch_all_agents()
    for p in patches:
        p.start()
    try:
        graph = TradingGraph(config={"paper_mode": True, "max_debate_rounds": 3})
        assert graph.config["paper_mode"] is True
        assert graph.config["max_debate_rounds"] == 3
        # Unspecified keys keep defaults
        assert graph.config["llm_provider"] == "anthropic"
    finally:
        for p in patches:
            p.stop()


def test_stage_1_calls_all_analysts():
    """_run_stage_1_analysts invokes all four analyst agents."""
    patches = _patch_all_agents()
    for p in patches:
        p.start()
    try:
        graph = TradingGraph()
        ctx = {"ticker": "7203", "date": "2026-03-22"}
        reports = graph._run_stage_1_analysts(ctx)
        assert "fundamental" in reports
        assert "sentiment" in reports
        assert "news" in reports
        assert "technical" in reports
        assert graph.fundamental_analyst.analyze.call_count == 1
    finally:
        for p in patches:
            p.stop()


def test_stage_2_runs_debate():
    """_run_stage_2_research calls bull, bear researchers and debate engine."""
    patches = _patch_all_agents()
    for p in patches:
        p.start()
    try:
        graph = TradingGraph()
        # debate_engine.run_debate must return proper dict
        graph.debate_engine.run_debate = MagicMock(return_value={
            "winner": "bull",
            "final_score": 6,
        })
        ctx = {"ticker": "7203"}
        analyst_reports = {"fundamental": {}, "sentiment": {}, "news": {}, "technical": {}}
        result = graph._run_stage_2_research(ctx, analyst_reports)
        assert result["debate_result"]["winner"] == "bull"
        graph.debate_engine.run_debate.assert_called_once()
    finally:
        for p in patches:
            p.stop()


def test_full_run_returns_all_stages():
    """graph.run() returns a result dict with all five stages and metadata."""
    patches = _patch_all_agents()
    for p in patches:
        p.start()
    try:
        graph = TradingGraph(config={"paper_mode": True})
        # Wire up debate engine
        graph.debate_engine.run_debate = MagicMock(return_value={
            "winner": "bull",
            "final_score": 7,
        })
        # Fund manager needs final_action key
        graph.fund_manager.analyze.return_value = {"final_action": "buy", "approved": True}

        result = graph.run(ticker="7203", date="2026-03-22")

        assert result["ticker"] == "7203"
        assert result["date"] == "2026-03-22"
        assert result["paper_mode"] is True
        assert "timestamp" in result
        assert "stages" in result
        assert set(result["stages"].keys()) == {
            "stage_1_analysts", "stage_2_research",
            "stage_3_trader", "stage_4_risk", "stage_5_fund_manager",
        }
        assert result["final_decision"]["final_action"] == "buy"
    finally:
        for p in patches:
            p.stop()


def test_run_defaults_date_to_today():
    """run() without date argument defaults to today's UTC date."""
    patches = _patch_all_agents()
    for p in patches:
        p.start()
    try:
        graph = TradingGraph()
        graph.debate_engine.run_debate = MagicMock(return_value={
            "winner": "neutral", "final_score": 0,
        })
        graph.fund_manager.analyze.return_value = {"final_action": "hold"}

        result = graph.run(ticker="9984")
        # date should be a valid ISO date string
        assert len(result["date"]) == 10
        assert result["date"].count("-") == 2
    finally:
        for p in patches:
            p.stop()


def test_stage_3_trader_receives_research():
    """_run_stage_3_trader passes research context to the trader agent."""
    patches = _patch_all_agents()
    for p in patches:
        p.start()
    try:
        graph = TradingGraph()
        graph.trader.analyze.return_value = {"action": "buy", "qty": 100}
        ctx = {"ticker": "7203"}
        research = {"debate_result": {"winner": "bull"}}
        decision = graph._run_stage_3_trader(ctx, research)
        assert decision["action"] == "buy"
        # Trader should get merged context
        call_ctx = graph.trader.analyze.call_args[0][0]
        assert "debate_result" in call_ctx
    finally:
        for p in patches:
            p.stop()


def test_stage_5_receives_trade_and_risk():
    """_run_stage_5_fund_manager receives both trade decision and risk assessment."""
    patches = _patch_all_agents()
    for p in patches:
        p.start()
    try:
        graph = TradingGraph()
        graph.fund_manager.analyze.return_value = {"final_action": "reject"}
        ctx = {"ticker": "7203"}
        td = {"action": "buy"}
        ra = {"approved": False, "reason": "too risky"}
        result = graph._run_stage_5_fund_manager(ctx, td, ra)
        call_ctx = graph.fund_manager.analyze.call_args[0][0]
        assert call_ctx["trade_decision"] == td
        assert call_ctx["risk_assessment"] == ra
        assert result["final_action"] == "reject"
    finally:
        for p in patches:
            p.stop()
