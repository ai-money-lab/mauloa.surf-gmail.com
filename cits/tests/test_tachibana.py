"""Tests for the Tachibana Securities API client."""

from unittest.mock import MagicMock

import pytest

from cits.japan.broker.tachibana_api import TachibanaAPI


def _mock_response(json_data, status_code=200):
    """Create a mock requests.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status.return_value = None
    return resp


# ===== Initialisation =====


def test_init_from_args():
    """TachibanaAPI uses constructor arguments for credentials."""
    api = TachibanaAPI(user_id="myuser", password="mypass")
    assert api.user_id == "myuser"
    assert api.password == "mypass"


def test_init_from_env(monkeypatch):
    """TachibanaAPI falls back to environment variables."""
    monkeypatch.setenv("TACHIBANA_USER_ID", "envuser")
    monkeypatch.setenv("TACHIBANA_PASSWORD", "envpass")
    api = TachibanaAPI()
    assert api.user_id == "envuser"
    assert api.password == "envpass"


# ===== Login =====


def test_login_success():
    """login() stores the session token on success."""
    api = TachibanaAPI(user_id="user1", password="pass1")
    api._session = MagicMock()
    api._session.post.return_value = _mock_response({
        "p_sd_date": "20260323_session_abc",
        "sResultCode": "0",
    })

    result = api.login()

    assert result is True
    assert api._session_token == "20260323_session_abc"
    api._session.post.assert_called_once()
    call_kwargs = api._session.post.call_args
    assert "/auth/" in call_kwargs.args[0]


def test_login_missing_token():
    """login() raises RuntimeError when p_sd_date is missing."""
    api = TachibanaAPI(user_id="user1", password="pass1")
    api._session = MagicMock()
    api._session.post.return_value = _mock_response({
        "sResultCode": "1",
        "sResultText": "Authentication failed",
    })

    with pytest.raises(RuntimeError, match="missing p_sd_date"):
        api.login()


def test_login_request_failure():
    """login() raises RuntimeError on network error."""
    import requests

    api = TachibanaAPI(user_id="user1", password="pass1")
    api._session = MagicMock()
    api._session.post.side_effect = requests.ConnectionError("refused")

    with pytest.raises(RuntimeError, match="Tachibana login failed"):
        api.login()


# ===== Place Order =====


def test_place_order_market():
    """place_order sends a market buy order."""
    api = TachibanaAPI(user_id="user1", password="pass1")
    api._session_token = "session123"
    api._session = MagicMock()
    api._session.post.return_value = _mock_response({
        "sOrderNumber": "ORD-001",
        "sResultCode": "0",
    })

    result = api.place_order(symbol="7203", side="buy", qty=100)

    assert result["order_id"] == "ORD-001"
    assert result["status"] == "0"

    # Verify the payload
    call_kwargs = api._session.post.call_args
    payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
    assert payload["sIssueCode"] == "7203"
    assert payload["sBaibaiKubun"] == "3"  # buy
    assert payload["sOrderPrice"] == "*"   # market


def test_place_order_limit():
    """place_order sends a limit sell order with price."""
    api = TachibanaAPI(user_id="user1", password="pass1")
    api._session_token = "session123"
    api._session = MagicMock()
    api._session.post.return_value = _mock_response({
        "sOrderNumber": "ORD-002",
        "sResultCode": "0",
    })

    result = api.place_order(
        symbol="9984", side="sell", qty=200,
        order_type="limit", price=5500.0,
    )

    assert result["order_id"] == "ORD-002"

    call_kwargs = api._session.post.call_args
    payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
    assert payload["sBaibaiKubun"] == "1"     # sell
    assert payload["sOrderPrice"] == "5500.0"  # limit price


def test_place_order_invalid_side():
    """place_order raises ValueError on invalid side."""
    api = TachibanaAPI(user_id="user1", password="pass1")
    api._session_token = "session123"

    with pytest.raises(ValueError, match="Invalid side"):
        api.place_order(symbol="7203", side="short", qty=100)


def test_place_order_invalid_order_type():
    """place_order raises ValueError on invalid order_type."""
    api = TachibanaAPI(user_id="user1", password="pass1")
    api._session_token = "session123"

    with pytest.raises(ValueError, match="Invalid order_type"):
        api.place_order(symbol="7203", side="buy", qty=100, order_type="stop")


def test_place_order_limit_no_price():
    """place_order raises ValueError when limit order has no price."""
    api = TachibanaAPI(user_id="user1", password="pass1")
    api._session_token = "session123"

    with pytest.raises(ValueError, match="price is required"):
        api.place_order(symbol="7203", side="buy", qty=100, order_type="limit")


def test_place_order_auto_login():
    """place_order calls login() if no session token."""
    api = TachibanaAPI(user_id="user1", password="pass1")
    api._session = MagicMock()
    # First call is login, second is order
    api._session.post.side_effect = [
        _mock_response({"p_sd_date": "auto_session"}),
        _mock_response({"sOrderNumber": "ORD-003", "sResultCode": "0"}),
    ]

    result = api.place_order(symbol="7203", side="buy", qty=100)

    assert api._session_token == "auto_session"
    assert result["order_id"] == "ORD-003"
    assert api._session.post.call_count == 2


# ===== Cancel Order =====


def test_cancel_order():
    """cancel_order sends a cancel request."""
    api = TachibanaAPI(user_id="user1", password="pass1")
    api._session_token = "session123"
    api._session = MagicMock()
    api._session.post.return_value = _mock_response({
        "sResultCode": "0",
        "sResultText": "OK",
    })

    result = api.cancel_order("ORD-001")

    assert result["order_id"] == "ORD-001"
    assert result["status"] == "0"

    call_kwargs = api._session.post.call_args
    payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
    assert payload["sCLMID"] == "CLMOrderCancelRequest"
    assert payload["sOrderNumber"] == "ORD-001"


def test_cancel_order_network_error():
    """cancel_order returns error dict on failure."""
    import requests

    api = TachibanaAPI(user_id="user1", password="pass1")
    api._session_token = "session123"
    api._session = MagicMock()
    api._session.post.side_effect = requests.ConnectionError("timeout")

    result = api.cancel_order("ORD-999")

    assert "error" in result
    assert result["order_id"] == "ORD-999"


# ===== Get Orders =====


def test_get_orders():
    """get_orders returns list of orders."""
    api = TachibanaAPI(user_id="user1", password="pass1")
    api._session_token = "session123"
    api._session = MagicMock()
    api._session.post.return_value = _mock_response({
        "aOrderList": [
            {"sOrderNumber": "ORD-001", "sIssueCode": "7203"},
            {"sOrderNumber": "ORD-002", "sIssueCode": "9984"},
        ],
    })

    result = api.get_orders()

    assert len(result) == 2
    assert result[0]["sOrderNumber"] == "ORD-001"


def test_get_orders_empty():
    """get_orders returns empty list when no orders."""
    api = TachibanaAPI(user_id="user1", password="pass1")
    api._session_token = "session123"
    api._session = MagicMock()
    api._session.post.return_value = _mock_response({"aOrderList": []})

    result = api.get_orders()

    assert result == []


def test_get_orders_network_error():
    """get_orders returns empty list on failure."""
    import requests

    api = TachibanaAPI(user_id="user1", password="pass1")
    api._session_token = "session123"
    api._session = MagicMock()
    api._session.post.side_effect = requests.ConnectionError("timeout")

    result = api.get_orders()

    assert result == []


# ===== Get Positions =====


def test_get_positions():
    """get_positions returns list of positions."""
    api = TachibanaAPI(user_id="user1", password="pass1")
    api._session_token = "session123"
    api._session = MagicMock()
    api._session.post.return_value = _mock_response({
        "aPositionList": [
            {"sIssueCode": "7203", "sVolume": "100"},
        ],
    })

    result = api.get_positions()

    assert len(result) == 1
    assert result[0]["sIssueCode"] == "7203"


def test_get_positions_empty():
    """get_positions returns empty list when no positions."""
    api = TachibanaAPI(user_id="user1", password="pass1")
    api._session_token = "session123"
    api._session = MagicMock()
    api._session.post.return_value = _mock_response({"aPositionList": []})

    result = api.get_positions()

    assert result == []


def test_get_positions_network_error():
    """get_positions returns empty list on failure."""
    import requests

    api = TachibanaAPI(user_id="user1", password="pass1")
    api._session_token = "session123"
    api._session = MagicMock()
    api._session.post.side_effect = requests.ConnectionError("timeout")

    result = api.get_positions()

    assert result == []
