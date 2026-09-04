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
    'SUSD', 'SVJUSD', 'THUSD', 'TRUSD', 'TUSD', 'USAD', 'USAT', 'USC', 'USN', 'FIDD','MUB', 'USR', 'USSI', 'USSD', 
    'USX', 'USYC', 'VUSD', 'VYUSD', 'WUSD', 'XUSD', 'YUSD', 'YZUSD', 'USTB', 'USTBL', 'USTC', 'UTY', 
    'UXD', 'AEUR', 'EUR0', 'EURAU', 'EURC', 'EURCV', 'EURE', 'EURI', 'EURM', 'EURQ', 'EURR', 'EURS', 'EURT', 
    'EUROT', 'EUROP', 'EUSDT', 'JEUR', 'REUR', 'SEUR', 'VEUR', 'GBPE', 'GBPM', 'TGBP', 'VGBP', 'CJPY', 'GYEN',
    'JPYC', 'JPYM', 'JPYSC', 'JPYT', 'AUDD', 'AUDM', 'AUDX', 'AUDF', 'AUSDT', 'BRL1', 'BRLA', 'BRLM', 'BRLV', 'BRZ', 
    'CADC', 'CADD', 'CADM', 'CHFAU', 'CHFM', 'CHUSD', 'CNGN', 'COPM', 'EMXN', 'HCHF', 'IDRT', 'IDRX', 'KESM', 'KRW1', 
    'KRWQ', 'KRWO', 'MXNE', 'NECT', 'NGNM', 'PHPM', 'QCAD', 'RLUST', 'SBUSDT', 'SOFID', 'TRYB', 'VAI', 'VCHF',
    'VCRED', 'VNST', 'WBRL', 'WCOP', 'WITRY', 'WMXN', 'WPEN', 'XDAI', 'XSGD', 'XTUSD', 'YLDS', 'YNUSDX', 'ZARM', 'ZARP', 'ZCHF',
    'ZSD', 'CBBTC', 'WBNB', 'WBTC', 'WETH', 'WAETHUSDC', 'WAETHUSDT', 'VBUSDC', 'BVUSDC', 'WEMIX$', 'XMD', 'HOLLAR', 'FRAX',
    'DAI', 'sDAI', 'USDS', 'sUSDS', 'GHO', 'eUSD', 'sFRAX', 'MIM', 'DOLA', 'GRAI',
    'HAI', 'USD0++', 'sUSDe', 'USDe', 'aUSDC', 'cUSDC', 'aUSDT', 'cUSDT', 'sUSDC',
    'sBUSD', 'sWETH', 'jUSDC', 'axlUSDC', 'ckUSDC', 'USDC.N', 'MUSDC', 'xUSDC',
    'USDZC', 'ETHUSDC', 'USDC.ETH', 'USDC.SOL', 'USDC.AVAX', 'USDC.ARB', 'USDC.POL',
    'USDC.SUI', 'WUSDC.B', 'USDT.Z', 'WSTETH', 'WEETH', 'WBETH', 'WSOL', 'WTRX', 'WFLR', 'WSTX', 'WAVAX', 'WNEAR',
    'WTAO', 'WSEI', 'WBTT', 'WCRO', 'WDAG', 'WOKB', 'WNXM', 'WPOL', 'WOETH', 'WPLS',
    'WRON', 'WIOTX', 'WPROS', 'WGNK', 'WBOT', 'WKROWN', 'WRBNT', 'WSOMI', 'CKBTC',
    'RBTC', 'RSETH', 'GTETH', 'GTBTC', 'BBTC', 'KBTC', 'XBTC', 'BGBTC', 'CDCBTC',
    'CBXRP', 'CBADA', 'CBLTC', 'CBETH', 'WXRP', 'WXRP2', 'WMATIC', 'WNCG', 'WCFG',
    'WFIL', 'WIMX', 'ENZOBTC', 'WCBTC', 'OWBTC', 'RENBTC', 'SOETH', 'XETH', 'WYLDS',
    'WAPLAUSDT0', 'WNUSDT0', 'WSRUSD', 'WAETHWETH', 'WFRAX', 'WM', 'FWSTETH', 'WXPL',
    'WSTETH2', 'WETH2', 'WETH3', 'WETH4', 'WETH5', 'WETH6', 'WETH7', 'WEETH2',
    'WBTC2', 'WBTC3', 'WBTC4', 'SOL2', 'XSOL', 'LBTC', 'BTC.B', 'TBTC', 'MSOL',
    'WDAI', 'DAI2',
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
    'WSPCXX', 'WTSLAX', 'WTSPCX', 'XOMX', 'KORUB', 'SPCX', 'WMETAX', 'WCOINX', 'SNDKON', 
    'MU', 'FGRS', 'BSPX', 'CRCLON', 'GLDX', 'MRNAON', 'DAAPL', 'DTSLA', 'DNVDA', 'DSPY',
    'DMSFT', 'DMSTR', 'DCOIN', 'ITOT', 'BULLET', 'SPACEX', 'SPCE','SPY','NVDA', 
    # DEAD CRYPTOS
    'JOHN'
}

FIREBASE_WEB_API_KEY = os.environ.get("FIREBASE_API_KEY")

# --- Database Initialization ---
db = None # Global DB object

def _patch_database_string(client, database_id):
    resolved_id = database_id or "(default)"
    try:
        client._database_string_internal = f"projects/{client.project}/databases/{resolved_id}"
    except AttributeError as e:
        raise RuntimeError(
        ) from e

def init_firebase():
    """Initialize Firebase connection using environment variables."""
    global db
    if not FIREBASE_AVAILABLE:
        raise ImportError("Firebase libraries not installed.")

    firebase_config_str = os.environ.get("FIREBASE_CONFIG")
    if not firebase_config_str:
        raise RuntimeError("FIREBASE_CONFIG environment variable is not set.")

    try:
        if not firebase_admin._apps:
            cred = credentials.Certificate(json.loads(firebase_config_str))
            firebase_admin.initialize_app(cred)

        # Optional override: set FIRESTORE_DATABASE_ID 
        database_id = os.environ.get("FIRESTORE_DATABASE_ID") or None
        db = firestore.client(database_id=database_id)
        _patch_database_string(db, database_id)
        print("✅ Firebase Connected Successfully")
        return db
    except Exception as e:
        raise RuntimeError(f"Firebase initialization failed: {e}") from e

# --- User Management Helpers ---

def _log_firestore_exception(label: str, e: Exception):
    """Log a Firestore exception in one line"""
    code = getattr(e, "code", None)
    print(f"Firestore Error ({label}): {type(e).__name__} code={code} - {e}")

def get_user_keys(uid) -> Dict:
    if not db: return {}
    try:
        doc = db.collection('users').document(uid).get()
        if doc.exists:
            return doc.to_dict()
    except Exception as e:
        _log_firestore_exception("get_user_keys", e)
    return {}

def update_user_keys(uid, data):
    if not db: return False
    try:
        db.collection('users').document(uid).set(data, merge=True)
        return True
    except Exception as e:
        _log_firestore_exception("update_user_keys", e)
        return False

def is_user_setup_complete(uid):
    keys = get_user_keys(uid)
    required = ["COINGECKO_API_KEY", "COINALYZE_VTMR_URL"]
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