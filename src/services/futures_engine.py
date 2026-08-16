import re
import unicodedata
import pandas as pd
from dataclasses import dataclass
from pathlib import Path
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
    oi_pct: Optional[float] = None
    funding_pct: Optional[float] = None


class PDFParser:
    """Handles extraction of tabular data from Coinalyze PDFs using regex. """

    FINANCIAL_PATTERN = re.compile(
        r'(\$?[+-]?[\d,\.]+[kKmMbBtT]?|[Nn]\/[Aa])\s+'
        r'(\$?[+-]?[\d,\.]+[kKmMbBtT]?|[Nn]\/[Aa])\s+'
        r'(?:([+\-]?[\d\.\,]+\%?|[\-\–\—]|[Nn]\/[Aa])\s+)?'
        r'(?:([+\-]?[\d\.\,]+\%?|[\-\–\—]|[Nn]\/[Aa])\s+)?'
        r'(\d*\.?\d+[kKmMbBtT]?)'
    )

    IGNORE_KEYWORDS = {
        'page', 'coinalyze', 'contract', 'filter', 'column',
        'mkt cap', 'vol 24h', 'vtmr', 'coins', 'all contracts', 'custom metrics', 'watchlists',
        'open interest - funding rate - liquidations'
    }

    _SUFFIX_MULT = {'k': 1e3, 'm': 1e6, 'b': 1e9, 't': 1e12}

    # CJK Radicals (U+2E80-2EFF) and CJK Radicals Supplement (U+2F00-2FDF)
    _TICKER_KEEP = r'\w\u2e80-\u2eff\u2f00-\u2fdf'

    @classmethod
    def _to_number(cls, s: str) -> float:
        s = s.strip()
        suffix = s[-1].lower() if s and s[-1].lower() in cls._SUFFIX_MULT else None
        if suffix:
            return float(s[:-1]) * cls._SUFFIX_MULT[suffix]
        return float(s)

    @staticmethod
    def _to_float(pct_str: Optional[str]) -> Optional[float]:
        if not pct_str:
            return None
        cleaned = pct_str.replace("%", "").strip()
        if cleaned in ("-", "–", "—", "") or cleaned.lower() == "n/a":
            return None
        try:
            return float(cleaned)
        except Exception:
            return None

    # --- Name/Ticker Extraction ---

    @staticmethod
    def _extract_name_ticker(line: str) -> Optional[Tuple[str, str]]:
        """Extract (name, ticker) when both sit on a single line (PC layout)."""
        line = line.strip()
        if not line:
            return None

        if ' ' in line:
            parts = line.rsplit(' ', 1)
            if len(parts) == 2:
                name, ticker = parts
                name = name.strip()
                ticker = ticker.strip()
                if name and ticker:
                    if ticker.isupper() or not ticker.isascii():
                        return (name, ticker)

        ascii_match = re.search(r'(.+?)([A-Z0-9]{1,10})$', line)
        if ascii_match:
            name, ticker = ascii_match.groups()
            if name and not name.isupper() and len(name) >= 2:
                return (name.strip(), ticker)

        cjk_match = re.search(
            r'(.+?)([\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af]{1,4})$',
            line
        )
        if cjk_match:
            name, ticker = cjk_match.groups()
            if name:
                return (name.strip(), ticker)

        return None

    @classmethod
    def _clean_ticker_strict(cls, text: Optional[str]) -> Optional[str]:
        """Validate that `text` is a standalone ticker occupying its own line."""
        if not text or not text.strip():
            return None
        text = text.strip()
        if ' ' in text:
            return None
        if text.isascii() and not text.isupper():
            return None
        cleaned = re.sub(rf'[^{cls._TICKER_KEEP}]', '', text)
        if 1 <= len(cleaned) <= 15:
            return cleaned
        return None

    @classmethod
    def _pair_lines(cls, raw_text_lines: List[str]) -> List[Tuple[str, str]]:
        """
        Pair name/ticker across both PC (single-line) and Android
        (stacked, possibly multi-line-name) layouts.
        """
        pairs: List[Tuple[str, str]] = []
        buffer: List[str] = []
        i = 0
        n = len(raw_text_lines)

        while i < n:
            line = raw_text_lines[i]
            next_line = raw_text_lines[i + 1] if i + 1 < n else None
            next_ticker = cls._clean_ticker_strict(next_line) if next_line else None

            if next_ticker:
                buffer.append(line)
                name = ' '.join(buffer).strip()
                pairs.append((name, next_ticker))
                buffer = []
                i += 2
                continue

            pair = cls._extract_name_ticker(line)
            if pair and not buffer:
                pairs.append(pair)
                i += 1
                continue

            buffer.append(line)
            i += 1

        return pairs

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

            # Preserve Unicode tickers (CJK, etc.) and CJK radical glyphs
            df['ticker'] = df['ticker'].apply(
                lambda x: re.sub(rf'[^{cls._TICKER_KEEP}]', '', str(x))
            )
            df['ticker'] = df['ticker'].apply(lambda x: unicodedata.normalize('NFKC', str(x)))
            df['name'] = df['name'].apply(lambda x: unicodedata.normalize('NFKC', str(x)))

            df = df[df['ticker'].str.len() >= 1]
            print(f"   Valid futures tokens: {len(df)}")
            return df
        except Exception as e:
            print(f"   PDF Error: {e}")
            return pd.DataFrame()

    @classmethod
    def extract_and_persist(cls, pdf_path: Path) -> Optional[Path]:
        df = cls.extract(pdf_path)
        if df.empty:
            return None
        csv_path = pdf_path.with_suffix(".csv")
        try:
            df.to_csv(csv_path, index=False)
        except Exception as e:
            print(f"   Could not parse futures CSV: {e}")
            return None
        print(f"   Futures data parsed: {csv_path.name}")
        return csv_path

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
                    cls._to_number(vtmr)
                    financials.append((mc, vol, vtmr, oi_str, fund_str))
                except Exception:
                    raw_text_lines.append(line)
            else:
                if not line.isdigit() and len(line) > 1:
                    raw_text_lines.append(line)

        token_pairs = cls._pair_lines(raw_text_lines)

        tokens: List[TokenData] = []
        limit = min(len(token_pairs), len(financials))

        for k in range(limit):
            name, ticker = token_pairs[k]
            mc, vol, vtmr, oi_pct_str, fund_pct_str = financials[k]

            tokens.append(TokenData(
                ticker=ticker,
                name=name,
                market_cap=mc,
                volume=vol,
                vtmr=cls._to_number(vtmr),
                oi_pct=cls._to_float(oi_pct_str),
                funding_pct=cls._to_float(fund_pct_str),
            ))
        return tokens