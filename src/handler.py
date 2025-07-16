import json
import os
from datetime import datetime, timezone

from src.bot_helpers import (
    get_table,
    send_message,
    get_quote_data,
    format_price_line,
    compute_cagr,
)

ALPHA_VANTAGE_KEY = os.environ['ALPHA_VANTAGE_KEY']


# --- Handler function definitions ---
from decimal import Decimal

def handle_start(body):
    chat_id = str(body.get('message', {}).get('chat', {}).get('id', ''))
    send_message(chat_id,
        "Yo fam! I'm your hype-bot—your stonks and crypto BFF. Drop a symbol and I'll slide into your chat when it's bussin' or sus AF. 🔥🚀\n"
        "Type !commands to see the drip."
    )
    return {'statusCode': 200}

def handle_set(body):
    chat_id = str(body.get('message', {}).get('chat', {}).get('id', ''))
    text = body.get('message', {}).get('text', '').strip()
    parts = text.split()
    if len(parts) != 4:
        send_message(chat_id, "Ayo, use: !set <SYMBOL> <DROP%> <MINUTES> fam 👀\nExample: !set AAPL 5 60")
        return {'statusCode': 200}
    try:
        symbol = parts[1].upper()
        threshold_percent = Decimal(str(float(parts[2])))
        interval_minutes = Decimal(str(int(parts[3])))
    except:
        send_message(chat_id, "Bro, gimme real numbers for percent and minutes.")
        return {'statusCode': 200}
    data = get_quote_data(symbol, ALPHA_VANTAGE_KEY)
    initial_price = data.get('price')
    if initial_price is None:
        send_message(chat_id, f"Bruh, couldn't fetch price for {symbol}. Try again.")
        return {'statusCode': 200}
    tbl = get_table('DDB_TABLE')
    tbl.put_item(Item={
        'chat_id': chat_id,
        'symbol': symbol,
        'threshold_percent': threshold_percent,
        'interval_minutes': interval_minutes,
        'alert_sent': False,
        'baseline_price': Decimal(str(initial_price)),
        'last_check': datetime.now(timezone.utc).isoformat()
    })
    send_message(chat_id, f'💯 Bet! Alert set for {symbol}: {threshold_percent}% drop in {interval_minutes} min.')
    return {'statusCode': 200}

def handle_price(body):
    chat_id = str(body.get('message', {}).get('chat', {}).get('id', ''))
    text = body.get('message', {}).get('text', '').strip()
    parts = text.split()
    if len(parts) != 2:
        send_message(chat_id, "Fam, use: !price <SYMBOL>\nExample: !price BTC-USD")
        return {'statusCode': 200}
    symbol = parts[1].upper()
    data = get_quote_data(symbol, ALPHA_VANTAGE_KEY)
    if not data or data.get('price') is None:
        send_message(chat_id, f"Bruh, couldn't fetch price for '{symbol}'.")
        return {'statusCode': 200}
    msg = format_price_line(symbol, data)
    send_message(chat_id, msg)
    return {'statusCode': 200}

def handle_list(body):
    from boto3.dynamodb.conditions import Attr
    chat_id = str(body.get('message', {}).get('chat', {}).get('id', ''))
    tbl = get_table('DDB_TABLE')
    resp = tbl.scan(FilterExpression=Attr('chat_id').eq(chat_id))
    items = resp.get('Items', [])
    if not items:
        send_message(chat_id, "No alerts yet, chief. Set one and let's get this bread!")
    else:
        msg = "👀 Here's your alert squad:\n"
        for it in items:
            msg += f'• {it["symbol"]} – {it["threshold_percent"]}% drop in {it["interval_minutes"]} min\n'
        send_message(chat_id, msg)
    return {'statusCode': 200}

def handle_delete(body):
    chat_id = str(body.get('message', {}).get('chat', {}).get('id', ''))
    text = body.get('message', {}).get('text', '').strip()
    parts = text.split()
    if len(parts) != 2:
        send_message(chat_id, "Yo, use: !delete <SYMBOL>")
        return {'statusCode': 200}
    symbol = parts[1].upper()
    tbl = get_table('DDB_TABLE')
    tbl.delete_item(Key={'chat_id': chat_id, 'symbol': symbol})
    send_message(chat_id, f'Deleted, no cap: {symbol} alert gone.')
    return {'statusCode': 200}

