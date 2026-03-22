"""Tests for data source modules: yfinance_jp, jquants_api, edinet_api, jpx modules."""

from unittest.mock import MagicMock, patch

import pandas as pd

from cits.japan.data.yfinance_jp import JapanStockData
from cits.japan.data.jquants_api import JQuantsClient
from cits.japan.data.edinet_api import EdinetClient
from cits.japan.data.jpx_shorts import JPXShortTracker
from cits.japan.data.jpx_flows import JPXFlowTracker


# ===== JapanStockData (yfinance) =====

def test_yf_ensure_tse_suffix():
    """_ensure_tse_suffix appends .T for plain ticker codes."""
    jsd = JapanStockData()
    assert jsd._ensure_tse_suffix("7203") == "7203.T"
    assert jsd._ensure_tse_suffix("^N225") == "^N225"
    assert jsd._ensure_tse_suffix("7203.T") == "7203.T"


@patch("cits.japan.data.yfinance_jp.yf.download")
def test_yf_get_stock_data(mock_dl):
    """get_stock_data calls yfinance with correct symbol."""
    mock_dl.return_value = pd.DataFrame({"Close": [100, 101]})
    jsd = JapanStockData()
    result = jsd.get_stock_data("7203", period="1mo")
    mock_dl.assert_called_once_with("7203.T", period="1mo", progress=False)
    assert not result.empty


@patch("cits.japan.data.yfinance_jp.yf.download")
def test_yf_get_stock_data_empty(mock_dl):
    """get_stock_data returns empty DataFrame on no data."""
    mock_dl.return_value = pd.DataFrame()
    jsd = JapanStockData()
    result = jsd.get_stock_data("9999")
    assert result.empty


@patch("cits.japan.data.yfinance_jp.yf.download")
def test_yf_get_nikkei225(mock_dl):
    """get_nikkei225 fetches ^N225."""
    mock_dl.return_value = pd.DataFrame({"Close": [38000]})
    jsd = JapanStockData()
    result = jsd.get_nikkei225()
    mock_dl.assert_called_once_with("^N225", period="3mo", progress=False)
    assert not result.empty


@patch("cits.japan.data.yfinance_jp.yf.Ticker")
def test_yf_get_financial_info(mock_ticker_cls):
    """get_financial_info returns company info dict."""
    mock_ticker = MagicMock()
    mock_ticker.info = {
        "shortName": "Toyota",
        "trailingPE": 12.5,
        "marketCap": 30_000_000_000_000,
    }
    mock_ticker_cls.return_value = mock_ticker
    jsd = JapanStockData()
    info = jsd.get_financial_info("7203")
    assert info["shortName"] == "Toyota"
    assert info["trailingPE"] == 12.5


@patch("cits.japan.data.yfinance_jp.yf.Ticker")
def test_yf_get_financial_info_error(mock_ticker_cls):
    """get_financial_info returns empty dict on exception."""
    mock_ticker_cls.side_effect = Exception("Network error")
    jsd = JapanStockData()
    assert jsd.get_financial_info("7203") == {}


# ===== JQuantsClient =====

def test_jquants_init():
    """JQuantsClient picks up API key from environment."""
    client = JQuantsClient()
    assert client._api_key == "test-jquants-key"


@patch("cits.japan.data.jquants_api.requests.Session")
def test_jquants_get_listed_stocks(mock_sess_cls):
    """get_listed_stocks returns a DataFrame from API response."""
    mock_sess = MagicMock()
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "info": [{"Code": "7203", "CompanyName": "Toyota"}]
    }
    mock_resp.raise_for_status.return_value = None
    mock_sess.get.return_value = mock_resp
    mock_sess.post.return_value = MagicMock(
        json=MagicMock(return_value={"refreshToken": "rt"}),
        raise_for_status=MagicMock(),
    )
    mock_sess_cls.return_value = mock_sess

    client = JQuantsClient()
    client._session = mock_sess
    # Simulate token refresh
    client._id_token = "test-token"
    client._token_expiry = 99999999999.0

    result = client.get_listed_stocks()
    assert not result.empty
    assert "Code" in result.columns


