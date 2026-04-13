"""Tests for broker modules: kabu_api and software_oco."""

import requests
from unittest.mock import MagicMock

import pytest

from cits.japan.broker.kabu_api import KabuStationAPI
from cits.japan.broker.software_oco import SoftwareOCO


# ===== KabuStationAPI =====

def _mock_response(json_data, status_code=200):
    """Create a mock requests.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status.return_value = None
    return resp


def test_kabu_init_password_from_arg():
    """KabuStationAPI uses password argument over env var."""
    api = KabuStationAPI(password="direct-pw")
    assert api.password == "direct-pw"


def test_kabu_init_password_from_env():
    """KabuStationAPI falls back to KABU_API_PASSWORD env var."""
    api = KabuStationAPI()
    assert api.password == "test-kabu-pw"  # set by conftest


def test_kabu_init_order_password_from_env():
    """KabuStationAPI reads order password from KABU_ORDER_PASSWORD env var."""
    api = KabuStationAPI()
    assert api.order_password == "test-kabu-order-pw"  # set by conftest


def test_kabu_init_order_password_from_arg():
    """KabuStationAPI uses order_password arg over env var."""
    api = KabuStationAPI(order_password="explicit-order-pw")
    assert api.order_password == "explicit-order-pw"


def test_kabu_place_order_uses_order_password():
    """place_order payload uses order_password (取引パスワード), not API password."""
    api = KabuStationAPI(password="api-pw", order_password="order-pw")
    api._token = "tok"
    api._session = MagicMock()
    api._session.headers = {"X-API-KEY": "tok"}
    api._session.post.return_value = _mock_response({"OrderId": "ORD-002"})

    api.place_order(symbol="7203", side="buy", qty=100, order_type="market")

    call_kwargs = api._session.post.call_args
    sent_payload = call_kwargs[1]["json"]  # kwargs json=
    assert sent_payload["Password"] == "order-pw"


def test_kabu_cancel_order_uses_order_password():
    """cancel_order payload uses order_password (取引パスワード), not API password."""
    api = KabuStationAPI(password="api-pw", order_password="order-pw")
    api._token = "tok"
    api._session = MagicMock()
    api._session.headers = {"X-API-KEY": "tok"}
    api._session.put.return_value = _mock_response({"OrderId": "ORD-001", "Result": 0})

    api.cancel_order("ORD-001")

    call_kwargs = api._session.put.call_args
    sent_payload = call_kwargs[1]["json"]
    assert sent_payload["Password"] == "order-pw"


def test_kabu_get_token():
    """_get_token sends POST and stores the token."""
    api = KabuStationAPI(password="pw")
    api._session = MagicMock()
    api._session.post.return_value = _mock_response({"Token": "abc123"})
    api._session.headers = {}

    token = api._get_token()

    assert token == "abc123"
    assert api._token == "abc123"


def test_kabu_get_token_failure():
    """_get_token raises RuntimeError on missing Token field."""
    api = KabuStationAPI(password="pw")
    api._session = MagicMock()
    api._session.post.return_value = _mock_response({"Result": 0})
    api._session.headers = {}

    with pytest.raises(RuntimeError, match="Token response missing"):
        api._get_token()


def test_kabu_get_board():
    """get_board returns board data after ensuring token."""
    api = KabuStationAPI(password="pw")
    api._token = "existing-token"
    api._session = MagicMock()
    api._session.headers = {"X-API-KEY": "existing-token"}
    api._session.get.return_value = _mock_response({"CurrentPrice": 2500, "Symbol": "7203"})

    result = api.get_board("7203", exchange=1)

    assert result["CurrentPrice"] == 2500
    api._session.get.assert_called_once()


def test_kabu_place_order_market():
    """place_order sends a market order."""
    api = KabuStationAPI(password="pw")
    api._token = "tok"
    api._session = MagicMock()
    api._session.headers = {"X-API-KEY": "tok"}
    api._session.post.return_value = _mock_response({"OrderId": "ORD-001"})

    result = api.place_order(symbol="7203", side="buy", qty=100, order_type="market")

    assert result["OrderId"] == "ORD-001"


def test_kabu_place_order_invalid_side():
    """place_order raises ValueError on invalid side."""
    api = KabuStationAPI(password="pw")
    api._token = "tok"

    with pytest.raises(ValueError, match="Invalid side"):
        api.place_order(symbol="7203", side="short", qty=100)


def test_kabu_place_order_limit_no_price():
    """place_order raises ValueError when limit order has no price."""
    api = KabuStationAPI(password="pw")
    api._token = "tok"

    with pytest.raises(ValueError, match="price is required"):
        api.place_order(symbol="7203", side="buy", qty=100, order_type="limit")


def test_kabu_cancel_order():
    """cancel_order sends PUT to the correct endpoint."""
    api = KabuStationAPI(password="pw")
    api._token = "tok"
    api._session = MagicMock()
    api._session.headers = {"X-API-KEY": "tok"}
    api._session.put.return_value = _mock_response({"OrderId": "ORD-001", "Result": 0})

    result = api.cancel_order("ORD-001")

    assert result["OrderId"] == "ORD-001"
    api._session.put.assert_called_once()


def test_kabu_get_positions_empty():
    """get_positions returns an empty list on error."""
    api = KabuStationAPI(password="pw")
    api._token = "tok"
    api._session = MagicMock()
    api._session.headers = {"X-API-KEY": "tok"}
    api._session.get.return_value = _mock_response([])

    result = api.get_positions()

    assert result == []


def test_kabu_place_stop_loss_order():
    """place_stop_loss_order sends a sell 逆指値 (FrontOrderType=30) order."""
    api = KabuStationAPI(password="pw", order_password="order-pw")
    api._token = "tok"
    api._session = MagicMock()
    api._session.headers = {"X-API-KEY": "tok"}
    api._session.post.return_value = _mock_response({"OrderId": "SL-001"})

    result = api.place_stop_loss_order(symbol="2170", qty=100, stop_price=611.0, exchange=9)

    assert result["OrderId"] == "SL-001"
    call_payload = api._session.post.call_args[1]["json"]
    assert call_payload["Side"] == 1           # 売り
    assert call_payload["FrontOrderType"] == 30  # 逆指値
    assert call_payload["Price"] == 611.0
    assert call_payload["Password"] == "order-pw"
    assert call_payload["Symbol"] == "2170"
    assert call_payload["Qty"] == 100


# ===== SoftwareOCO =====

def test_oco_create():
    """create_oco creates an OCO and starts monitoring."""
    broker = MagicMock(spec=KabuStationAPI)
    broker.place_order.return_value = {"OrderId": "SL-001"}
    # Make get_board return no price so the monitor thread exits quickly
    broker.get_board.return_value = {"CurrentPrice": None}

    oco = SoftwareOCO(broker=broker, check_interval=0.01)
    oco_id = oco.create_oco(
        symbol="7203", side="buy", qty=100,
        take_profit=2600, stop_loss=2400,
    )

    assert oco_id is not None
    assert len(oco.get_active_ocos()) == 1
    # Cleanup
    oco.cancel_oco(oco_id)


def test_oco_cancel():
    """cancel_oco stops monitoring and cancels the SL order."""
    broker = MagicMock(spec=KabuStationAPI)
    broker.place_order.return_value = {"OrderId": "SL-002"}
    broker.get_board.return_value = {"CurrentPrice": None}

    oco = SoftwareOCO(broker=broker, check_interval=0.01)
    oco_id = oco.create_oco(
        symbol="7203", side="buy", qty=100,
        take_profit=2600, stop_loss=2400,
    )

    result = oco.cancel_oco(oco_id)

    assert result is True
    broker.cancel_order.assert_called_with("SL-002")
    assert oco.get_active_ocos() == []


def test_oco_cancel_nonexistent():
    """cancel_oco returns False for unknown oco_id."""
    broker = MagicMock(spec=KabuStationAPI)
    oco = SoftwareOCO(broker=broker)
    assert oco.cancel_oco("nonexistent") is False


def test_oco_tp_triggers_for_long():
    """OCO monitoring fires TP market order when price >= take_profit for longs."""
    broker = MagicMock(spec=KabuStationAPI)
    broker.place_order.return_value = {"OrderId": "SL-003"}

    # First call returns price at TP
    broker.get_board.return_value = {"CurrentPrice": 2600}

    oco = SoftwareOCO(broker=broker, check_interval=0.01)
    oco.create_oco(
        symbol="7203", side="buy", qty=100,
        take_profit=2600, stop_loss=2400,
    )

    # Wait for the thread to process
    import time
    time.sleep(0.2)

    # The TP should have fired: a market sell order + SL cancel
    sell_calls = [
        c for c in broker.place_order.call_args_list
        if c.kwargs.get("side") == "sell" and c.kwargs.get("order_type") == "market"
    ]
    assert len(sell_calls) >= 1


def test_oco_sl_detected_as_filled():
    """OCO marks status filled_sl when broker reports SL order State=5."""
    broker = MagicMock(spec=KabuStationAPI)
    broker.place_order.return_value = {"OrderId": "SL-FILL"}
    # Price stays between TP and SL — no TP hit
    broker.get_board.return_value = {"CurrentPrice": 2500}
    # get_orders reports the SL order as filled (State=5 = 完了)
    broker.get_orders.return_value = [{"OrderId": "SL-FILL", "State": 5}]

    oco = SoftwareOCO(broker=broker, check_interval=0.01)
    oco_id = oco.create_oco(
        symbol="7203", side="buy", qty=100,
        take_profit=2600, stop_loss=2400,
    )

    import time
    time.sleep(0.2)

    # OCO should no longer be active
    active = oco.get_active_ocos()
    assert not any(o["oco_id"] == oco_id for o in active)


# ===== Login / Token edge cases =====

def test_kabu_login_wrong_password():
    """_get_token raises HTTPError on 401 (wrong API password)."""
    api = KabuStationAPI(password="wrong-pw")
    api._session = MagicMock()
    api._session.headers = {}
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = requests.HTTPError("401 Unauthorized")
    api._session.post.return_value = mock_resp

    with pytest.raises(requests.HTTPError):
        api._get_token()


def test_kabu_login_connection_refused():
    """_get_token raises ConnectionError when kabuStation is not running."""
    api = KabuStationAPI(password="pw")
    api._session = MagicMock()
    api._session.headers = {}
    api._session.post.side_effect = requests.ConnectionError("Connection refused")

    with pytest.raises(requests.ConnectionError):
        api._get_token()


def test_kabu_get_token_sets_header():
    """_get_token stores token and updates X-API-KEY header."""
    api = KabuStationAPI(password="pw")
    api._session = MagicMock()
    api._session.post.return_value = _mock_response({"Token": "hdr-token"})
    api._session.headers = {}

    api._get_token()

    assert api._token == "hdr-token"
    assert api._session.headers["X-API-KEY"] == "hdr-token"


def test_kabu_ensure_token_calls_get_token_once():
    """_ensure_token is idempotent — only fetches token on first call."""
    api = KabuStationAPI(password="pw")
    api._session = MagicMock()
    api._session.post.return_value = _mock_response({"Token": "once"})
    api._session.headers = {}

    api._ensure_token()
    api._ensure_token()  # second call should be no-op

    assert api._session.post.call_count == 1


# ===== Input validation (qty / price) =====

def test_kabu_place_order_qty_zero():
    """place_order raises ValueError when qty is 0."""
    api = KabuStationAPI(password="pw")
    api._token = "tok"

    with pytest.raises(ValueError, match="qty must be > 0"):
        api.place_order(symbol="7203", side="buy", qty=0)


def test_kabu_place_order_negative_qty():
    """place_order raises ValueError when qty is negative."""
    api = KabuStationAPI(password="pw")
    api._token = "tok"

    with pytest.raises(ValueError, match="qty must be > 0"):
        api.place_order(symbol="7203", side="buy", qty=-1)


def test_kabu_place_limit_order_zero_price():
    """place_order raises ValueError when limit price is 0."""
    api = KabuStationAPI(password="pw")
    api._token = "tok"

    with pytest.raises(ValueError, match="price must be > 0"):
        api.place_order(symbol="7203", side="buy", qty=100, order_type="limit", price=0)


def test_kabu_place_limit_order_negative_price():
    """place_order raises ValueError when limit price is negative."""
    api = KabuStationAPI(password="pw")
    api._token = "tok"

    with pytest.raises(ValueError, match="price must be > 0"):
        api.place_order(symbol="7203", side="buy", qty=100, order_type="limit", price=-100)


# ===== Network failure resilience =====

def test_kabu_get_board_network_error():
    """get_board returns error dict (not exception) on network failure."""
    api = KabuStationAPI(password="pw")
    api._token = "tok"
    api._session = MagicMock()
    api._session.headers = {"X-API-KEY": "tok"}
    api._session.get.side_effect = requests.ConnectionError("unreachable")

    result = api.get_board("7203", exchange=1)

    assert "error" in result
    assert result["symbol"] == "7203"


def test_kabu_get_positions_network_error():
    """get_positions returns [] (not exception) on network failure."""
    api = KabuStationAPI(password="pw")
    api._token = "tok"
    api._session = MagicMock()
    api._session.headers = {"X-API-KEY": "tok"}
    api._session.get.side_effect = requests.ConnectionError("unreachable")

    result = api.get_positions()

    assert result == []


def test_kabu_place_order_network_error():
    """place_order returns error dict (not exception) on network failure."""
    api = KabuStationAPI(password="pw")
    api._token = "tok"
    api._session = MagicMock()
    api._session.headers = {"X-API-KEY": "tok"}
    api._session.post.side_effect = requests.ConnectionError("unreachable")

    result = api.place_order(symbol="7203", side="buy", qty=100)

    assert "error" in result
    assert result["symbol"] == "7203"
    assert result["side"] == "buy"


def test_kabu_cancel_order_network_error():
    """cancel_order returns error dict (not exception) on network failure."""
    api = KabuStationAPI(password="pw")
    api._token = "tok"
    api._session = MagicMock()
    api._session.headers = {"X-API-KEY": "tok"}
    api._session.put.side_effect = requests.ConnectionError("unreachable")

    result = api.cancel_order("ORD-999")

    assert "error" in result
    assert result["order_id"] == "ORD-999"