def handle_reset(body):
    from boto3.dynamodb.conditions import Attr
    chat_id = str(body.get('message', {}).get('chat', {}).get('id', ''))
    tbl = get_table('DDB_TABLE')
    resp = tbl.scan(FilterExpression=Attr('chat_id').eq(chat_id))
    for it in resp.get('Items', []):
        tbl.delete_item(Key={'chat_id': chat_id, 'symbol': it['symbol']})
    send_message(chat_id, "All alerts nuked, we good. 🚮")
    return {'statusCode': 200}

def handle_createindex(body):
    chat_id = str(body.get('message', {}).get('chat', {}).get('id', ''))
    text = body.get('message', {}).get('text', '').strip()
    parts = text.split()
    if len(parts) < 3:
        send_message(chat_id, "How to squad up: !createindex <NAME> <SYMBOL1> <SYMBOL2> ...")
        return {'statusCode': 200}
    name = parts[1]
    symbols = [s.upper() for s in parts[2:]]
    idx_tbl = get_table('INDEX_TABLE')
    created_at = datetime.now(timezone.utc).isoformat()
    baseline_prices = []
    for sym in symbols:
        data = get_quote_data(sym, ALPHA_VANTAGE_KEY)
        price = data.get('price')
        baseline_prices.append(Decimal(str(price)) if price is not None else Decimal('0'))
    idx_tbl.put_item(Item={
        'chat_id': chat_id,
        'index_name': name,
        'symbols': symbols,
        'baseline_price': sum(baseline_prices),
        'baseline_prices': baseline_prices,
        'created_at': created_at,
    })
    send_message(chat_id, f'🔥 Squad mix "{name}" locked in: {", ".join(symbols)}')
    return {'statusCode': 200}

def handle_index(body):
    chat_id = str(body.get('message', {}).get('chat', {}).get('id', ''))
    text = body.get('message', {}).get('text', '').strip()
    parts = text.split()
    if len(parts) != 2:
        send_message(chat_id, "Bro, use: !index <NAME>")
        return {'statusCode': 200}
    name = parts[1]
    idx_tbl = get_table('INDEX_TABLE')
    res = idx_tbl.get_item(Key={'chat_id': chat_id, 'index_name': name})
    item = res.get('Item')
    if not item:
        send_message(chat_id, f"Sheesh, squad mix \"{name}\" not found.")
        return {'statusCode': 200}
    symbols = item['symbols']
    baselines = [Decimal(str(bp)) for bp in item.get('baseline_prices', [])]
    created_iso = item.get('created_at')
    lines = []
    total_current = 0.0
    for sym, base in zip(symbols, baselines):
        data = get_quote_data(sym, ALPHA_VANTAGE_KEY)
        lines.append(format_price_line(sym, data))
        total_current += data.get('price') or 0.0
    # Convert total_current to Decimal for compute_cagr
    current_total_dec = Decimal(str(total_current))
    cagr = compute_cagr(baselines, current_total_dec, created_iso)
    # Compute average symbol return to avoid mixing Decimal and float
    ind_returns = []
    for sym, base in zip(symbols, baselines):
        data = get_quote_data(sym, ALPHA_VANTAGE_KEY)
        price = data.get('price') or 0.0
        base_f = float(base)
        if base_f > 0:
            ind_returns.append((price / base_f - 1) * 100)
    avg_ret = sum(ind_returns) / len(ind_returns) if ind_returns else 0.0
    msg = f"💹 Squad mix: {name}\n" + "\n".join(lines)
    msg += f"\n💼 Portfolio Return (CAGR): {cagr:.2f}%\n"
    msg += f"📊 Avg Symbol Return: {avg_ret:.2f}%\n"
    send_message(chat_id, msg)
    return {'statusCode': 200}

