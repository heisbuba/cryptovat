import re
import time
import asyncio
import threading
import aiohttp

from ..config import STABLECOINS
from .utils import short_num

# TOKENS CACHING

CACHE: dict = {"data": None, "timestamp": 0}
CACHE_TTL = 1800  # 3 mins data cache
_cache_lock = threading.Lock()

PAGES = 6        
PER_PAGE = 250
LC_THRESHOLD = 1_000_000_000 

STEALTH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

COINGECKO_URL = "https://api.coingecko.com/api/v3/coins/markets"

REQUEST_TIMEOUT = aiohttp.ClientTimeout(connect=5, total=10)


def invalidate_cache() -> None:
    """Force the next get_screener_data() call to re-fetch."""
    with _cache_lock:
        CACHE["data"] = None
        CACHE["timestamp"] = 0


# ── Fetch (async) ────────────────────────────────────────────────────────────

def _build_headers(api_key: str) -> dict:
    headers = STEALTH_HEADERS.copy()
    api_key = (api_key or "").strip()
    if api_key:
        headers["x-cg-demo-api-key" if api_key.startswith("CG-") else "x-cg-pro-api-key"] = api_key
    return headers


async def _fetch_page_async(session: aiohttp.ClientSession, page: int, api_key: str) -> list:
    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": PER_PAGE,
        "page": page,
        "price_change_percentage": "24h,7d,30d,1y",
        "sparkline": "false",
    }
    headers = _build_headers(api_key)
    try:
        async with session.get(COINGECKO_URL, params=params, headers=headers) as r:
            if r.status in (401, 403, 429) and ("x-cg-demo-api-key" in headers or "x-cg-pro-api-key" in headers):
                async with session.get(COINGECKO_URL, params=params, headers=STEALTH_HEADERS) as r2:
                    return await r2.json() if r2.status == 200 else []
            return await r.json() if r.status == 200 else []
    except Exception:
        return []


async def _fetch_top_1000_async(api_key: str) -> list:
    connector = aiohttp.TCPConnector(limit=PAGES, limit_per_host=PAGES)
    async with aiohttp.ClientSession(connector=connector, timeout=REQUEST_TIMEOUT) as session:
        page_results = await asyncio.gather(*[
            _fetch_page_async(session, p, api_key) for p in range(1, PAGES + 1)
        ])

    coins = [c for page in page_results for c in page]
    
    coins = [c for c in coins if (c.get("symbol") or "").upper() not in STABLECOINS]

    return [_enrich(c) for c in coins if c and isinstance(c, dict)]


def _fetch_top_1000(api_key: str) -> list:
    return asyncio.run(_fetch_top_1000_async(api_key))


# ── Enrichment ─────────────────────────────────────────────────────────────

def _fmt_price(p) -> str:
    if p is None: return "N/A"
    if p >= 10_000: return f"${p:,.0f}"
    if p >= 1: return f"${p:,.2f}"
    if p >= 0.001: return f"${p:.4f}"
    return f"${p:.6f}"


def _fmt_large(n) -> str:
    if not n: return "—"
    return f"${short_num(n)}"


def _fmt_pct(v) -> str:
    if v is None: return "—"
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:.2f}%"


def _pct_class(v) -> str:
    if v is None: return "pct-neutral"
    return "pct-pos" if v >= 0 else "pct-neg"


def _enrich(coin: dict) -> dict:
    vol = coin.get("total_volume") or 0
    mcap = coin.get("market_cap") or 0
    large_cap = mcap > LC_THRESHOLD  

    if mcap > 0:
        vtmr_raw = vol / mcap
        vtmr_display = f"{vtmr_raw:.3f}x"
        if vtmr_raw >= 1.0:
            vtmr_class = "vtmr-high"
        elif vtmr_raw >= 0.5:
            vtmr_class = "vtmr-mid"
        else:
            vtmr_class = "vtmr-low"
    else:
        vtmr_raw, vtmr_display, vtmr_class = 0.0, "—", "vtmr-none"

    p24 = coin.get("price_change_percentage_24h_in_currency")
    p7d = coin.get("price_change_percentage_7d_in_currency")
    p30d = coin.get("price_change_percentage_30d_in_currency")
    p1y = coin.get("price_change_percentage_1y_in_currency")

    return {
        **coin,
        "vtmr_raw": vtmr_raw,
        "vtmr_display": vtmr_display,
        "vtmr_class": vtmr_class,
        "large_cap": large_cap,
        "fmt_price": _fmt_price(coin.get("current_price")),
        "fmt_mcap": _fmt_large(mcap),
        "fmt_volume": _fmt_large(vol),
        "fmt_24h": _fmt_pct(p24),
        "fmt_7d": _fmt_pct(p7d),
        "fmt_30d": _fmt_pct(p30d),
        "fmt_1y": _fmt_pct(p1y),
        "cls_24h": _pct_class(p24),
        "cls_7d": _pct_class(p7d),
        "cls_30d": _pct_class(p30d),
        "cls_1y": _pct_class(p1y),
    }


