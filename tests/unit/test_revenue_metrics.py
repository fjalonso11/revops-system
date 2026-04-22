from src.revenue.velocity import _days_between, _avg


def test_days_between_positive():
    assert _days_between("2024-01-01T00:00:00+00:00", "2024-01-11T00:00:00+00:00") == 10.0


def test_days_between_negative_returns_none():
    assert _days_between("2024-01-11T00:00:00+00:00", "2024-01-01T00:00:00+00:00") is None


def test_days_between_missing_returns_none():
    assert _days_between(None, "2024-01-01T00:00:00+00:00") is None
    assert _days_between("2024-01-01T00:00:00+00:00", None) is None


def test_avg_empty_returns_none():
    assert _avg([]) is None


def test_avg_values():
    assert _avg([10.0, 20.0, 30.0]) == 20.0
