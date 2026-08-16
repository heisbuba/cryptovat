import time
import asyncio
import aiohttp
from decimal import Decimal, ROUND_HALF_UP

# --- Caches --- #
CACHE = {}                # snapshot data
CACHE_DURATION = 240       # 4 minutes

HIST_CACHE = {}            # 1-year historical aggregates
HIST_CACHE_DURATION = 3600 # 1 hour 

BASE_URL = "https://api.coingecko.com/api/v3"
REQUEST_TIMEOUT = aiohttp.ClientTimeout(connect=5, total=15)

STEALTH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Connection": "keep-alive",
}


def format_compact(num):
    """Converts large numbers into human-readable strings (e.g., 1.5M, 2B)."""
    if num is None or num == 0: return "0"
    for unit in ['', 'K', 'M', 'B', 'T']:
        if abs(num) < 1000.0:
            return f"{num:,.2f}{unit}".replace(".00", "")
        num /= 1000.0
    return f"{num:,.2f}P"


def _build_headers(cg_key: str) -> dict:
    headers = STEALTH_HEADERS.copy()
    cg_key = (cg_key or "").strip()
    if cg_key and cg_key != "CONFIG_REQUIRED_CG":
        headers["x-cg-demo-api-key" if cg_key.startswith("CG-") else "x-cg-pro-api-key"] = cg_key
    return headers


# --- Snapshot -- #

async def _fetch_snapshot_async(session: aiohttp.ClientSession, coin_id: str, headers: dict) -> dict:
    url = (f"{BASE_URL}/coins/{coin_id}?"
           "localization=false&tickers=false&market_data=true&"
           "community_data=false&developer_data=false&sparkline=false&"
           "price_change_percentage=1h")
    try:
        async with session.get(url, headers=headers) as r:
            if r.status == 429:
                return {"status": "error", "message": "Rate Limit Hit. Please wait."}
            if r.status != 200:
                return {"status": "error", "message": f"API {r.status}"}
            res = await r.json()
    except Exception as e:
        return {"status": "error", "message": str(e)}

    mkt = res.get('market_data', {})
    symbol = res.get('symbol', '').upper()

    mcap = mkt.get('market_cap', {}).get('usd', 0) or 0
    vol = mkt.get('total_volume', {}).get('usd', 0) or 0

    p_ch_24h = mkt.get('price_change_percentage_24h', 0) or 0
    p_ch_1h = mkt.get('price_change_percentage_1h_in_currency', {}).get('usd', 0) or 0

    d_vol = Decimal(str(vol))
    d_mcap = Decimal(str(mcap))

    vtmr_val = (d_vol / d_mcap).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) if d_mcap > 0 else 0
    vtpc_val = vol / abs(p_ch_24h) if p_ch_24h != 0 else 0
    current_price = mkt.get('current_price', {}).get('usd', 0)

    links = {
        "cg": f"https://www.coingecko.com/en/coins/{coin_id}",
        "tv": f"https://www.tradingview.com/chart/?symbol={symbol}USDT"
    }

    return {
        "status": "success",
        "vitals": {
            "name": res.get('name', 'Unknown'),
            "symbol": symbol,
            "price": f"${current_price:,.8f}" if current_price < 1 else f"${current_price:,.2f}",
            "mcap": f"${format_compact(mcap)}",
            "vol24h": f"${format_compact(vol)}"
        },
        "ratios": {
            "vtmr": f"{vtmr_val}x",
            "vtpc": f"${format_compact(vtpc_val)}"
        },
        "velocity": {
            "h1": f"{p_ch_1h:+.2f}%",
            "h24": f"{p_ch_24h:+.2f}%",
            "d7": f"{(mkt.get('price_change_percentage_7d') or 0):+.2f}%",
            "m1": f"{(mkt.get('price_change_percentage_30d') or 0):+.2f}%",
            "y1": f"{(mkt.get('price_change_percentage_1y') or 0):+.2f}%"
        },
        "supply": {
            "total": format_compact(mkt.get('total_supply', 0))
        },
        "links": links
    }


