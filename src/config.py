import os
import json
import sys
from typing import Dict

# --- Firebase Imports ---
try:
    import firebase_admin
    from firebase_admin import credentials, firestore, auth
    FIREBASE_AVAILABLE = True
except ImportError:
    firebase_admin = None
    credentials = None
    firestore = None
    auth = None
    FIREBASE_AVAILABLE = False
    print("❌ Firebase libraries not available - This version requires Firebase for Hugging Face")

# --- Constants ---
STABLECOINS = {
     # STABLECOINS + WRAPPED COINS GOES HERE
    'USD+', 'USD0', 'USD1', 'USD3', 'USDA', 'USDAT', 'USDB', 'USDC', 'USDC.E',
    'USDCV', 'USDCX', 'USDD', 'USDE', 'USDF', 'USDFC', 'USDG', 'USDGLO', 'USDGO',
    'USDH', 'USDJ', 'USDKG', 'USDL', 'USDM', 'USDM1', 'USDN', 'USDO', 'USDON', 'USDP',
    'USDPT', 'USDQ', 'USDR', 'USDRIF', 'USDS', 'USDSM', 'USDST', 'USDSUI', 'USDT', 
    'USDT+', 'USDT0', 'USDTB', 'USDTZ', 'USDU', 'USDV', 'USDW', 'USDX', 'USDXL', 'USDY',
    'USDZ', 'ALUSD', 'APXUSD', 'AUSD', 'AVUSD', 'BNBUSD', 'BNUSD', 'BSC-USD', 'BTCUSD',
    'BUSD', 'CGUSD', 'CRVUSD', 'CTUSD', 'CUSD', 'DFIUSD', 'DUSD', 'EUSD', 'FDUSD',
    'FEUSD', 'FRXUSD', 'FTUSD', 'FUSD', 'FXUSD', 'GGUSD', 'GUSD', 'HLUSD', 'HYUSD', 'INVUSD', 
    'IUSD', 'JUPUSD', 'JUSD', 'KUSD', 'LISUSD', 'LUSD', 'LVLUSD', 'LVUSD', 'MANTRAUSD', 'MCUSD', 
    'MKUSD', 'MSUSD', 'MUSD', 'NUSD', 'NXUSD', 'OUSD', 'PATHUSD', 'PMUSD', 'PUSD', 'PYUSD', 
    'REUSD', 'RLUSD', 'RUSD', 'RZUSD', 'SATUSD', 'SIGUSD', 'SPUSD', 'SRUSD', 'SSUPERUSD', 'STUSD',
    'SUSD', 'SVJUSD', 'THUSD', 'TRUSD', 'TUSD', 'USAD', 'USAT', 'USC', 'USN', 'FIDD','MUB', 'USR', 'USS', 'USSD', 
    'USX', 'USYC', 'VUSD', 'VYUSD', 'WUSD', 'XUSD', 'YUSD', 'YZUSD', 'USTB', 'USTBL', 'USTC', 'UTY', 
    'UXD', 'AEUR', 'EUR0', 'EURAU', 'EURC', 'EURCV', 'EURE', 'EURI', 'EURM', 'EURQ', 'EURR', 'EURS', 'EURT', 
    'EUROT', 'EUROP', 'EUSDT', 'JEUR', 'REUR', 'SEUR', 'VEUR', 'GBPE', 'GBPM', 'TGBP', 'VGBP', 'CJPY', 'GYEN',
    'JPYC', 'JPYM', 'JPYSC', 'JPYT', 'AUDD', 'AUDM', 'AUDX', 'AUDF', 'AUSDT', 'BRL1', 'BRLA', 'BRLM', 'BRLV', 'BRZ', 
    'CADC', 'CADD', 'CADM', 'CHFAU', 'CHFM', 'CHUSD', 'CNGN', 'COPM', 'EMXN', 'HCHF', 'IDRT', 'IDRX', 'KESM', 'KRW1', 
    'KRWQ', 'KRWO', 'MXNE', 'NECT', 'NGNM', 'PHPM', 'QCAD', 'RLUST', 'SBUSDT', 'SOFID', 'TRYB', 'VAI', 'VCHF',
    'VCRED', 'VNST', 'WBRL', 'WCOP', 'WITRY', 'WMXN', 'WPEN', 'XDAI', 'XSGD', 'XTUSD', 'YLDS', 'YNUSDX', 'ZARM', 'ZARP', 'ZCHF',
    'ZSD', 'CBBTC', 'WBNB', 'WBTC', 'WETH', 'WAETHUSDC', 'WAETHUSDT', 'VBUSDC', 'BVUSDC', 'WEMIX$', 'XMD', 'HOLLAR', 'FRAX',
    # TOKENIZED bSTOCKS
    'AAPLB', 'AAOIB', 'ALABB', 'AMATB', 'AMZNB', 'ASMLB', 'AVGOB', 'AXTIB',
    'BMNRB', 'CBRSB', 'COHRB', 'COINB', 'CRCLB', 'CRDOB', 'DELLB', 'FLNCB',
    'GMEB', 'GOOGLB', 'GSB', 'HOODB', 'IBMB', 'IRENB', 'LITEB', 'METAB',
    'MRVLB', 'MUUB', 'NBISB', 'NFLXB', 'NVDAB', 'ORCLB', 'PLTRB', 'PYPLB',
    'QCOMB', 'QQQB', 'RKLBB', 'SKHYB', 'SMCIB', 'SMHB', 'SNDKB', 'SOXLB',
    'SOXSB', 'SPCXB', 'SPYB', 'TSLAB', 'TSMB', 'USARB', 'WDCB', 'NOKB',
    # TOKENIZED xSTOCKS
    'AAPLX', 'ABBVX', 'ABTX', 'ACNX', 'AMBRX', 'AMDX', 'AMZNX', 'APPX',
    'ARKX', 'ASMLX', 'AVGOX', 'AZNX', 'BACX', 'BMNRX', 'BRK.BX', 'BTGOX',
    'CEGX', 'CLSKX', 'CMCSAX', 'COINX', 'COPXX', 'CORZX', 'CRCLX', 'CRWDX',
    'CSCOX', 'CVXX', 'DHRX', 'ETNX', 'GMEX', 'GOOGLX', 'GSX', 'HDX', 'HONX',
    'HOODX', 'IBMX', 'IEMGX', 'INTCX', 'IWMX', 'JNJX', 'JPMX', 'KOX', 'KRAQX',
    'LINX', 'LLYX', 'MARAX', 'MCDX', 'MDTX', 'METAX', 'MRKX', 'MRVLX', 'MSFTX',
    'MSTRX', 'NFLXX', 'NVDAX', 'NVOX', 'OPENX', 'ORCLX', 'PALLX', 'PEPX',
    'PFEX', 'PGX', 'PLTRX', 'PPLTX', 'QQQX', 'RBLXX', 'RIOTX', 'RSPCX',
    'SCHFX', 'SKHYX', 'SLVX', 'SNDKX', 'SPCXX', 'SPYX', 'STRCX', 'TMOX',
    'TQQQX', 'TSLAX', 'TSMX', 'TSPACEX', 'UBERX', 'UNHX', 'VCXX', 'VTIX',
    'VTX', 'WCRCLX', 'WGOOGLX', 'WMTX', 'WNVDAX', 'WSKHYX', 'WSNDKX',
    'WSPCXX', 'WTSLAX', 'WTSPCX', 'XOMX'
}

