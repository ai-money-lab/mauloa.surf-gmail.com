"""CITS Backtest module."""

__all__ = ["BacktestEngine", "BacktestResult"]


def __getattr__(name: str):
    """Lazy import to avoid errors when engine.py is not yet written."""
    if name in __all__:
        from cits.backtest.engine import BacktestEngine, BacktestResult  # noqa: F811

        _map = {"BacktestEngine": BacktestEngine, "BacktestResult": BacktestResult}
        return _map[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
