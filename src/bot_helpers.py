

import json
import os
from decimal import Decimal
from datetime import datetime, timezone

import urllib3
import boto3
from boto3.dynamodb.conditions import Attr

# Configuration
API_URL = f"https://api.telegram.org/bot{os.environ['BOT_TOKEN']}"
HTTP = urllib3.PoolManager()
DYNAMODB = boto3.resource('dynamodb')

def get_table(name):
    """
    Return a DynamoDB Table resource for the given environment variable key.
    """
    return DYNAMODB.Table(os.environ[name])

def send_message(chat_id, text):
    """
    Send a Telegram message via the Bot API.
    """
    HTTP.request(
        'POST',
        f"{API_URL}/sendMessage",
        body=json.dumps({'chat_id': chat_id, 'text': text}).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )

def get_quote_data(symbol, alpha_key):
    """
    Fetch price, open, high, low, volume, and adjusted close for a symbol.
    """
    if '-' in symbol:
        from_sym, to_sym = symbol.split('-')
        url = (
            f"https://www.alphavantage.co/query"
            f"?function=CURRENCY_EXCHANGE_RATE"
            f"&from_currency={from_sym}"
            f"&to_currency={to_sym}"
            f"&apikey={alpha_key}"
        )
        resp = HTTP.request('GET', url)
        data = json.loads(resp.data.decode())
        rate = data.get('Realtime Currency Exchange Rate', {}).get('5. Exchange Rate')
        return {'price': float(rate) if rate else None}
    url = (
        f"https://www.alphavantage.co/query"
        f"?function=GLOBAL_QUOTE"
        f"&symbol={symbol}"
        f"&apikey={alpha_key}"
    )
    resp = HTTP.request('GET', url)
    quote = json.loads(resp.data.decode()).get('Global Quote', {})
    return {
        'price': float(quote.get('05. price', 0)),
        'open':   _to_float(quote.get('02. open')),
        'high':   _to_float(quote.get('03. high')),
        'low':    _to_float(quote.get('04. low')),
        'volume': quote.get('06. volume'),
        'adj':    get_adjusted_close(symbol, alpha_key)
    }

def get_adjusted_close(symbol, alpha_key):
    """
    Fetch the latest daily adjusted close for a stock symbol.
    """
    if '-' in symbol:
        return None
    url = (
        f"https://www.alphavantage.co/query"
        f"?function=TIME_SERIES_DAILY_ADJUSTED"
        f"&symbol={symbol}"
        f"&apikey={alpha_key}"
    )
    resp = HTTP.request('GET', url)
    ts = json.loads(resp.data.decode()).get('Time Series (Daily)', {})
    if not ts:
        return None
    dates = sorted(ts.keys())
    return float(ts[dates[-1]]['5. adjusted close'])

def _to_float(val):
    """
    Safely convert a value to float, returning None on failure.
    """
    try:
        return float(val)
    except:
        return None

def format_price_line(symbol, data):
    """
    Format a line of price data with color indicator and stats.
    """
    open_p = data.get('open')  # Safe access  [oai_citation:7‡Real Python](https://realpython.com/python-keyerror/?utm_source=chatgpt.com)
    color = (
        '🟢' if open_p is not None and data['price'] > open_p else
        '🔴' if open_p is not None else
        '⚪'
    )
    line = f"{color} • {symbol}: ${data['price']:.2f}"
    if data.get('adj') is not None:
        line += f" (Adj: ${data['adj']:.2f})"
    if open_p is not None:
        line += (
            f", O:{open_p:.2f}, H:{data.get('high', 0):.2f}, "
            f"L:{data.get('low', 0):.2f}, V:{data.get('volume')}"
        )
    return line

def compute_cagr(baselines, current_total, created_iso):
    """
    Compute the annualized CAGR based on baselines and current total.
    """
    baseline_sum = sum(baselines)
    if baseline_sum <= 0:
        return 0.0
    # Convert current_total (float) to Decimal for safe arithmetic
    current_dec = Decimal(str(current_total))
    total_return = current_dec / baseline_sum - Decimal('1')
    if created_iso:
        created_dt = datetime.fromisoformat(created_iso)
        delta = datetime.now(timezone.utc) - created_dt
        years = delta.days / 365.25 if delta.days > 0 else 0
        if years > 0:
            return ((1 + total_return) ** (1 / years) - 1) * 100
    return total_return * 100

def avg_equal_return(baselines, symbols, alpha_key):
    """
    Compute the equal-weight average return across symbols.
    """
    rets = []
    for base, sym in zip(baselines, symbols):
        data = get_quote_data(sym, alpha_key)
        price = data.get('price') or 0
        if base > 0:
            rets.append((price / base - 1) * 100)
    return sum(rets) / len(rets) if rets else 0.0