# --- Historical monthly metrics -- #

def _compute_historical_metrics(prices: list, volumes: list) -> dict | None:
    """Pure, no I/O. Degrades gracefully for coins younger than 30 days —
    uses whatever history is available rather than requiring a full 30."""
    n = min(len(prices), len(volumes))
    if n < 7:
        return None
    prices, volumes = prices[:n], volumes[:n]

    avg_7d_daily_vol = sum(volumes[-7:]) / min(7, n)
    avg_30d_vol = sum(volumes) / n

    total_dollar_vol = sum(p * v for p, v in zip(prices, volumes))
    total_vol = sum(volumes)
    vwap_30d = (total_dollar_vol / total_vol) if total_vol else 0.0

    return {"avg_7d_daily_vol": avg_7d_daily_vol, "avg_30d_vol": avg_30d_vol, "vwap_30d": vwap_30d}


async def _fetch_historical_async(session: aiohttp.ClientSession, coin_id: str, headers: dict) -> dict:
    placeholder = {"avg_7d_daily_vol": "—", "avg_30d_vol": "—", "vwap_30d": "—"}
    url = f"{BASE_URL}/coins/{coin_id}/market_chart"
    params = {"vs_currency": "usd", "days": "30", "interval": "daily"}
    try:
        async with session.get(url, params=params, headers=headers) as r:
            if r.status != 200:
                return placeholder
            res = await r.json()
    except Exception:
        return placeholder

    prices = [p[1] for p in res.get("prices", []) if len(p) > 1]
    volumes = [v[1] for v in res.get("total_volumes", []) if len(v) > 1]

    metrics = _compute_historical_metrics(prices, volumes)
    if metrics is None:
        return placeholder

    return {
        "avg_7d_daily_vol": f"${format_compact(metrics['avg_7d_daily_vol'])}",
        "avg_30d_vol": f"${format_compact(metrics['avg_30d_vol'])}",
        "vwap_30d": f"${format_compact(metrics['vwap_30d'])}",
    }

# --- Orchestration --- #

async def _fetch_needed(coin_id: str, headers: dict, need_snapshot: bool, need_historical: bool):
    async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
        coros = []
        if need_snapshot:
            coros.append(_fetch_snapshot_async(session, coin_id, headers))
        if need_historical:
            coros.append(_fetch_historical_async(session, coin_id, headers))
        results = await asyncio.gather(*coros)
    it = iter(results)
    snapshot = next(it) if need_snapshot else None
    historical = next(it) if need_historical else None
    return snapshot, historical


def calculate_deep_dive(coin_id: str, user_keys: dict) -> dict:
    """Fetches market data + 1-year history from CoinGecko and returns a
    structured payload."""
    coin_id = coin_id.strip().lower()
    now = time.time()

    global CACHE, HIST_CACHE
    CACHE = {k: v for k, v in CACHE.items() if now < v['expires']}
    HIST_CACHE = {k: v for k, v in HIST_CACHE.items() if now < v['expires']}

    need_snapshot = coin_id not in CACHE
    need_historical = coin_id not in HIST_CACHE

    if need_snapshot or need_historical:
        headers = _build_headers(str(user_keys.get("COINGECKO_API_KEY", "")))
        snapshot, historical = asyncio.run(_fetch_needed(coin_id, headers, need_snapshot, need_historical))

        if need_snapshot:
            if snapshot.get("status") == "error":
                return snapshot
            CACHE[coin_id] = {"data": snapshot, "expires": time.time() + CACHE_DURATION}

        if need_historical:
            HIST_CACHE[coin_id] = {"data": historical, "expires": time.time() + HIST_CACHE_DURATION}
    else:
        print(f"    ⚡ Serving {coin_id} from cache")

    payload = dict(CACHE[coin_id]["data"])
    payload["historical"] = HIST_CACHE[coin_id]["data"]
    return payload