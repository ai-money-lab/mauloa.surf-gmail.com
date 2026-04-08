"""Tests for cits.scripts.daily_report -- report generation (no email send)."""

from cits.scripts.daily_report import generate_report


def test_generate_report_returns_string():
    report = generate_report()
    assert isinstance(report, str)
    assert len(report) > 0


def test_report_contains_header():
    report = generate_report()
    assert "CITS Daily Trade Report" in report


def test_report_contains_sections():
    report = generate_report()
    assert "Open Positions" in report
    assert "End of Report" in report