FIREBASE_WEB_API_KEY = os.environ.get("FIREBASE_API_KEY")

# --- Database Initialization ---
db = None # Global DB object

def init_firebase():
    """Initialize Firebase connection using environment variables."""
    global db
    if not FIREBASE_AVAILABLE:
        raise ImportError("Firebase libraries not installed.")
    
    firebase_config_str = os.environ.get("FIREBASE_CONFIG")
    if not firebase_config_str:
        # In development, you might want to skip this or warn
        print("⚠️ FIREBASE_CONFIG not set")
        return None
    
    try:
        if not firebase_admin._apps:
            cred = credentials.Certificate(json.loads(firebase_config_str))
            firebase_admin.initialize_app(cred)
        
        db = firestore.client()
        print("✅ Firebase Connected Successfully")
        return db
    except Exception as e:
        raise Exception(f"Firebase initialization failed: {e}")

# --- User Management Helpers ---

def get_user_keys(uid) -> Dict:
    if not db: return {}
    try:
        doc = db.collection('users').document(uid).get()
        if doc.exists:
            return doc.to_dict()
    except Exception as e:
        print(f"Firestore Error: {e}")
    return {}

def update_user_keys(uid, data):
    if not db: return False
    try:
        db.collection('users').document(uid).set(data, merge=True)
        return True
    except Exception:
        return False

def is_user_setup_complete(uid):
    keys = get_user_keys(uid)
    required = ["CMC_API_KEY", "COINGECKO_API_KEY", "LIVECOINWATCH_API_KEY", "COINALYZE_VTMR_URL"]
    for k in required:
        if k not in keys or not keys[k] or "CONFIG_" in str(keys[k]):
            return False
    return True

# Admin dashboard stats
def increment_global_stat(field: str):
    """Atomically increments a global statistic in Firestore."""
    if not db: return
    try:
        # 'stats' collection, 'global' document
        ref = db.collection('stats').document('global')
        # Use merge=True to create the document if it doesn't exist
        ref.set({field: firestore.Increment(1)}, merge=True)
    except Exception as e:
        print(f"⚠️ Stats Increment Error: {e}")

def get_global_stats() -> Dict:
    """Fetches global statistics from Firestore."""
    if not db: return {}
    try:
        doc = db.collection('stats').document('global').get()
        return doc.to_dict() if doc.exists else {}
    except Exception as e:
        print(f"⚠️ Stats Fetch Error: {e}")
        return {}