# ── Cache-backed accessor ────────────────────────────────────────────────────

def get_screener_data(api_key: str) -> list:
    """Return cached top-1000 data, refreshing if stale (> CACHE_TTL) or empty."""
    with _cache_lock:
        now = time.time()
        if CACHE["data"] and (now - CACHE["timestamp"] <= CACHE_TTL):
            return CACHE["data"]

    data = _fetch_top_1000(api_key)

    with _cache_lock:
        if data:
            CACHE["data"] = data
            CACHE["timestamp"] = time.time()
        return CACHE["data"] or []


# ── Filters ──────────────────────────────────────────────────────────────────

DEFAULT_FILTERS: dict[str, str] = {
    "min_24h": "",
    "min_7d": "",
    "min_30d": "",
    "min_1y": "",
    "min_mcap": "10m",   
    "min_vtmr": "0.2",  
}

_HUMAN_NUMBER_FIELDS: frozenset[str] = frozenset({"min_mcap"})

INCLUDE_NO_1Y_KEY = "include_no_1y"
INCLUDE_NO_1Y_DEFAULT = "1"

_HUMAN_NUM_RE = re.compile(r"^\s*([+-]?\d+(?:\.\d+)?)\s*([kKmMbBtT]?)\s*$")
_HUMAN_NUM_MULTIPLIERS = {"": 1, "k": 1e3, "m": 1e6, "b": 1e9, "t": 1e12}


def parse_human_number(raw: str) -> float:
    """Parses strings like '5m', '1.2b', '500k', '2500000' into a float.
    Raises ValueError if the string doesn't match the expected shape."""
    match = _HUMAN_NUM_RE.match(str(raw))
    if not match:
        raise ValueError(f"Unparseable human number: {raw!r}")
    value, suffix = match.groups()
    return float(value) * _HUMAN_NUM_MULTIPLIERS[suffix.lower()]


def _safe_float(val) -> float | None:
    try:
        if val is None:
            return None
        if isinstance(val, str):
            val = val.strip()
            if val == "":
                return None
            val = val.replace('%', '')
            val = val.lower().replace('x', '')
        return float(val)
    except (TypeError, ValueError):
        return None


def parse_threshold(key: str, raw_val) -> float | None:
    """Returns None if blank — None means 'no constraint', not zero."""
    if raw_val is None or str(raw_val).strip() == "":
        return None
    if key in _HUMAN_NUMBER_FIELDS:
        try:
            return parse_human_number(raw_val)
        except (TypeError, ValueError):
            return None
    return _safe_float(raw_val)


# Namespaced so screener state
SESSION_PREFIX = "pcp_active_"
PROFILE_PREFIX = "pcp_default_"


def resolve_filter(key: str, session: dict, profile: dict) -> str:
    """Priority: session > profile default > hardcoded default."""
    s_val = session.get(f"{SESSION_PREFIX}{key}")
    if s_val is not None:
        return str(s_val)
    p_val = profile.get(f"{PROFILE_PREFIX}{key}")
    return str(p_val) if p_val is not None else DEFAULT_FILTERS[key]


def _get_vtmr(raw: dict) -> float:
    v = raw.get("vtmr_raw")
    if v is not None:
        return v
    mcap = raw.get("market_cap") or 0.0
    vol = raw.get("total_volume") or 0.0
    return (vol / mcap) if mcap > 0 else 0.0


def apply_filters(raw: dict, th: dict, include_no_1y: bool = True) -> bool:
    """
    Every key in th may be None, meaning that filter is off — any
    combination of set/unset filters is valid.
    """
    p24 = raw.get("price_change_percentage_24h_in_currency")
    p7d = raw.get("price_change_percentage_7d_in_currency")
    p30d = raw.get("price_change_percentage_30d_in_currency")
    p1y = raw.get("price_change_percentage_1y_in_currency")
    mcap = raw.get("market_cap") or 0.0
    vtmr = _get_vtmr(raw)

    if th["min_24h"] is not None and p24 is not None and p24 < th["min_24h"]: return False
    if th["min_7d"] is not None and p7d is not None and p7d < th["min_7d"]: return False
    if th["min_30d"] is not None and p30d is not None and p30d < th["min_30d"]: return False
    if th["min_1y"] is not None:
        if p1y is None:
            if not include_no_1y:
                return False
        elif p1y < th["min_1y"]:
            return False
    if th["min_mcap"] is not None and mcap < th["min_mcap"]: return False
    if th["min_vtmr"] is not None and vtmr < th["min_vtmr"]: return False
    return True


def filter_tokens(tokens: list, thresholds: dict, include_no_1y: bool = True) -> list:
    return [t for t in tokens if apply_filters(t, thresholds, include_no_1y)]