def test_jquants_get_listed_stocks_no_data():
    """get_listed_stocks returns empty DataFrame when API returns None."""
    client = JQuantsClient()
    client._get = MagicMock(return_value=None)
    result = client.get_listed_stocks()
    assert result.empty


def test_jquants_get_financial_statements():
    """get_financial_statements returns dict from API."""
    client = JQuantsClient()
    client._get = MagicMock(return_value={"statements": [{"revenue": 1000}]})
    result = client.get_financial_statements("7203")
    assert "statements" in result


# ===== EdinetClient =====

def test_edinet_init():
    """EdinetClient picks up API key from environment."""
    client = EdinetClient()
    assert client._api_key == "test-edinet-key"


def test_edinet_get_large_holdings():
    """get_large_holdings returns a list of filings."""
    client = EdinetClient()
    client._get = MagicMock(return_value={
        "results": [{"holder": "BlackRock", "shares": 5000000}]
    })
    result = client.get_large_holdings("7203")
    assert len(result) == 1
    assert result[0]["holder"] == "BlackRock"


def test_edinet_get_large_holdings_empty():
    """get_large_holdings returns empty list when API returns None."""
    client = EdinetClient()
    client._get = MagicMock(return_value=None)
    assert client.get_large_holdings("7203") == []


def test_edinet_search_filings():
    """search_filings returns matching filings."""
    client = EdinetClient()
    client._get = MagicMock(return_value={
        "results": [{"docId": "DOC001", "filerName": "Toyota"}]
    })
    result = client.search_filings("Toyota", filing_type="120")
    assert len(result) == 1


def test_edinet_get_filing_document():
    """get_filing_document returns a document dict."""
    client = EdinetClient()
    client._get = MagicMock(return_value={"docId": "DOC001", "status": "ok"})
    result = client.get_filing_document("DOC001")
    assert result["docId"] == "DOC001"


# ===== JPXShortTracker =====

def test_jpx_short_ratio_cached():
    """get_short_selling_ratio uses cache within TTL."""
    tracker = JPXShortTracker()
    tracker._ratio_cache = {"total_short_ratio": 42.0}
    from datetime import datetime
    tracker._ratio_cache_time = datetime.now()

    result = tracker.get_short_selling_ratio()
    assert result["total_short_ratio"] == 42.0


def test_jpx_parse_short_ratio():
    """_parse_short_ratio returns expected keys."""
    result = JPXShortTracker._parse_short_ratio("<html>some html</html>")
    assert "total_short_ratio" in result
    assert "margin_short_ratio" in result


@patch.object(JPXShortTracker, "_fetch_page", return_value="<html></html>")
def test_jpx_short_positions(mock_fetch):
    """get_short_positions fetches and parses page."""
    tracker = JPXShortTracker()
    result = tracker.get_short_positions(ticker="7203")
    assert isinstance(result, list)


# ===== JPXFlowTracker =====

@patch.object(JPXFlowTracker, "_fetch_flow_data")
def test_jpx_flow_investor_flows(mock_fetch):
    """get_investor_flows returns parsed flow data."""
    mock_fetch.return_value = {
        "foreign_investors": {"buy": 100, "sell": 80, "net": 20},
        "individuals": {"buy": 50, "sell": 60, "net": -10},
    }
    tracker = JPXFlowTracker()
    flows = tracker.get_investor_flows()
    assert flows["foreign_investors"]["net"] == 20


@patch.object(JPXFlowTracker, "get_investor_flows")
def test_jpx_flow_trend_buying(mock_flows):
    """analyze_flow_trend detects foreign buying trend."""
    mock_flows.return_value = {
        "foreign_investors": {"buy": 100, "sell": 80, "net": 20},
        "individuals": {"buy": 50, "sell": 60, "net": -10},
    }
    tracker = JPXFlowTracker()
    analysis = tracker.analyze_flow_trend()
    assert analysis["foreign_trend"] == "buying"
    assert analysis["dominant_buyer"] == "foreign_investors"
