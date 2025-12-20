import time
import datetime
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Tuple
import config
from utils import create_session, short_num, now_str

SESSION = create_session()

def fetch_coingecko(session):
    tokens = []
    print("   Scanning CoinGecko...")
    for page in range(1, 5):
        url = "https://api.coingecko.com/api/v3/coins/markets"
        params = {"vs_currency": "usd", "order": "market_cap_desc", "per_page": 250, "page": page}
        try:
            r = session.get(url, params=params, timeout=15)
            r.raise_for_status()
            data = r.json()
            for t in data:
                symbol = (t.get("symbol") or "").upper()
                if symbol in config.STABLECOINS: continue
                volume = float(t.get("total_volume") or 0)
                marketcap = float(t.get("market_cap") or 0)
                if marketcap and volume > 0.75 * marketcap:
                    tokens.append({"symbol": symbol, "marketcap": marketcap, "volume": volume, "source": "CG"})
            time.sleep(0.2)
        except: continue
    print(f"   CoinGecko: {len(tokens)} tokens")
    return tokens

def fetch_coinmarketcap(session):
    tokens = []
    print("   Scanning CoinMarketCap...")
    if not config.CMC_API_KEY or "CONFIG_REQUIRED" in config.CMC_API_KEY:
        print("   ⚠️  No CMC API key")
        return tokens
    headers = {"X-CMC_PRO_API_KEY": config.CMC_API_KEY}
    for start in range(1, 1001, 100):
        url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"
        params = {"start": start, "limit": 100, "convert": "USD"}
        try:
            r = session.get(url, headers=headers, params=params, timeout=15)
            r.raise_for_status()
            data = r.json().get("data", [])
            for t in data:
                symbol = (t.get("symbol") or "").upper()
                if symbol in config.STABLECOINS: continue
                quote = t.get("quote", {}).get("USD", {})
                volume = float(quote.get("volume_24h") or 0)
                marketcap = float(quote.get("market_cap") or 0)
                if marketcap and volume > 0.75 * marketcap:
                    tokens.append({"symbol": symbol, "marketcap": marketcap, "volume": volume, "source": "CMC"})
            time.sleep(0.2)
        except: continue
    print(f"   CoinMarketCap: {len(tokens)} tokens")
    return tokens

def fetch_livecoinwatch(session):
    tokens = []
    if not config.LIVECOINWATCH_API_KEY or "CONFIG_REQUIRED" in config.LIVECOINWATCH_API_KEY:
        print("   ⚠️  No LCW API key")
        return tokens
    print("   Scanning LiveCoinWatch...")
    url = "https://api.livecoinwatch.com/coins/list"
    headers = {"content-type": "application/json", "x-api-key": config.LIVECOINWATCH_API_KEY}
    payload = {"currency": "USD", "sort": "rank", "order": "ascending", "offset": 0, "limit": 1000, "meta": True}
    try:
        r = session.post(url, json=payload, headers=headers, timeout=20)
        data = r.json()
        for t in data:
            symbol = (t.get("code") or "").upper()
            if symbol in config.STABLECOINS: continue
            volume = float(t.get("volume") or 0)
            marketcap = float(t.get("cap") or 0)
            if marketcap and volume > 0.75 * marketcap:
                tokens.append({"symbol": symbol, "marketcap": marketcap, "volume": volume, "source": "LCW"})
    except: pass
    print(f"   LiveCoinWatch: {len(tokens)} tokens")
    return tokens

def fetch_coinrankings(session):
    tokens = []
    print("   Scanning CoinRankings...")
    if not config.COINRANKINGS_API_KEY or "CONFIG_REQUIRED" in config.COINRANKINGS_API_KEY:
        print("   ⚠️  No CR API key")
        return tokens
    headers = {"x-access-token": config.COINRANKINGS_API_KEY}
    url = "https://api.coinranking.com/v2/coins"
    for offset in range(0, 1000, 100):
        params = {"limit": 100, "offset": offset, "orderBy": "marketCap", "orderDirection": "desc"}
        try:
            r = session.get(url, headers=headers, params=params, timeout=15)
            data = r.json().get("data", {}).get("coins", [])
            for coin in data:
                symbol = (coin.get("symbol") or "").upper()
                if symbol in config.STABLECOINS: continue
                volume = float(coin.get("24hVolume") or 0)
                marketcap = float(coin.get("marketCap") or 0)
                if marketcap and volume > 0.75 * marketcap:
                    tokens.append({"symbol": symbol, "marketcap": marketcap, "volume": volume, "source": "CR"})
            time.sleep(0.2)
        except: pass
    print(f"   CoinRankings: {len(tokens)} tokens")
    return tokens