def handle_deleteindex(body):
    chat_id = str(body.get('message', {}).get('chat', {}).get('id', ''))
    text = body.get('message', {}).get('text', '').strip()
    parts = text.split()
    if len(parts) != 2:
        send_message(chat_id, "Yo, use: !deleteindex <NAME>")
        return {'statusCode': 200}
    name = parts[1]
    idx_tbl = get_table('INDEX_TABLE')
    idx_tbl.delete_item(Key={'chat_id': chat_id, 'index_name': name})
    send_message(chat_id, f'Dropped squad mix "{name}". Outta here! 🗑️')
    return {'statusCode': 200}

def handle_indexes(body):
    from boto3.dynamodb.conditions import Attr
    chat_id = str(body.get('message', {}).get('chat', {}).get('id', ''))
    idx_tbl = get_table('INDEX_TABLE')
    resp = idx_tbl.scan(FilterExpression=Attr('chat_id').eq(chat_id))
    items = resp.get('Items', [])
    if not items:
        send_message(chat_id, "No squad mixes saved, fam. Create one with !createindex.")
    else:
        msg = "📚 Your squad mixes:\n"
        for it in items:
            msg += f'• {it["index_name"]}: {", ".join(it["symbols"])}\n'
        send_message(chat_id, msg)
    return {'statusCode': 200}

def handle_commands(body):
    chat_id = str(body.get('message', {}).get('chat', {}).get('id', ''))
    send_message(chat_id,
        "Here's the plug on commands:\n"
        "• !start\n"
        "• !set <SYMBOL> <DROP%> <MINUTES>\n"
        "• !price <SYMBOL>\n"
        "• !list\n"
        "• !delete <SYMBOL>\n"
        "• !reset\n"
        "• !createindex <NAME> <SYMBOLS>\n"
        "• !index <NAME>\n"
        "• !deleteindex <NAME>\n"
        "• !indexes\n"
        "• !commands"
    )
    return {'statusCode': 200}


COMMANDS = {
    '!start': handle_start,
    '!set': handle_set,
    '!price': handle_price,
    '!list': handle_list,
    '!delete': handle_delete,
    '!reset': handle_reset,
    '!createindex': handle_createindex,
    '!index': handle_index,
    '!deleteindex': handle_deleteindex,
    '!indexes': handle_indexes,
    '!commands': handle_commands
}

def lambda_handler(event, context):
    body = json.loads(event.get('body','{}'))
    chat_id = str(body.get('message',{}).get('chat',{}).get('id',''))
    text = body.get('message',{}).get('text','').strip()
    cmd = text.split()[0] if text else ''
    handler = COMMANDS.get(cmd)
    if handler:
        return handler(body)
    return {'statusCode':200}

def price_checker(event, context):
    """
    Scheduled function to scan alerts and send notifications when threshold is met.
    """
    tbl = get_table('DDB_TABLE')
    response = tbl.scan(FilterExpression=Attr('alert_sent').eq(False))
    for item in response.get('Items', []):
        chat_id = item['chat_id']
        symbol = item['symbol']
        last = item.get('last_check')
        if last:
            last_dt = datetime.fromisoformat(last)
            if (datetime.now(timezone.utc) - last_dt).total_seconds() < float(item.get('interval_minutes', 0)) * 60:
                continue
        baseline = float(item.get('baseline_price', 0))
        threshold = float(item.get('threshold_percent', 0))
        current_price = get_price(symbol)
        if current_price is None:
            tbl.update_item(
                Key={'chat_id': chat_id, 'symbol': symbol},
                UpdateExpression="SET last_check = :lc",
                ExpressionAttributeValues={':lc': datetime.now(timezone.utc).isoformat()}
            )
            continue
        alert_sent = False
        # Detect drop beyond threshold
        if current_price <= baseline * (1 - threshold / 100):
            send_message(chat_id, f"🚨 {symbol} has dropped {threshold}% from ${baseline:.2f} to ${current_price:.2f}")
            alert_sent = True
        update_expr = "SET last_check = :lc"
        expr_attr_vals = {':lc': datetime.now(timezone.utc).isoformat()}
        if alert_sent:
            update_expr += ", alert_sent = :val"
            expr_attr_vals[':val'] = True
        tbl.update_item(
            Key={'chat_id': chat_id, 'symbol': symbol},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_attr_vals
        )
