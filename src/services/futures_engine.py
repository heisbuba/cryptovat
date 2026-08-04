import re
import pandas as pd
from dataclasses import dataclass
from typing import List, Optional, Tuple

try:
    import pypdf
except Exception:
    pypdf = None

@dataclass
class TokenData:
    ticker: str
    name: str
    market_cap: str
    volume: str
    vtmr: float
    funding: str = "-"
    oiss: str = "-"

class PDFParser:
    """Handles extraction of tabular data from Coinalyze PDFs using regex."""
    
    FINANCIAL_PATTERN = re.compile(
        r'(\$?[+-]?[\d,\.]+[kKmMbB]?|[Nn]\/[Aa])\s+'
        r'(\$?[+-]?[\d,\.]+[kKmMbB]?|[Nn]\/[Aa])\s+'
        r'(?:([+\-]?[\d\.\,]+\%?|[\-\–\—]|[Nn]\/[Aa])\s+)?'
        r'(?:([+\-]?[\d\.\,]+\%?|[\-\–\—]|[Nn]\/[Aa])\s+)?'
        r'(\d*\.?\d+)'
    )

    IGNORE_KEYWORDS = {
        'page', 'coinalyze', 'contract', 'filter', 'column',
        'mkt cap', 'vol 24h', 'vtmr', 'coins', 'all contracts', 'custom metrics', 'watchlists',
        'open interest - funding rate - liquidations'
    }

    # --- Signal Helpers  ---

    @staticmethod
    def _oi_score_and_signal(oi_change: float) -> Tuple[int, str]:
        if oi_change > 0.20: return 5, "Strong"
        if oi_change > 0.10: return 4, "Bullish"
        if oi_change > 0.00: return 3, "Build-Up"
        if oi_change > -0.10: return 2, "Weakening"
        if oi_change > -0.20: return 1, "Exiting"
        return 0, "Exiting"

    @staticmethod
    def _funding_score_and_signal(funding_val: float) -> Tuple[str, str]:
        if funding_val >= 0.05: return "Greed", "oi-strong"
        if funding_val > 0.00: return "Bullish", "oi-strong"
        if funding_val <= -0.05: return "Extreme Fear", "oi-weak"
        if funding_val < 0.00: return "Bearish", "oi-weak"
        return "Neutral", ""

    @classmethod
    def make_oiss(cls, oi_percent_str: str) -> str:
        if not oi_percent_str: return "-"
        val = oi_percent_str.replace("%", "").strip()
        try:
            oi_change = float(val) / 100
            score, signal = cls._oi_score_and_signal(oi_change)
            
            if oi_change > 0: css_class = "oi-strong"
            elif oi_change < 0: css_class = "oi-weak"
            else: css_class = ""

            sign = "+" if oi_change > 0 else ""
            if css_class:
                return f'<span class="{css_class}">{sign}{oi_change*100:.0f}%</span> {signal}'
            return f"{sign}{oi_change*100:.0f}% {signal}"
        except Exception:
            return "-"

    @classmethod
    def make_funding_signal(cls, funding_str: str) -> str:
        if not funding_str or funding_str in ['-', 'N/A']: return "-"
        try:
            val = float(funding_str.replace('%', '').strip())
            signal_word, css_class = cls._funding_score_and_signal(val)
            
            if css_class:
                return f'<span class="{css_class}">{val}%</span> <span style="font-size:0.8em; color:#7f8c8d;">{signal_word}</span>'
            return f'{val}% {signal_word}'
        except Exception:
            return funding_str

    # --- Core Extraction Logic ---

    @classmethod
    def extract(cls, path) -> pd.DataFrame:
        print(f"   Parsing Futures PDF: {path.name}")
        if pypdf is None:
            print("   pypdf not available - PDF parsing disabled.")
            return pd.DataFrame()
        data: List[TokenData] = []
        try:
            reader = pypdf.PdfReader(path)
            for page in reader.pages:
                raw = page.extract_text() or ""
                lines = [ln.strip() for ln in raw.split("\n") if ln.strip()]
                page_data = cls._parse_page_smart(lines)
                data.extend(page_data)
            print(f"   Extracted {len(data)} futures tokens")
            if not data:
                return pd.DataFrame()
            df = pd.DataFrame([vars(t) for t in data])
            df['ticker'] = df['ticker'].apply(lambda x: re.sub(r'[^A-Z0-9]', '', str(x).upper()))
            df = df[df['ticker'].str.len() >= 1]
            print(f"   Valid futures tokens: {len(df)}")
            return df
        except Exception as e:
            print(f"   PDF Error: {e}")
            return pd.DataFrame()

    @classmethod
    def _parse_page_smart(cls, lines: List[str]) -> List[TokenData]:
        financials = []
        raw_text_lines = []
        
        for line in lines:
            if any(k in line.lower() for k in cls.IGNORE_KEYWORDS):
                continue
            
            fin_match = cls.FINANCIAL_PATTERN.search(line)
            if fin_match:
                groups = fin_match.groups()
                mc = groups[0].replace('$', '').replace(',', '')
                vol = groups[1].replace('$', '').replace(',', '')
                oi_str = groups[2]
                fund_str = groups[3]
                vtmr = groups[4]
                try:
                    float(vtmr)
                    financials.append((mc, vol, vtmr, oi_str, fund_str))
                except:
                    raw_text_lines.append(line)
            else:
                if not line.isdigit() and len(line) > 1:
                    raw_text_lines.append(line)
        
        token_pairs = []
        i = 0
        while i < len(raw_text_lines):
            line = raw_text_lines[i]
            clean_current = cls._clean_ticker_strict(line)
            
            if clean_current:
                if i + 1 < len(raw_text_lines):
                    next_line = raw_text_lines[i + 1]
                    clean_next = cls._clean_ticker_strict(next_line)
                    if clean_next:
                        token_pairs.append((line, clean_next))
                        i += 2
                        continue
            
            same_line_split = line.rsplit(' ', 1)
            if len(same_line_split) == 2:
                name_part, ticker_part = same_line_split
                same_line_ticker = cls._clean_ticker_strict(ticker_part)
                if same_line_ticker and name_part.strip():
                    token_pairs.append((name_part, same_line_ticker))
                    i += 1
                    continue

            if i + 1 < len(raw_text_lines):
                name_candidate = raw_text_lines[i]
                ticker_candidate_raw = raw_text_lines[i + 1]
                ticker = cls._clean_ticker_strict(ticker_candidate_raw)
                if ticker:
                    token_pairs.append((name_candidate, ticker))
                    i += 2
                else:
                    i += 1
            else:
                i += 1
        
        tokens: List[TokenData] = []
        limit = min(len(token_pairs), len(financials))
        
        for k in range(limit):
            name, ticker = token_pairs[k]
            mc, vol, vtmr, oi_pct, fund_pct = financials[k]

            oiss_val = cls.make_oiss(oi_pct) if oi_pct and oi_pct not in ['-', 'N/A'] else "-"
            funding_val = cls.make_funding_signal(fund_pct)

            tokens.append(TokenData(
                ticker=ticker,
                name=name,
                market_cap=mc,
                volume=vol,
                vtmr=float(vtmr),
                funding=funding_val,
                oiss=oiss_val
            ))
        return tokens

    @staticmethod
    def _clean_ticker_strict(text: str) -> Optional[str]:
        if not text.isupper():
            return None
        if len(text) > 15: return None
        cleaned = re.sub(r'[^A-Z0-9]', '', text.upper())
        if 1 <= len(cleaned) <= 12: return cleaned
        return None
