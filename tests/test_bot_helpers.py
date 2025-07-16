import pytest
from decimal import Decimal
from datetime import datetime, timedelta, timezone

from src.bot_helpers import format_price_line, compute_cagr, avg_equal_return

@pytest.mark.parametrize("data,expected_prefix", [
    # Stock up scenario
    ({"price":150.0,"open":100.0,"high":155.0,"low":95.0,"volume":"123","adj":149.0}, "🟢"),  
    # Stock down scenario
    ({"price":90.0,"open":100.0,"high":105.0,"low":85.0,"volume":"456","adj":None}, "🔴"),  
    # Crypto (no open)
    ({"price":42.0}, "⚪"),
])
def test_format_price_line(data, expected_prefix):
    """format_price_line should prefix correctly for various cases."""
    line = format_price_line("SYM", data)
    assert line.startswith(expected_prefix)
    assert "SYM" in line

def test_compute_cagr_flat_year():
    """compute_cagr returns ~0% for no change over one year."""
    baselines = [Decimal('100'), Decimal('200')]
    now = datetime.now(timezone.utc)
    created = (now - timedelta(days=365)).isoformat()
    cagr = compute_cagr(baselines, 300.0, created)
    assert pytest.approx(0.0, abs=1e-2) == cagr

def test_compute_cagr_half_year_gain():
    """compute_cagr annualizes a half-year 21% gain to ~46.4%."""
    baselines = [Decimal('100')]
    now = datetime.now(timezone.utc)
    created = (now - timedelta(days=182)).isoformat()
    cagr = compute_cagr(baselines, 121.0, created)
    assert pytest.approx(46.4, rel=1e-2) == cagr

def test_avg_equal_return(monkeypatch):
    """avg_equal_return should calculate equal-weight returns correctly."""
    # Stub get_quote_data to return predictable prices
    monkeypatch.setattr("src.bot_helpers.get_quote_data",
                        lambda sym, key: {"price": 2.0 if sym=="A" else 4.0})
    baselines = [1, 2]
    symbols = ["A","B"]
    avg = avg_equal_return(baselines, symbols, alpha_key="DUMMY")
    # (2/1 -1)*100 =100%, (4/2 -1)*100 =100%, average =100
    assert pytest.approx(100.0) == avg