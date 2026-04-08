"""Tests for cits.scripts.vps_failover -- health check logic (no network)."""

from cits.scripts.vps_failover import check_port, check_vps_health


def test_check_port_closed():
    """Port check on unreachable host should return False."""
    result = check_port("127.0.0.1", 59999, timeout=0.5)
    assert result is False


def test_check_vps_health_returns_dict():
    """Health check should return expected keys even if VPS unreachable."""
    health = check_vps_health()
    assert isinstance(health, dict)
    assert "healthy" in health
    assert "ssh" in health
    assert "vnc" in health
    assert "kabu_api" in health
    assert "details" in health


def test_check_vps_health_offline():
    """VPS should be unhealthy in test environment."""
    health = check_vps_health()
    # In test env, VPS is not reachable
    assert health["healthy"] is False
