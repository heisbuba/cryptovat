import time
import datetime
import html
import threading
import asyncio
import aiohttp
from typing import List, Dict, Any, Tuple

from src.state import get_user_temp_dir, update_progress, set_pending_file
from src.config import STABLECOINS
from src.services.utils import short_num, now_str

REQUEST_TIMEOUT = aiohttp.ClientTimeout(connect=5, total=20)

def spot_volume_tracker(user_keys, user_id) -> None:
    """Spot volume analysis, generates HTML report. Prioritizes CoinGecko for accuracy."""
    def safe_float(val, default):
        try:
            if val is None or str(val).strip() == "":
                return default
            return float(val)
        except (ValueError, TypeError):
            return default

    print("    Starting fresh spot analysis...")
    threading.current_thread().name = f"user_{user_id}"
    update_progress(user_id, 10, "Starting spot market scan...", "active")

    CMC_API_KEY = user_keys.get("CMC_API_KEY", "CONFIG_REQUIRED_CMC")
    COINGECKO_API_KEY = user_keys.get("COINGECKO_API_KEY", "CONFIG_REQUIRED_CG")
    LIVECOINWATCH_API_KEY = user_keys.get("LIVECOINWATCH_API_KEY", "CONFIG_REQUIRED_LCW")

    settings = user_keys.get("engine_settings", {})
    MIN_VTMR    = safe_float(settings.get('min_vtmr'), 0.5)
    MAX_VTMR    = safe_float(settings.get('max_vtmr'), 199.0)
    MIN_LC_VTMR = safe_float(settings.get('min_largecap_vtmr'), 0.5)
    LC_THRESHOLD = 1_000_000_000
    FETCH_THRESHOLD = min(MIN_VTMR, MIN_LC_VTMR)

    # Stealth headers to avoid rate-limiting/blocking
    STEALTH_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }

    def create_html_report(hot_tokens: List[Dict[str, Any]]) -> str:
        """Generate HTML report with summary, table, and navigation."""
        date_prefix = datetime.datetime.now().strftime("%b-%d-%y")
        user_dir = get_user_temp_dir(user_id)
        html_file = user_dir / f"Spot_Analysis_Report_{date_prefix}.html"
        current_time = now_str("%d-%m-%Y %H:%M:%S")

        max_flip = max((t.get('flipping_multiple', 0) for t in hot_tokens), default=0)
        large_cap_count = len([t for t in hot_tokens if t.get('large_cap')])

        html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
            <title>Spot Analysis Report</title>
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&family=JetBrains+Mono:wght@700&display=swap" rel="stylesheet">
            <style>
                :root {{
                    --bg-dark: #151a1e;
                    --bg-card: #1e252a;
                    --accent-green: #10b981;
                    --text-main: #ffffff;
                    --text-dim: #848e9c;
                    --border: #2b3139;
                }}
                body {{ 
                    font-family: 'Inter', sans-serif; 
                    margin: 0; 
                    background-color: var(--bg-dark); 
                    color: var(--text-main); 
                    -webkit-font-smoothing: antialiased;
                }}
                .header {{ 
                    background: linear-gradient(180deg, rgba(16, 185, 129, 0.1) 0%, transparent 100%);
                    padding: 30px 15px; 
                    text-align: center; 
                    border-bottom: 1px solid var(--border);
                }}
                .header h1 {{ margin: 0; font-size: 1.3rem; color: var(--accent-green); font-weight: 800; text-transform: uppercase; }}
                .header p {{ margin: 8px 0 0; font-size: 0.8rem; color: var(--text-dim); font-family: 'JetBrains Mono', monospace; }}
                
                .summary {{ 
                    background: var(--bg-card); 
                    padding: 15px; 
                    margin: 15px; 
                    border-radius: 12px; 
                    border: 1px solid var(--border);
                    font-size: 0.85rem;
                    line-height: 1.5;
                    text-align: center;
                }}
                .summary b {{ color: var(--accent-green); }}

                .table-container {{ 
                    margin: 0 10px; 
                    border-radius: 12px; 
                    border: 1px solid var(--border); 
                    background: var(--bg-card);
                    overflow-x: auto;
                    -webkit-overflow-scrolling: touch;
                }}
                table {{ width: 100%; border-collapse: collapse; table-layout: fixed; }}
                
                th {{ 
                    background: rgba(0, 0, 0, 0.2); 
                    color: var(--text-dim); 
                    padding: 12px 5px; 
                    text-align: left; 
                    font-size: 0.65rem; 
                    text-transform: uppercase; 
                    letter-spacing: 1px;
                    border-bottom: 1px solid var(--border);
                    white-space: nowrap;
                }}
                td {{ 
                    padding: 0; 
                    border-bottom: 1px solid #2b3139; 
                    height: 52px; 
                    vertical-align: middle; 
                    font-size: 0.85rem; 
                    white-space: nowrap;
                }}
                tr:last-child td {{ border-bottom: none; }}
                
                tr.large-cap {{ background: rgba(16, 185, 129, 0.03); }}
                tr.large-cap td:first-child {{ border-left: 3px solid var(--accent-green); }}

                .ticker-btn {{
                    display: block; 
                    width: 100%; 
                    height: 100%; 
                    padding: 14px 8px;
                    color: var(--accent-green); 
                    text-decoration: none; 
                    font-weight: 800; 
                    box-sizing: border-box; 
                    touch-action: manipulation;
                    -webkit-tap-highlight-color: rgba(16, 185, 129, 0.15);
                    transition: background 0.15s;
                }}
                .ticker-btn:active {{ 
                    background: rgba(16, 185, 129, 0.1); 
                }}

                @media (max-width: 480px) {{
                    td {{ font-size: 0.72rem; }}
                    th {{ font-size: 0.58rem; padding: 10px 4px; }}
                    .ticker-btn {{ padding: 10px 4px !important; }}
                    .mono {{ font-size: 0.68rem; }}
                    .header h1 {{ font-size: 1.1rem; }}
                    .summary {{ font-size: 0.75rem; margin: 10px; }}
                    .hide-on-mobile {{
                        display: none;
                    }}
                }}
                
                .nav-box {{ text-align: center; margin: 30px 0; }}
                .back-btn {{
                    display: inline-flex;
                    align-items: center;
                    padding: 12px 24px;
                    background: transparent;
                    border: 1px solid var(--text-dim);
                    color: var(--text-dim);
                    border-radius: 8px;
                    text-decoration: none;
                    font-weight: 800;
                    font-size: 0.85rem;
                    touch-action: manipulation;
                    -webkit-tap-highlight-color: rgba(255,255,255,0.1);
                    transition: all 0.15s;
                }}
                .back-btn:active {{
                    background: rgba(255,255,255,0.08);
                    border-color: #fff;
                    color: #fff;
                }}
                /* Hover only for devices with a mouse */
                @media (hover: hover) {{
                    .back-btn:hover {{
                        border-color: #fff;
                        color: #fff;
                        background: rgba(255,255,255,0.05);
                    }}
                }}

                .mono {{ font-family: 'JetBrains Mono', monospace; }}
                .vol-high {{ color: #ef4444; font-weight: bold; }}
                .pcp-pos {{ color: var(--accent-green); font-weight: bold; }}
                .pcp-neg {{ color: #ef4444; font-weight: bold; }}
                .pcp-flat {{ color: var(--text-dim); }}
                
                .footer {{ 
                    text-align: center; 
                    padding: 30px 20px; 
                    font-size: 0.75rem; 
                    color: var(--text-dim); 
                    border-top: 1px solid var(--border);
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Spot Volume Analysis Report</h1>
                <p>{current_time}</p>
            </div>
            
            <div class="summary">
                Found <b>{len(hot_tokens)}</b> tokens. | <b>{large_cap_count}</b> Largecaps tokens found | Highest VTMR <b>{max_flip:.1f}x</b>.
            </div>

            <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th style="width: 10%; text-align:center;">#</th>
                        <th style="width: 22%;">Ticker</th>
                        <th style="width: 15%;" class="hide-on-mobile">24H %</th>
                        <th style="width: 19%;">MarketCap</th>
                        <th style="width: 18%;">Volume</th>
                        <th style="width: 16%;">VTMR</th>
                    </tr>
                </thead>
                <tbody>
        """

        for i, token in enumerate(hot_tokens):
            is_lc = token.get('large_cap', False)
            row_class = "large-cap" if is_lc else ""
            vtmr = token.get('flipping_multiple', 0)
            vol_class = "vol-high" if vtmr >= 2 else ""
            sym = html.escape(str(token.get('symbol', '???')), quote=True)

            pcp = token.get('pcp')
            if pcp is None:
                pcp_html = '<span class="pcp-flat">n/a</span>'
            else:
                pcp_class = "pcp-pos" if pcp > 0 else ("pcp-neg" if pcp < 0 else "pcp-flat")
                pcp_sign = "+" if pcp > 0 else ""
                pcp_html = f'<span class="{pcp_class}">{pcp_sign}{pcp:.2f}%</span>'

            # Link to deep-diver with ticker param
            link = f'<a href="/deep-diver?ticker={sym}" class="ticker-btn">{sym}</a>'

            html_content += f"""
                <tr class="{row_class}">
                    <td style="text-align:center; color:var(--text-dim);" class="mono">#{i+1}</td>
                    <td>{link}</td>
                    <td style="padding-left:5px;" class="mono hide-on-mobile">{pcp_html}</td>
                    <td style="padding-left:5px;" class="mono">${short_num(token.get('marketcap', 0))}</td>
                    <td style="padding-left:5px;" class="mono">${short_num(token.get('volume', 0))}</td>
                    <td class="mono {vol_class}" style="padding-left:5px;">{vtmr:.2f}x</td>
                </tr>
            """

        html_content += f"""
                </tbody>
            </table>
            </div>

            <div class="nav-box">
                <a href="/reports-list" class="back-btn">← BACK TO REPORTS LIST</a>
            </div>

            <div class="footer">
                Report by QuantVat using SpotVolTracker v3.0
            </div>
        </body>
        </html>
        """

        with open(html_file, "w", encoding="utf-8") as f:
            f.write(html_content)
        return html_file

    async def _fetch_cg_page(session: aiohttp.ClientSession, page: int, headers: dict) -> Tuple[int | None, list]:
        params = {"vs_currency": "usd", "order": "market_cap_desc", "per_page": 250, "page": page}
        try:
            async with session.get("https://api.coingecko.com/api/v3/coins/markets", params=params, headers=headers) as r:
                if r.status == 200:
                    return r.status, await r.json()
                return r.status, []
        except Exception:
            return None, []

    async def fetch_coingecko(session: aiohttp.ClientSession) -> List[Dict[str, Any]]:
        use_key = bool(COINGECKO_API_KEY and COINGECKO_API_KEY != "CONFIG_REQUIRED_CG")
        headers = STEALTH_HEADERS.copy()
        if use_key:
            headers["x-cg-demo-api-key"] = COINGECKO_API_KEY

        # All 4 pages concurrently
        results = list(await asyncio.gather(*[_fetch_cg_page(session, p, headers) for p in range(1, 5)]))
        # Only retry
        retry_pages = [p for p, (status, _) in zip(range(1, 5), results) if use_key and status in (401, 403, 429)]
        if retry_pages:
            retry_results = await asyncio.gather(*[_fetch_cg_page(session, p, STEALTH_HEADERS) for p in retry_pages])
            for p, res in zip(retry_pages, retry_results):
                results[p - 1] = res

        tokens = []
        for _, page_data in results:
            for t in page_data:
                symbol = (t.get("symbol") or "").upper()
                if symbol in STABLECOINS: continue
                vol, mc = float(t.get("total_volume") or 0), float(t.get("market_cap") or 0)
                pcp_raw = t.get("price_change_percentage_24h")
                pcp = float(pcp_raw) if pcp_raw is not None else None
                price_raw = t.get("current_price")
                price = float(price_raw) if price_raw is not None else None
                if mc > 0 and (vol / mc) >= FETCH_THRESHOLD:
                    tokens.append({"symbol": symbol, "marketcap": mc, "volume": vol, "pcp": pcp, "price": price, "source": "CG"})
        print(f"    CoinGecko returned: {len(tokens)} tokens")
        return tokens

    async def fetch_coinmarketcap(session: aiohttp.ClientSession) -> List[Dict[str, Any]]:
        tokens = []
        if not CMC_API_KEY or CMC_API_KEY == "CONFIG_REQUIRED_CMC": return tokens
        headers = STEALTH_HEADERS.copy()
        headers["X-CMC_PRO_API_KEY"] = CMC_API_KEY
        try:
            async with session.get(
                "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest",
                headers=headers, params={"start": 1, "limit": 1000, "convert": "USD"}
            ) as r:
                if r.status != 200:
                    print("    CoinMarketCap returned: 0 tokens")
                    return tokens
                payload = await r.json()
            for t in payload.get("data", []):
                symbol = (t.get("symbol") or "").upper()
                if symbol in STABLECOINS: continue
                q = t.get("quote", {}).get("USD", {})
                vol, mc = float(q.get("volume_24h") or 0), float(q.get("market_cap") or 0)
                pcp_raw = q.get("percent_change_24h")
                pcp = float(pcp_raw) if pcp_raw is not None else None
                price_raw = q.get("price")
                price = float(price_raw) if price_raw is not None else None
                if mc > 0 and (vol / mc) >= FETCH_THRESHOLD:
                    tokens.append({"symbol": symbol, "marketcap": mc, "volume": vol, "pcp": pcp, "price": price, "source": "CMC"})
        except Exception:
            pass
        print(f"    CoinMarketCap returned: {len(tokens)} tokens")
        return tokens

    async def fetch_livecoinwatch(session: aiohttp.ClientSession) -> List[Dict[str, Any]]:
        tokens = []
        if not LIVECOINWATCH_API_KEY or LIVECOINWATCH_API_KEY == "CONFIG_REQUIRED_LCW": return tokens
        headers = STEALTH_HEADERS.copy()
        headers.update({"content-type": "application/json", "x-api-key": LIVECOINWATCH_API_KEY})
        payload = {"currency": "USD", "sort": "rank", "order": "ascending", "offset": 0, "limit": 1000, "meta": True}
        try:
            async with session.post("https://api.livecoinwatch.com/coins/list", json=payload, headers=headers) as r:
                if r.status != 200:
                    print("    LiveCoinWatch returned: 0 tokens")
                    return tokens
                data = await r.json()
            for t in data:
                symbol = (t.get("code") or "").upper()
                if symbol in STABLECOINS: continue
                vol, mc = float(t.get("volume") or 0), float(t.get("cap") or 0)
                delta_day = t.get("delta", {}).get("day")
                pcp = (float(delta_day) - 1) * 100 if delta_day is not None else None
                price_raw = t.get("rate")
                price = float(price_raw) if price_raw is not None else None
                if mc > 0 and (vol / mc) >= FETCH_THRESHOLD:
                    tokens.append({"symbol": symbol, "marketcap": mc, "volume": vol, "pcp": pcp, "price": price, "source": "LCW"})
        except Exception:
            pass
        print(f"    LiveCoinWatch returned: {len(tokens)} tokens")
        return tokens

    async def _fetch_all_sources_async() -> Tuple[List[Dict[str, Any]], int]:
        print("    Volume-driven scan (filters applied)...")
        results = []
        total_sources = 3
        connector = aiohttp.TCPConnector(limit=10)
        async with aiohttp.ClientSession(connector=connector, timeout=REQUEST_TIMEOUT) as session:
            tasks = [
                asyncio.create_task(fetch_coingecko(session)),
                asyncio.create_task(fetch_coinmarketcap(session)),
                asyncio.create_task(fetch_livecoinwatch(session)),
            ]
            for i, coro in enumerate(asyncio.as_completed(tasks), start=1):
                try:
                    res = await coro
                    if res:
                        results.extend(res)
                except Exception:
                    continue
                finally:
                    pct = 10 + int((i / total_sources) * 40)
                    update_progress(user_id, pct, f"Fetched {i} of {total_sources} sources...", "active")
        print(f"    Total raw results: {len(results)}")
        return results, len(results)

    def fetch_all_sources() -> Tuple[List[Dict[str, Any]], int]:
        return asyncio.run(_fetch_all_sources_async())

    # --- Processing Logic ---
    t0 = time.perf_counter()
    raw_tokens, _ = fetch_all_sources()
    print(f"    Total time taken: {time.perf_counter() - t0:.2f}s")
    update_progress(user_id, 60, "Cross-referencing and verifying tokens...", "active")
    all_data = {}
    for t in raw_tokens:
        all_data.setdefault(t['symbol'], []).append(t)

    def is_price_close(p1: float, p2: float, tol: float = 0.01) -> bool:
        """
        Return True if two prices are within `tol` relative difference (default 1%).
        """
        if p1 is None or p2 is None or p1 <= 0 or p2 <= 0:
            return False
        return abs(p1 - p2) / max(p1, p2) <= tol

    # Tracks how often CG's 0% gets overridden vs confirmed, per run
    pcp_stats = {"cg_zero_seen": 0, "overridden": 0, "confirmed_zero": 0}

    DISAGREEMENT_THRESHOLD = 0.5  # percentage points; below this, treat as noise not disagreement

    def pick_best_pcp(tokens: List[Dict[str, Any]], reference_price: float | None) -> float | None:
        """
        Smart PCP selection with price consistency guard.
        """
        cg = next((t for t in tokens if t['source'] == 'CG'), None)
        cg_pcp = cg.get('pcp') if cg else None

        # 1. Non-zero CG value is trusted outright
        if cg_pcp is not None and cg_pcp != 0:
            return cg_pcp

        others = [
            t for t in tokens
            if t['source'] != 'CG'
            and t.get('pcp') is not None
            and is_price_close(t.get('price'), reference_price)
        ]

        if cg_pcp == 0:
            pcp_stats["cg_zero_seen"] += 1
            disagreeing = [t['pcp'] for t in others if abs(t['pcp']) > DISAGREEMENT_THRESHOLD]
            if disagreeing:
                pcp_stats["overridden"] += 1
                return disagreeing[0]
            pcp_stats["confirmed_zero"] += 1
            return 0.0

        # cg_pcp is None — CG had no data for this symbol at all
        if not others:
            return None
        non_zero = [t['pcp'] for t in others if t['pcp'] != 0]
        return non_zero[0] if non_zero else 0.0

    verified_tokens = []
    for sym, tokens in all_data.items():
        cg_data = next((t for t in tokens if t['source'] == 'CG'), None)

        if cg_data:
            # CoinGecko is authoritative for volume & marketcap
            volume, marketcap = cg_data['volume'], cg_data['marketcap']
            ratio = volume / marketcap
            is_large = marketcap > LC_THRESHOLD
            reference_price = cg_data.get('price')

            if (is_large and MIN_LC_VTMR <= ratio <= MAX_VTMR) or \
               (not is_large and MIN_VTMR <= ratio <= MAX_VTMR):
                verified_tokens.append({
                    "symbol": sym,
                    "marketcap": marketcap,
                    "volume": volume,
                    "flipping_multiple": ratio,
                    "source_count": len(tokens),
                    "large_cap": is_large,
                    "pcp": pick_best_pcp(tokens, reference_price=reference_price),
                })
        else:
            # Fallback: require ≥ 2 non-CG sources
            if len(tokens) >= 2:
                volume = sum(t['volume'] for t in tokens) / len(tokens)
                marketcap = sum(t['marketcap'] for t in tokens) / len(tokens)
                ratio = volume / marketcap
                is_large = any(t['marketcap'] > LC_THRESHOLD for t in tokens)

                prices = [t['price'] for t in tokens if t.get('price')]
                reference_price = sum(prices) / len(prices) if prices else None

                if (is_large and MIN_LC_VTMR <= ratio <= MAX_VTMR) or \
                   (not is_large and MIN_VTMR <= ratio <= MAX_VTMR):
                    verified_tokens.append({
                        "symbol": sym,
                        "marketcap": marketcap,
                        "volume": volume,
                        "flipping_multiple": ratio,
                        "source_count": len(tokens),
                        "large_cap": is_large,
                        "pcp": pick_best_pcp(tokens, reference_price=reference_price),
                    })

    hot_tokens = sorted(verified_tokens, key=lambda x: x["flipping_multiple"], reverse=True)
    update_progress(user_id, 90, "Compiling spot report...", "active")
    html_file = create_html_report(hot_tokens)
    set_pending_file(user_id, "spot", html_file)

    report_filename = html_file.name
    now_h = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"    Found {len(hot_tokens)} filtered tokens at {now_h}")
    print(f"    Report saved as: {report_filename}")
    print("     Spot analysis completed!")