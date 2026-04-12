"""Tests for broker modules: kabu_api and software_oco."""

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
