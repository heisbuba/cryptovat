import time
import datetime
import html
import threading
import asyncio
import aiohttp
from typing import Any

from src.state import get_user_temp_dir, update_progress, set_pending_file
from src.config import STABLECOINS
from src.services.utils import short_num, now_str

REQUEST_TIMEOUT = aiohttp.ClientTimeout(connect=5, total=20)


def evaluate_signal(vtmr: float, c24: float | None, c7: float | None) -> str:
    """Compute bias signal from volume-turnover ratio and price momentum."""
    c24 = c24 or 0.0
    c7 = c7 or 0.0
    if c24 < -5.0 and vtmr >= 0.5:
        return "CLIMAX"
    if c24 > 0.0 and c7 > 5.0 and vtmr >= 0.3:
        return "BREAKOUT"
    if -5.0 <= c7 <= 10.0 and vtmr >= 0.15:
        return "ACCUMULATING"
    return "NEUTRAL"


def spot_volume_tracker(user_keys: dict[str, Any], user_id: str | int) -> None:
    def safe_float(val: Any, default: float) -> float:
        try:
            if val is None or str(val).strip() == "":
                return default
            return float(val)
        except (ValueError, TypeError):
            return default

    MC_SUFFIX_MULT = {'k': 1e3, 'm': 1e6, 'b': 1e9, 't': 1e12}

    def parse_mc(val: Any, default: float) -> float:
        """Parses market-cap shorthand like '5m', '1.2b', '500k', '1t' into a raw float."""
        if val is None:
            return default
        s = str(val).strip().replace('$', '').replace(',', '')
        if s == "":
            return default
        suffix = s[-1].lower() if s and s[-1].lower() in MC_SUFFIX_MULT else None
        try:
            if suffix:
                return float(s[:-1]) * MC_SUFFIX_MULT[suffix]
            return float(s)
        except (ValueError, TypeError):
            return default

    print("    Starting fresh spot analysis...")
    threading.current_thread().name = f"user_{user_id}"
    update_progress(user_id, 10, "Starting spot market scan...", "active")

    COINGECKO_API_KEY = user_keys.get("COINGECKO_API_KEY", "CONFIG_REQUIRED_CG")
    settings = user_keys.get("engine_settings", {})
    MIN_VTMR = safe_float(settings.get('min_vtmr'), 0.5)
    MAX_VTMR = safe_float(settings.get('max_vtmr'), 199.0)
    MIN_LC_VTMR = safe_float(settings.get('min_largecap_vtmr'), 0.5)
    MIN_S_MC = parse_mc(settings.get('min_s_mc'), 0.0)
    MAX_S_MC = parse_mc(settings.get('max_s_mc'), float('inf'))
    LC_THRESHOLD = 1_000_000_000
    FETCH_THRESHOLD = min(MIN_VTMR, MIN_LC_VTMR)

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

    def create_html_report(hot_tokens: list[dict[str, Any]]) -> Any:
        date_prefix = datetime.datetime.now().strftime("%b-%d-%y")
        user_dir = get_user_temp_dir(user_id)
        html_file = user_dir / f"Spot_Analysis_{date_prefix}.html"
        current_time = now_str("%d-%m-%Y %H:%M:%S")

        max_flip = max((t.get('flipping_multiple', 0) for t in hot_tokens), default=0)
        large_cap_count = len([t for t in hot_tokens if t.get('large_cap')])

        rows_html = []
        for i, token in enumerate(hot_tokens):
            is_lc = token.get('large_cap', False)
            row_class = "large-cap" if is_lc else ""
            vtmr = token.get('flipping_multiple', 0)
            vol_class = "vol-high" if vtmr >= 2 else ""
            sym = html.escape(str(token.get('symbol', '???')), quote=True)
            coin_id = html.escape(token.get('coin_id', ''), quote=True)
            signal = token.get('signal', 'NEUTRAL')

            pcp = token.get('pcp')
            if pcp is None:
                pcp_html = '<span class="pcp-flat">n/a</span>'
            else:
                pcp_class = "pcp-pos" if pcp > 0 else ("pcp-neg" if pcp < 0 else "pcp-flat")
                pcp_sign = "+" if pcp > 0 else ""
                pcp_html = f'<span class="{pcp_class}">{pcp_sign}{pcp:.2f}%</span>'

            data_attrs = {
                "coin-id": coin_id,
                "symbol": sym,
                "price": token.get('price', 0),
                "mcap": token.get('marketcap', 0),
                "vol24": token.get('volume', 0),
                "vtmr": vtmr,
                "c24": token.get('change_24h', 0),
                "c7": token.get('change_7d', 0),
                "c30": token.get('change_30d', 0),
                "c1y": token.get('change_1y', 'N/A'),
                "explainer": html.escape(token.get('explainer', ''), quote=True),
            }
            data_str = " ".join(f'data-{k}="{v}"' for k, v in data_attrs.items())

            rows_html.append(f"""
                <tr class="{row_class}" {data_str}>
                    <td style="text-align:center; color:var(--text-dim);" class="mono">#{i+1}</td>
                     <td><a href="/deep-diver?ticker={sym}" class="ticker-btn">{sym}</a></td>
                    <td style="padding-left:5px;" class="mono hide-on-mobile">{pcp_html}</td>
                    <td style="padding-left:5px;" class="mono">${short_num(token.get('marketcap', 0))}</td>
                    <td style="padding-left:5px;" class="mono">${short_num(token.get('volume', 0))}</td>
                    <td class="mono {vol_class}" style="padding-left:5px;">{vtmr:.2f}x</td>
                    <td style="text-align:center;">
                        <button class="action-btn analyze-btn" onclick="handleAction(event, this)">Summary</button>
                    </td>
                </tr>
            """)

        table_rows = "\n".join(rows_html)

        # HTML template
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
                    --accent-blue: #3b82f6;
                    --text-main: #ffffff;
                    --text-dim: #848e9c;
                    --border: #2b3139;
                    --danger: #ef4444;
                    --signal-climax: #f59e0b;
                    --signal-breakout: #10b981;
                    --signal-accumulating: #3b82f6;
                    --signal-neutral: #6b7280;
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
                table {{ width: 100%; border-collapse: collapse; table-layout: fixed; min-width: 800px; }}
                
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
                    .hide-on-mobile {{ display: none; }}
                                    }}

                .action-btn {{
                    border: none;
                    padding: 6px 12px;
                    border-radius: 6px;
                    font-weight: 800;
                    font-size: 0.75rem;
                    cursor: pointer;
                    transition: all 0.2s ease;
                    background: var(--accent-blue);
                    color: #ffffff;
                }}
                .action-btn:disabled {{
                    background: #4b5563;
                    opacity: 0.7;
                    cursor: wait;
                }}
                .action-btn.view-btn {{
                    background: var(--accent-green);
                    color: #0b0f11;
                }}

                .modal-overlay {{
                    position: fixed;
                    top: 0; left: 0; width: 100%; height: 100%;
                    background: rgba(0, 0, 0, 0.75);
                    display: none;
                    align-items: center;
                    justify-content: center;
                    z-index: 1000;
                    backdrop-filter: blur(4px);
                }}
                .modal-overlay.active {{ display: flex; }}
                .modal-card {{
                    background: var(--bg-card);
                    border: 1px solid var(--border);
                    border-radius: 12px;
                    width: 90%;
                    max-width: 600px;
                    padding: 20px;
                    box-shadow: 0 10px 25px rgba(0, 0, 0, 0.5);
                    max-height: 90vh;
                    overflow-y: auto;
                }}
                .modal-header {{
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    border-bottom: 1px solid var(--border);
                    padding-bottom: 10px;
                    margin-bottom: 15px;
                    gap: 10px;
                }}
                .modal-header-left {{
                    display: flex;
                    align-items: center;
                    gap: 10px;
                    min-width: 0;
                }}
                .modal-title {{ font-size: 1.1rem; font-weight: 800; color: var(--accent-green); }}
                .chart-link {{
                    flex-shrink: 0;
                    color: var(--accent-blue);
                    text-decoration: none;
                    font-size: 0.7rem;
                    font-weight: 800;
                    border: 1px solid var(--accent-blue);
                    padding: 4px 10px;
                    border-radius: 6px;
                    touch-action: manipulation;
                    -webkit-tap-highlight-color: rgba(59, 130, 246, 0.15);
                }}
                .chart-link:active {{ background: rgba(59, 130, 246, 0.15); }}
                @media (hover: hover) {{
                    .chart-link:hover {{ background: rgba(59, 130, 246, 0.1); }}
                }}
                .modal-close {{
                    background: none; border: none; color: var(--text-dim);
                    font-size: 1.5rem; cursor: pointer; line-height: 1;
                }}
                .modal-body {{
                    font-size: 0.85rem;
                    line-height: 1.6;
                    color: var(--text-main);
                    white-space: pre-line;
                    font-family: 'Inter', sans-serif;
                }}

                .mono {{ font-family: 'JetBrains Mono', monospace; }}
                .vol-high {{ color: #ef4444; font-weight: bold; }}
                .pcp-pos {{ color: var(--accent-green); font-weight: bold; }}
                .pcp-neg {{ color: #ef4444; font-weight: bold; }}
                .pcp-flat {{ color: var(--text-dim); }}

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
                @media (hover: hover) {{
                    .back-btn:hover {{
                        border-color: #fff;
                        color: #fff;
                        background: rgba(255,255,255,0.05);
                    }}
                }}

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
                <h1>Spot Volume-driven Analysis</h1>
                <p>{current_time}</p>
            </div>
            
            <div class="summary">
                Found <b>{len(hot_tokens)}</b> tokens. | <b>{large_cap_count}</b> Largecaps tokens found | Highest VTMR <b>{max_flip:.1f}x</b>.
            </div>

            <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th style="width: 6%; text-align:center;">#</th>
                        <th style="width: 16%;">Ticker</th>
                        <th style="width: 12%;" class="hide-on-mobile">24H %</th>
                        <th style="width: 16%;">MarketCap</th>
                        <th style="width: 16%;">Volume</th>
                        <th style="width: 14%;">VTMR</th>
                        <th style="width: 16%;">Summary</th>
                    </tr>
                </thead>
                <tbody>
                    {table_rows}
                </tbody>
            </table>
            </div>

            <div class="modal-overlay" id="modalOverlay">
                <div class="modal-card">
                    <div class="modal-header">
                        <div class="modal-header-left">
                            <div class="modal-title" id="modalTitle">Analysis Breakdown</div>
                            <a class="chart-link" id="modalChartLink" href="#" target="_blank" rel="noopener">View Chart ↗</a>
                        </div>
                        <button class="modal-close" id="modalClose">&times;</button>
                    </div>
                    <div class="modal-body" id="modalBody"></div>
                </div>
            </div>

            <div class="nav-box">
                <a href="/reports-list" class="back-btn">← BACK TO REPORTS LIST</a>
            </div>

            <div class="footer">
                Report by SpotVolTracker v3.5
            </div>

                        <script>
                const overlay = document.getElementById('modalOverlay');
                const modalTitle = document.getElementById('modalTitle');
                const modalBody = document.getElementById('modalBody');
                const modalClose = document.getElementById('modalClose');
                const modalChartLink = document.getElementById('modalChartLink');

                const closeModal = () => overlay.classList.remove('active');
                modalClose.addEventListener('click', closeModal);
                overlay.addEventListener('click', (e) => {{ if (e.target === overlay) closeModal(); }});
                document.addEventListener('keydown', (e) => {{ if (e.key === 'Escape') closeModal(); }});

                function shortNum(num) {{
                    if (num === null || isNaN(num)) return "N/A";
                    if (num >= 1e9) return "$" + (num / 1e9).toFixed(2) + "B";
                    if (num >= 1e6) return "$" + (num / 1e6).toFixed(2) + "M";
                    if (num >= 1e3) return "$" + (num / 1e3).toFixed(2) + "K";
                    return "$" + num.toFixed(2);
                }}

                function handleAction(event, btn) {{
                    event.stopPropagation();
                    const tr = btn.closest('tr');
                    const explainer = tr.getAttribute('data-explainer');
                    const symbol = tr.getAttribute('data-symbol');

                    if (!explainer) {{
                        alert('Analysis data not available for this token.');
                        return;
                    }}

                    modalTitle.textContent = symbol + ' — Quick Breakdown';
                    modalBody.textContent = explainer;
                    modalChartLink.href = `https://www.tradingview.com/chart/?symbol=${{symbol}}USDT`;
                    overlay.classList.add('active');
                }}
            </script>
        </body>
        </html>
        """

        with open(html_file, "w", encoding="utf-8") as f:
            f.write(html_content)
        return html_file

    # ------------------------------------------------------------------
    # Async data fetching 
    # ------------------------------------------------------------------
    async def _fetch_cg_page(session: aiohttp.ClientSession, page: int, headers: dict) -> tuple[int | None, list]:
        params = {
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": 250,
            "page": page,
            "price_change_percentage": "24h,7d,30d,1y",
        }
        try:
            async with session.get("https://api.coingecko.com/api/v3/coins/markets", params=params, headers=headers) as resp:
                if resp.status == 200:
                    return resp.status, await resp.json()
                return resp.status, []
        except Exception:
            return None, []

    async def fetch_coingecko(session: aiohttp.ClientSession) -> list[dict[str, Any]]:
        use_key = bool(COINGECKO_API_KEY and COINGECKO_API_KEY != "CONFIG_REQUIRED_CG")
        headers = STEALTH_HEADERS.copy()
        if use_key:
            headers["x-cg-demo-api-key"] = COINGECKO_API_KEY

        results = list(await asyncio.gather(*[_fetch_cg_page(session, p, headers) for p in range(1, 7)]))
        
        retry_pages = [p for p, (status, _) in zip(range(1, 7), results) if use_key and status in (401, 403, 429)]
        if retry_pages:
            retry_results = await asyncio.gather(*[_fetch_cg_page(session, p, STEALTH_HEADERS) for p in retry_pages])
            for p, res in zip(retry_pages, retry_results):
                results[p - 1] = res

        tokens = []
        for _, page_data in results:
            for t in page_data:
                symbol = (t.get("symbol") or "").upper()
                if symbol in STABLECOINS:
                    continue
                vol = safe_float(t.get("total_volume"), 0.0)
                mc = safe_float(t.get("market_cap"), 0.0)
                if mc <= 0:
                    continue
                ratio = vol / mc
                if ratio < FETCH_THRESHOLD:
                    continue

                coin_id = t.get("id", "")
                price = safe_float(t.get("current_price"), None)
                pcp = t.get("price_change_percentage_24h")
                change_24h = safe_float(pcp, None)
                change_7d = safe_float(t.get("price_change_percentage_7d_in_currency"), None)
                change_30d = safe_float(t.get("price_change_percentage_30d_in_currency"), None)
                change_1y = safe_float(t.get("price_change_percentage_1y_in_currency"), None)

                tokens.append({
                    "coin_id": coin_id,
                    "symbol": symbol,
                    "marketcap": mc,
                    "volume": vol,
                    "price": price,
                    "pcp": change_24h,
                    "change_24h": change_24h,
                    "change_7d": change_7d,
                    "change_30d": change_30d,
                    "change_1y": change_1y,
                    "signal": "NEUTRAL",   # will be recomputed
                })
        print(f"    CoinGecko returned: {len(tokens)} tokens")
        return tokens

    async def _fetch_all_sources_async() -> list[dict[str, Any]]:
        print("    Volume-driven scan (filters applied)...")
        connector = aiohttp.TCPConnector(limit=10)
        async with aiohttp.ClientSession(connector=connector, timeout=REQUEST_TIMEOUT) as session:
            cg_tokens = await fetch_coingecko(session)
            update_progress(user_id, 50, "Data fetched, processing...", "active")
            return cg_tokens

    def fetch_all_sources() -> list[dict[str, Any]]:
        return asyncio.run(_fetch_all_sources_async())

    t0 = time.perf_counter()
    cg_tokens = fetch_all_sources()
    print(f"    Total time taken: {time.perf_counter() - t0:.2f}s")
    update_progress(user_id, 60, "Cross-referencing and verifying tokens...", "active")

    def evaluate_signal(vtmr: float, c24: float | None, c7: float | None) -> str:
        c24 = c24 or 0.0
        c7 = c7 or 0.0
        if c24 < -5.0 and vtmr >= 0.5:
            return "CLIMAX"
        if c24 > 0.0 and c7 > 5.0 and vtmr >= 0.3:
            return "BREAKOUT"
        if -5.0 <= c7 <= 10.0 and vtmr >= 0.15:
            return "ACCUMULATING"
        return "NEUTRAL"

    verified_tokens = []
    for t in cg_tokens:
        ratio = t['volume'] / t['marketcap']
        is_large = t['marketcap'] > LC_THRESHOLD
        mc_ok = MIN_S_MC <= t['marketcap'] <= MAX_S_MC
        vtmr_ok = (is_large and MIN_LC_VTMR <= ratio <= MAX_VTMR) or \
                  (not is_large and MIN_VTMR <= ratio <= MAX_VTMR)
        if vtmr_ok and mc_ok:
            signal = evaluate_signal(ratio, t.get('change_24h'), t.get('change_7d'))

            # Cap classification
            mc = t['marketcap']
            if mc >= 1_000_000_000:
                cap_label = "large cap"
            elif mc >= 100_000_000:
                cap_label = "small cap"
            else:
                cap_label = "micro cap"

            # Build inline explainer (no backend API call needed)
            c24 = t.get('change_24h') or 0.0
            vtpc = (t['volume'] / abs(c24)) if c24 else 0.0

            def _fmt_pct(v):
                if v is None or not isinstance(v, (int, float)):
                    return 'N/A'
                return f"+{v:.2f}%" if v > 0 else f"{v:.2f}%"

            c24_s = _fmt_pct(t.get('change_24h'))
            c7_s  = _fmt_pct(t.get('change_7d'))
            c30_s = _fmt_pct(t.get('change_30d'))
            c1y_s = _fmt_pct(t.get('change_1y'))

            if "ACCUMULATING" in signal:
                ctx = ("Is the token being accumulated before significant move? "
                       "Price is consolidation-bound while baseline daily volume shows a notable swell. "
                       "The chart and underlying catalyst needs to be researched. But click on ticker to do deep dive on it.")
            elif "BREAKOUT" in signal:
                ctx = ("A momentum to ride? Price expansion is accompanied by heavy volume acceleration. "
                       "The chart and underlying catalyst needs to be researched. But click on ticker to do deep dive on it.")
            elif "CLIMAX" in signal:
                ctx = ("Back from dead or potential exhaustion? Massive volume spike coincides with "
                       "sharp downward price action. The chart and underlying catalyst needs to be researched. But click on ticker to do deep dive on it.")
            else:
                ctx = ("Is the token moving? Back from dead, being accumulated before significant move "
                       "or a momentum to ride? The chart and underlying catalyst needs to be researched. But click on ticker to do deep dive on it.")

            explainer = (
                f"{t['symbol']} Price is: ${t['price']:.6g}, and Marketcap is: {short_num(t['marketcap'])}. "
                f"And our data-backed bias is: {signal}.\n\n"
                f"Token's PCP data: 24h is {c24_s}, 7d is {c7_s}, 30d is {c30_s}, and 1y is {c1y_s}.\n\n"
                f"Today's volume is {short_num(t['volume'])} and VTMR is {ratio:.3f}x, "
                f"and VTPC for today's each 1% move is {short_num(vtpc)}.\n\n"
                f"Question: {ctx}"
            )

            verified_tokens.append({
                "coin_id": t['coin_id'],
                "symbol": t['symbol'],
                "marketcap": t['marketcap'],
                "volume": t['volume'],
                "price": t['price'],
                "flipping_multiple": ratio,
                "large_cap": is_large,
                "pcp": t.get('pcp'),
                "change_24h": t.get('change_24h'),
                "change_7d": t.get('change_7d'),
                "change_30d": t.get('change_30d'),
                "change_1y": t.get('change_1y'),
                "signal": signal,
                "explainer": explainer,
            })

    hot_tokens = sorted(verified_tokens, key=lambda x: x["flipping_multiple"], reverse=True)
    update_progress(user_id, 90, "Compiling spot report...", "active")

    html_file = create_html_report(hot_tokens)
    set_pending_file(user_id, "spot", html_file)

    report_filename = html_file.name
    now_h = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"    Found {len(hot_tokens)} filtered tokens at {now_h}")
    print(f"    Report saved as: {report_filename}")
    print("    Spot analysis completed!")