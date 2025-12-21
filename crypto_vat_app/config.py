import os
import threading
from pathlib import Path
import firebase_admin
from firebase_admin import credentials, firestore

# ==============================
# GLOBAL PATHS & STATE
# ==============================
BASE_DIR = Path(__file__).resolve().parent
UPLOAD_FOLDER = BASE_DIR / "temp_uploads"
UPLOAD_FOLDER.mkdir(exist_ok=True)

# Default to local cwd if no other path found
REPORT_SAVE_PATH = Path.cwd()

# Global Threading State
LIVE_LOGS = []
PROGRESS = {"percent": 0, "text": "System Idle", "status": "idle"}
LOCK = threading.Lock()

# ==============================
# API KEYS & CONFIG
# ==============================
HTML2PDF_API_KEY = 'CONFIG_REQUIRED_HTML2PDF'
CMC_API_KEY = 'CONFIG_REQUIRED_CMC'
LIVECOINWATCH_API_KEY = 'CONFIG_REQUIRED_LCW'
COINRANKINGS_API_KEY = 'CONFIG_REQUIRED_CR'
COINALYZE_VTMR_URL = 'CONFIG_VTMR_URL'

STABLECOINS = {
    'USDT', 'USDC', 'BUSD', 'DAI', 'BSC-USD', 'USD1', 'CBBTC', 'WBNB', 'WETH',
    'UST', 'TUSD', 'USDP', 'USDD', 'FRAX', 'GUSD', 'LUSD', 'FDUSD'
}

# ==============================
# FIREBASE HELPER (LOCAL MODE)
# ==============================
class FirebaseHelper:
    _db = None
    _initialized = False

    @classmethod
    def initialize(cls):
        """Initializes Firestore/Auth ONLY. Skips Storage."""
        if not cls._initialized:
            try:
                cred_path = BASE_DIR / "firebase_credentials.json"
                if cred_path.exists():
                    cred = credentials.Certificate(str(cred_path))
                    # Initialize WITHOUT storageBucket
                    if not len(firebase_admin._apps):
                        firebase_admin.initialize_app(cred)
                    
                    cls._db = firestore.client()
                    cls._initialized = True
                    print("   ✅ Firebase Auth & DB Connected (Local Mode)")
                else:
                    print("   ⚠️  firebase_credentials.json missing.")
            except Exception as e:
                print(f"   ❌ Firebase Init Error: {e}")
        return cls._db, None # Return None for bucket

    @staticmethod
    def upload_report(user_id: str, local_path: Path):
        """
        Local Mode: Skips cloud upload.
        Returns None so the engine knows it's local only.
        """
        return None

    @staticmethod
    def log_activity(user_id: str, action: str):
        db, _ = FirebaseHelper.initialize()
        if db:
            try:
                db.collection('analytics').add({
                    'uid': user_id,
                    'action': action,
                    'timestamp': firestore.SERVER_TIMESTAMP
                })
            except: pass