def run_spot_analysis(user_id: str):
    print("   📊 Starting fresh spot analysis...")
    
    sources = [fetch_coingecko, fetch_coinmarketcap, fetch_livecoinwatch, fetch_coinrankings]
    results = []
    
    with ThreadPoolExecutor(max_workers=4) as exe:
        futures = [exe.submit(fn, SESSION) for fn in sources]
        for f in as_completed(futures):
            try:
                res = f.result(timeout=60)
                if res: results.extend(res)
            except: continue
    
    all_data = {}
    for t in results:
        sym = t.get('symbol', '').upper()
        if sym: all_data.setdefault(sym, []).append(t)
    
    verified = []
    for sym, tokens in all_data.items():
        volumes = [float(t['volume']) for t in tokens]
        mcs = [float(t['marketcap']) for t in tokens]
        if not volumes or not mcs: continue
        
        avg_vol = sum(volumes)/len(volumes)
        avg_mc = sum(mcs)/len(mcs)
        ratio = avg_vol/avg_mc if avg_mc else 0
        large_cap = any(m > 1_000_000_000 for m in mcs)

        # Exact logic from v4.0
        if (len(tokens) == 1 and large_cap and ratio >= 0.50) or (len(tokens) >= 2 and ratio > 0.75):
            verified.append({
                "symbol": sym, 
                "marketcap": avg_mc, 
                "volume": avg_vol,
                "flipping_multiple": ratio, 
                "source_count": len(tokens), 
                "large_cap": large_cap
            })
    
    hot_tokens = sorted(verified, key=lambda x: x['flipping_multiple'], reverse=True)
    
    # HTML Report Generation
    date_prefix = datetime.datetime.now().strftime("%b-%d-%y")
    filename = f"{user_id}_Volumed_Spot_Tokens_{date_prefix}.html"
    save_path = config.UPLOAD_FOLDER / filename
    current_time = now_str("%d-%m-%Y %H:%M:%S")
    
    max_flip = max((t.get('flipping_multiple', 0) for t in hot_tokens), default=0)
    high_volume = len([t for t in hot_tokens if t.get('flipping_multiple', 0) >= 2])
    large_cap_count = len([t for t in hot_tokens if t.get('large_cap')])

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Crypto Volume Tracker v2.0</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
            .header {{ text-align: center; background-color: #2c3e50; color: white; padding: 20px; border-radius: 10px; }}
            .summary {{ background-color: #34495e; color: white; padding: 15px; border-radius: 8px; margin: 10px 0; }}
            .table {{ width: 100%; border-collapse: collapse; background-color: white; }}
            .table th {{ background-color: #3498db; color: white; padding: 12px; text-align: left; }}
            .table td {{ padding: 10px; border-bottom: 1px solid #ddd; }}
            .table tr:nth-child(even) {{ background-color: #f2f2f2; }}
            .table tr:hover {{ background-color: #e8f4f8; }}
            .footer {{ text-align: center; margin-top: 20px; color: #7f8c8d; }}
            .large-cap {{ background-color: #e8f6f3 !important; }}
            .high-volume {{ color: #e74c3c; font-weight: bold; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>SPOT VOLUME CRYPTO TRACKER v2.0</h1>
            <p>High Volume Spot Tokens Analysis</p>
            <p><small>Generated on: {current_time}</small></p>
        </div>
        <div class="summary">
            <h3>Summary</h3>
            <p>Total High-Volume Tokens: {len(hot_tokens)}</p>
            <p>Peak Flipping (VTMR) Multiple: {max_flip:.1f}x</p>
            <p>High-Volume Tokens (2x+): {high_volume}</p>
            <p>Large-Cap Tokens (>$1B): {large_cap_count}</p>
        </div>
    """

    if hot_tokens:
        html += """<table class="table"><tr><th>Rank</th><th>Ticker</th><th>Market Cap</th><th>Volume 24h</th><th>Spot VTMR</th><th>Verifications</th><th>Large Cap</th></tr>"""
        for i, token in enumerate(hot_tokens):
            row_class = "large-cap" if token.get('large_cap') else ""
            volume_class = "high-volume" if token.get('flipping_multiple', 0) >= 2 else ""
            html += f"""
            <tr class="{row_class}">
                <td>#{i+1}</td>
                <td><b>{token.get('symbol')}</b></td>
                <td>${short_num(token.get('marketcap', 0))}</td>
                <td>${short_num(token.get('volume', 0))}</td>
                <td class="{volume_class}">{token.get('flipping_multiple', 0):.1f}x</td>
                <td>{token.get('source_count')}</td>
                <td>{'Yes' if token.get('large_cap') else 'No'}</td>
            </tr>"""
        html += "</table>"
    else:
        html += "<div style='text-align: center; padding: 40px;'><h3>No high-volume tokens found</h3></div>"

    html += """<div class="footer"><p>Generated by Spot Volume Crypto Tracker v2.0 | By (@heisbuba)</p></div></body></html>"""
    
    with open(save_path, "w", encoding="utf-8") as f: f.write(html)
    print(f"   ✅ Found {len(hot_tokens)} high-volume tokens.")