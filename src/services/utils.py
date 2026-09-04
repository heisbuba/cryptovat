import os
import datetime
import requests
from pathlib import Path
from typing import Optional
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from weasyprint import HTML, CSS

# Import Global State
from ..state import get_user_temp_dir

# --- Shared Utilities ---

def create_session(retries: int = 3, backoff_factor: float = 0.5, status_forcelist=(429, 500, 502, 503, 504)) -> requests.Session:
    # Initialize requests session with exponential backoff and retry logic
    session = requests.Session()
    retry = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
        allowed_methods=frozenset(["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS"])
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

SESSION = create_session()

def short_num(n: float | int) -> str:
    # Scale large integers into abbreviated strings (K, M, B)
    try:
        n = float(n)
    except Exception:
        return str(n)
    if n >= 1_000_000_000:
        return f"{n/1_000_000_000:.2f}B"
    if n >= 1_000_000:
        return f"{n/1_000_000:.2f}M"
    if n >= 1_000:
        return f"{n/1_000:.2f}K"
    return str(round(n))

def now_str(fmt: str = "%d-%m-%Y %H:%M:%S") -> str:
    # Return current local system time in specified format
    return datetime.datetime.now().strftime(fmt)

# --- PDF Generation ---
_PDF_ONLY_CSS = CSS(string="""
    thead { display: table-header-group !important; }
    tr { break-inside: avoid !important; page-break-inside: avoid !important; }
""")

def _content_bottom_in(doc) -> float:
    """Return the actual bottom-most content position, in inches, from a
    rendered WeasyPrint Document
    """
    def _max_bottom(box):
        m = 0.0
        pos_y = getattr(box, "position_y", None)
        height = getattr(box, "height", None)
        if pos_y is not None and isinstance(height, (int, float)):
            m = max(m, pos_y + height)
        for child in (getattr(box, "children", None) or []):
            m = max(m, _max_bottom(child))
        return m

    page = doc.pages[0]
    root_box = page._page_box.children[0]
    bottom_px = _max_bottom(root_box)
    return bottom_px / 96.0 

def _measure_required_page_height_in(
    html_obj: HTML,
    width_in: float = 8.5,
    safety_in: float = 500.0,
    buffer_in: float = 0.3,
) -> float:
    """Determine the page height needed to fit all content on one page.
    """
    css = CSS(string=f"@page {{ size: {width_in}in {safety_in}in; margin: 0; }}")
    doc = html_obj.render(stylesheets=[css, _PDF_ONLY_CSS])
    try:
        bottom_in = _content_bottom_in(doc)
    except Exception as e:
        print(f"   ⚠️  Content-height measurement failed ({e}); using safety height.")
        return safety_in
    return min(bottom_in + buffer_in, safety_in)

def convert_html_to_pdf(html_content: str, user_id: str) -> Optional[Path]:
    # Render HTML string to PDF file
    print("   Converting to PDF...")
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    pdf_name = f"cross-market-analysis-{timestamp}.pdf"

    user_dir = get_user_temp_dir(user_id)
    pdf_path = user_dir / pdf_name

    try:
        html_obj = HTML(string=html_content)  # parse once, reuse for every render below
        required_height_in = _measure_required_page_height_in(html_obj)
        page_css = CSS(string=f"@page {{ size: 8.5in {required_height_in:.2f}in; margin: 0; }}")
        doc = html_obj.render(stylesheets=[page_css, _PDF_ONLY_CSS])

        attempts = 0
        while len(doc.pages) > 1 and attempts < 3:
            required_height_in = min(required_height_in * 1.5, 500.0)
            page_css = CSS(string=f"@page {{ size: 8.5in {required_height_in:.2f}in; margin: 0; }}")
            doc = html_obj.render(stylesheets=[page_css, _PDF_ONLY_CSS])
            attempts += 1

        doc.write_pdf(pdf_path)

        file_size = pdf_path.stat().st_size
        print(f"   PDF created: {pdf_name}")
        print(f"   Size: {file_size:,} bytes")
        return pdf_path

    except Exception as e:
        print(f"   ❌ WeasyPrint Error: {e}")
        return None

# --- File Cleanup ---

def cleanup_after_analysis(spot_file: Optional[Path], futures_file: Optional[Path], keep_spot: bool = False) -> int:
    files_cleaned = 0

    for file_path, file_type in [(spot_file, "spot"), (futures_file, "futures CSV")]:
        if keep_spot and file_type == "spot":
            continue 
        if file_path and file_path.exists():
            try:
                file_path.unlink()
                print(f"   🗑️  Cleaned up {file_type} file: {file_path.name}")
                files_cleaned += 1
            except Exception as e:
                print(f"   ⚠️  Could not remove {file_type} file: {e}")

    return files_cleaned