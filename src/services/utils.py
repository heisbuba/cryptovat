import os
import datetime
import requests
from pathlib import Path
from typing import Optional
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from playwright.sync_api import sync_playwright

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

def convert_html_to_pdf(html_content: str, user_id: str) -> Optional[Path]:
    # Render HTML string to PDF file using headless Chromium
    print("   Converting to PDF (Using Playwright)...")
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    pdf_name = f"crypto-analysis-{timestamp}.pdf"
    
    user_dir = get_user_temp_dir(user_id)
    pdf_path = user_dir / pdf_name
        
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            try:
                page = browser.new_page()
                
                # Ensure styles/assets are fully loaded before printing
                page.set_content(html_content, wait_until="load")
                
                # Export to US Letter with full background rendering and 0 margins
                page.pdf(
                    path=pdf_path,
                    format="Letter",       
                    landscape=False,
                    scale=1.0,            
                    print_background=True,
                    margin={"top": "0", "bottom": "0", "left": "0", "right": "0"}
                )
            finally:
                browser.close()

        file_size = pdf_path.stat().st_size
        print(f"   PDF created: {pdf_name}")
        print(f"   Size: {file_size:,} bytes")
        print(f"   Location: {user_dir}")
        return pdf_path

    except Exception as e:
        print(f"   ❌ Playwright Error: {e}")
        return None

# --- File Cleanup ---

def cleanup_after_analysis(spot_file: Optional[Path], futures_file: Optional[Path]) -> int:
    # File identity is recorded in the manifest at creation time.
    files_cleaned = 0

    for file_path, file_type in [(spot_file, "spot"), (futures_file, "futures CSV")]:
        if file_path and file_path.exists():
            try:
                file_path.unlink()
                print(f"   🗑️  Cleaned up {file_type} file: {file_path.name}")
                files_cleaned += 1
            except Exception as e:
                print(f"   ⚠️  Could not remove {file_type} file: {e}")
    
    if files_cleaned > 0:
        print(f"   ✅ Cleaned up {files_cleaned} source files")
    return files_cleaned