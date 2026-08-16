import threading
import requests
import datetime
import time
import csv
import io
from flask import Blueprint, jsonify, session, request, redirect, url_for, render_template, flash, Response
from markupsafe import escape
from werkzeug.utils import secure_filename
from googleapiclient.errors import HttpError

# --- Import Logic Services --- #
from ..services.spot_engine import spot_volume_tracker
from ..services.analysis import crypto_analysis_v4
from ..services.deep_diver_engine import calculate_deep_dive
from ..services.futures_engine import PDFParser
from ..services.journal_engine import JournalEngine
from ..services import screener_engine
from ..state import LOCK, USER_LOGS, USER_PROGRESS, update_progress, get_user_temp_dir, get_progress, set_pending_file, try_start_task, end_task
from ..config import get_user_keys, update_user_keys, db, firestore, increment_global_stat
from .auth import login_required

# --- Simple DD Search Cache --- #
SEARCH_CACHE = {} 
SEARCH_TTL = 3600  # 1-hour TTL for search results

tasks_bp = Blueprint('tasks', __name__)

# -- Deep Diver -- #
@tasks_bp.route('/quant-diver')
@login_required
def quant_diver_page():
    return render_template('dashboard/deep_diver.html')
    
# --- Background Worker Helper --- #
def run_background_task(target_func, user_id) -> bool:
    """Prevents two concurrent same-user actions from
    racing each other's progress/manifest writes."""
    if not try_start_task(user_id, target_func.__name__):
        return False

    # Initialize session logs and progress before spawning thread
    with LOCK:
        USER_LOGS[user_id] = []
        USER_PROGRESS[user_id] = {"percent": 5, "text": "Initializing Engine...", "status": "active"}

    def worker():
        try:
            threading.current_thread().name = f"user_{user_id}"
            user_keys = get_user_keys(user_id)
            target_func(user_keys, user_id)
            increment_global_stat("lifetime_scans")
            update_progress(user_id, 100, "Analysis Complete", "success")
        except Exception as e:
            print(f"\n[CRITICAL ERROR] {str(e)}\n")
            update_progress(user_id, 0, str(e) or "Error Occurred", "error")
        finally:
            end_task(user_id)

    # Run task in daemon thread to prevent blocking main process
    thread = threading.Thread(target=worker, name=f"user_{user_id}")
    thread.daemon = True
    thread.start()
    return True

# --- Job Triggers --- #

@tasks_bp.route("/run-spot")
@login_required
def run_spot():
    uid = session['user_id']
    if not run_background_task(spot_volume_tracker, uid):
        return jsonify({"status": "busy", "message": "A task is already running for your account. Please wait for it to finish."})
    return jsonify({"status": "started"})

@tasks_bp.route("/run-advanced")
@login_required
def run_advanced():
    uid = session['user_id']
    if not run_background_task(crypto_analysis_v4, uid):
        return jsonify({"status": "busy", "message": "A task is already running for your account. Please wait for it to finish."})
    return jsonify({"status": "started"})

# --- Progress & Logs API --- #

@tasks_bp.route("/progress")
@login_required
def progress():
    uid = session['user_id']
    return jsonify(get_progress(uid))

@tasks_bp.route("/logs-chunk")
@login_required
def logs_chunk():
    # Returns incremental log updates to the frontend based on last index
    uid = session['user_id']
    try:
        last_idx = int(request.args.get('last', 0))
    except (ValueError, TypeError):
        last_idx = 0
    
    with LOCK:
        logs = USER_LOGS.get(uid, [])
        current_len = len(logs)
        if last_idx >= current_len:
            new_logs = []
        else:
            new_logs = logs[last_idx:]
            
    return jsonify({"logs": new_logs, "last_index": current_len})


# --- Filters Save & Retrieve --- #
@tasks_bp.route("/save-filters", methods=["POST"])
@login_required
def save_filters():
    uid = session['user_id']
    filter_data = request.get_json()
    success = update_user_keys(uid, {"engine_settings": filter_data})
    if success:
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 500

@tasks_bp.route("/reset-filters", methods=["POST"])
@login_required
def reset_filters():
    # Remove custom engine settings from user's Firestore document
    uid = session['user_id']
    if not db:
        return jsonify({"status": "error"}), 500
    try:
        db.collection('users').document(uid).update({
            "engine_settings": firestore.DELETE_FIELD
        })
        return jsonify({"status": "success"})
    except Exception as e:
        print(f"Reset Error: {e}")
        return jsonify({"status": "error"}), 500

# --- Token Screener --- #
@tasks_bp.route("/screener/refresh")
@login_required
def token_screener_refresh():
    screener_engine.invalidate_cache()
    return redirect(url_for('main.token_screener'))

@tasks_bp.route("/screener/reset")
@login_required
def token_screener_reset():
    uid = session['user_id']
    for key in screener_engine.DEFAULT_FILTERS:
        session.pop(f"{screener_engine.SESSION_PREFIX}{key}", None)
    session.pop(f"{screener_engine.SESSION_PREFIX}{screener_engine.INCLUDE_NO_1Y_KEY}", None)

    # Also clear the persisted Firestore defaults (see token_screener's profile_updates)
    if db:
        try:
            updates = {
                f"{screener_engine.PROFILE_PREFIX}{key}": firestore.DELETE_FIELD
                for key in screener_engine.DEFAULT_FILTERS
            }
            updates[f"{screener_engine.PROFILE_PREFIX}{screener_engine.INCLUDE_NO_1Y_KEY}"] = firestore.DELETE_FIELD
            db.collection('users').document(uid).update(updates)
        except Exception as e:
            print(f"Screener Reset Error: {e}")

    flash("Filters reverted to system defaults.", "success")
    return redirect(url_for('main.token_screener'))

@tasks_bp.route("/screener/export.csv")
@login_required
def token_screener_export_csv():
    uid = session['user_id']
    user_data = get_user_keys(uid)
    api_key = user_data.get("COINGECKO_API_KEY", "")

    filters = {
        k: screener_engine.resolve_filter(k, session, user_data)
        for k in screener_engine.DEFAULT_FILTERS
    }
    thresholds = {k: screener_engine.parse_threshold(k, filters[k]) for k in screener_engine.DEFAULT_FILTERS}

    include_no_1y_raw = session.get(
        f"{screener_engine.SESSION_PREFIX}{screener_engine.INCLUDE_NO_1Y_KEY}",
        user_data.get(f"{screener_engine.PROFILE_PREFIX}{screener_engine.INCLUDE_NO_1Y_KEY}", screener_engine.INCLUDE_NO_1Y_DEFAULT),
    )
    include_no_1y = str(include_no_1y_raw) == "1"

    raw_tokens = screener_engine.get_screener_data(api_key)
    tokens = screener_engine.filter_tokens(raw_tokens, thresholds, include_no_1y)
    tokens.sort(key=lambda x: x.get("vtmr_raw", 0.0), reverse=True)

    fields = ["id", "symbol", "name", "fmt_price", "fmt_mcap", "fmt_volume",
              "vtmr_display", "fmt_24h", "fmt_7d", "fmt_30d", "fmt_1y"]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for t in tokens:
        row = dict(t)
        row["symbol"] = str(row.get("symbol", "")).upper()
        writer.writerow(row)

    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=quantvat_token_screener_filtered.csv"},
    )

# --- Deep Diver Data Handling --- #
@tasks_bp.route("/api/search-tickers")
@login_required
def search_tickers():
    global SEARCH_CACHE
    query = request.args.get('q', '').strip().lower()
    if not query: return jsonify([])

    now = time.time()
    SEARCH_CACHE = {k: v for k, v in SEARCH_CACHE.items() if now < v[1] + SEARCH_TTL}
    if query in SEARCH_CACHE:
       data, timestamp = SEARCH_CACHE[query]
       return jsonify(data)

    uid = session['user_id']
    user_keys = get_user_keys(uid)
    cg_key = user_keys.get("COINGECKO_API_KEY", "")
    
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    if cg_key and "pro-api" not in cg_key and cg_key != "CONFIG_REQUIRED_CG":
        headers["x-cg-demo-api-key"] = cg_key

    try:
        # Proxy search to CoinGecko and cache results to save API credits
        r = requests.get(f"https://api.coingecko.com/api/v3/search?query={query}", headers=headers, timeout=5)
        r.raise_for_status()
        results = r.json().get('coins', [])[:8]
        SEARCH_CACHE[query] = (results, now)
        return jsonify(results)
    except Exception as e:
        print(f"[SEARCH ERROR] {e}")
        return jsonify([])

@tasks_bp.route("/api/dive/<coin_id>")
@login_required
def get_dive_data(coin_id):
    # Fetch granular coin statistics and ratios
    uid = session['user_id']
    user_keys = get_user_keys(uid)
    data = calculate_deep_dive(coin_id, user_keys)
    if data.get("status") == "error":
        return jsonify(data), 500
    # Watchlist save & retrieve
    watchlist = user_keys.get('watchlist', [])
    data['is_watched'] = any(item.get('coin_id') == coin_id for item in watchlist)
    return jsonify(data)

# --- Futures Data Handling --- #
@tasks_bp.route("/get-futures-data")
@login_required
def get_futures_data():
    uid = session['user_id']
    user_keys = get_user_keys(uid)
    futures_url = user_keys.get("COINALYZE_VTMR_URL", "")
    return render_template("dashboard/upload_futures.html", futures_url=futures_url)

@tasks_bp.route("/upload-futures", methods=["POST"])
@login_required
def upload_futures():
    # Handle PDF upload and trigger background parsing
    if 'futures_pdf' not in request.files:
        return jsonify({"error": "No file part"}), 400
        
    file = request.files['futures_pdf']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if not file.filename.lower().endswith('.pdf') or file.mimetype not in (
        'application/pdf', 'application/x-pdf', 'application/octet-stream'
    ):
        return jsonify({"error": "Only PDF files are accepted"}), 400

    uid = session['user_id']
    if not try_start_task(uid, "upload_futures"):
        return jsonify({"error": "A task is already running for your account. Please wait for it to finish."}), 409
    try:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"futures_data_{timestamp}.pdf"
        user_dir = get_user_temp_dir(uid)
        save_path = user_dir / filename
        file.save(save_path)
        
        def parse_worker(path_to_process):
            try:
                threading.current_thread().name = f"user_{uid}"
                update_progress(uid, 0, "File received. Extracting data tables...", "active")
                update_progress(uid, 50, "Parsing PDF tables...", "active")
                csv_path = PDFParser.extract_and_persist(path_to_process)
                if csv_path:
                    set_pending_file(uid, "futures", csv_path)
                    # Raw PDF is no longer needed once extraction succeeds
                    try:
                        path_to_process.unlink()
                    except Exception as e:
                        print(f"   Could not remove source futures PDF: {e}")
                    update_progress(uid, 100, "Futures Data Parsed & Ready.", "success")
                else:
                    update_progress(uid, 0, "PDF recognized but no table data found.", "error")
            except Exception as e:
                update_progress(uid, 0, f"Parse Error: {str(e)}", "error")
            finally:
                end_task(uid)

        thread = threading.Thread(target=parse_worker, args=(save_path,))
        thread.start()

        return jsonify({"status": "success", "message": "Upload successful, parsing started."}), 200
    except Exception as e:
        end_task(uid)
        return jsonify({"error": str(e)}), 500

# --- Trading Journal Routes --- #
@tasks_bp.route("/journal/save", methods=["POST"])
@login_required
def save_journal_trade():
    # Persistent storage of trade logs to Google Drive AppData
    uid = session['user_id']
    trade_entry = request.get_json()
    
    creds = JournalEngine.get_creds(uid)
    if not creds:
        return jsonify({"status": "error", "message": "Google Drive not linked"}), 401
    
    try:
        service = JournalEngine.get_drive_service(creds)
        file_id = JournalEngine.initialize_journal(service, uid=uid)
        try:
            JournalEngine.save_trade(service, file_id, trade_entry)
        except HttpError as e:
            if e.resp.status != 404:
                raise
            update_user_keys(uid, {"journal_drive_file_id": firestore.DELETE_FIELD})
            file_id = JournalEngine.initialize_journal(service, uid=uid)
            JournalEngine.save_trade(service, file_id, trade_entry)
        
        return jsonify({
            "status": "success", 
            "message": "Trade synced", 
            "trade": trade_entry 
        })
    except Exception as e:
        print(f"❌ Journal Save Error: {e}") 
        return jsonify({"status": "error", "message": str(e)}), 500

@tasks_bp.route("/journal/delete/<trade_id>", methods=["POST"])
@login_required
def delete_journal_trade(trade_id):
    # Remove specific trade entry from Drive file by ID
    uid = session['user_id']
    creds = JournalEngine.get_creds(uid)
    if not creds:
        return jsonify({"status": "error", "message": "Google Drive session expired. Please reconnect."}), 401
    
    try:
        service = JournalEngine.get_drive_service(creds)
        file_id = JournalEngine.initialize_journal(service, uid=uid)
        try:
            success = JournalEngine.delete_trade(service, file_id, str(trade_id))
        except HttpError as e:
            if e.resp.status != 404:
                raise
            update_user_keys(uid, {"journal_drive_file_id": firestore.DELETE_FIELD})
            file_id = JournalEngine.initialize_journal(service, uid=uid)
            success = JournalEngine.delete_trade(service, file_id, str(trade_id))
        
        if success:
            return jsonify({"status": "success", "message": "Trade Log deleted successfully"})
        else:
            return jsonify({"status": "error", "message": "Trade not found in your journal file"}), 404
            
    except Exception as e:
        print(f"❌ Deletion Error: {str(e)}")
        return jsonify({"status": "error", "message": "Internal Server Error during deletion"}), 500
        
@tasks_bp.route("/journal/stats")
@login_required
def get_journal_stats():
    # Return winrate, best ticker, and dominant bias metrics
    uid = session['user_id']
    creds = JournalEngine.get_creds(uid)
    if not creds: return jsonify({})
    try:
        service = JournalEngine.get_drive_service(creds)
        file_id = JournalEngine.initialize_journal(service, uid=uid)
        try:
            journal = JournalEngine.load_journal(service, file_id)
        except HttpError as e:
            if e.resp.status != 404:
                raise
            update_user_keys(uid, {"journal_drive_file_id": firestore.DELETE_FIELD})
            file_id = JournalEngine.initialize_journal(service, uid=uid)
            journal = JournalEngine.load_journal(service, file_id)
        return jsonify(JournalEngine.calculate_stats(journal))
    except Exception as e:
        print(f"⚠️ Journal Stats Error: {e}")
        return jsonify({})

# ---------------------------------------------------------
# GOOGLE AUTH FLOW
# ---------------------------------------------------------

@tasks_bp.route("/auth/google/login")
@login_required
def google_login():
    # Redirect to Google's consent screen for Drive access
    flow = JournalEngine.get_flow()
    authorization_url, state = flow.authorization_url(
        access_type='offline', 
        include_granted_scopes='true',
        prompt='consent'
    )
    session['oauth_state'] = state
    session['code_verifier'] = flow.code_verifier 
    return redirect(authorization_url)

@tasks_bp.route("/auth/google/callback")
@login_required
def google_callback():
    flow = JournalEngine.get_flow()
    flow.code_verifier = session.get('code_verifier')  
    authorization_response = request.url.replace('http:', 'https:')

    try:
        flow.fetch_token(authorization_response=authorization_response)
        creds = flow.credentials
        uid = session['user_id']
        update_user_keys(uid, {
            "google_refresh_token": creds.refresh_token,
            "google_token_json": creds.to_json()
        })
        session.pop('code_verifier', None)   # cleanup
        flash("Google Drive connected successfully!", "success")
        return redirect(url_for('main.settings'))
    except Exception as e:
        print(f"❌ OAuth Callback Error: {e}")
        flash(f"Login Failed: {str(e)}", "error")
        return redirect(url_for('main.settings'))

@tasks_bp.route("/auth/google/disconnect", methods=["POST"])
@login_required
def google_disconnect():
    # Remove Google Drive credentials from database
    uid = session['user_id']
    try:
        db.collection('users').document(uid).update({
            "google_refresh_token": firestore.DELETE_FIELD,
            "google_token_json": firestore.DELETE_FIELD,
            "journal_drive_file_id": firestore.DELETE_FIELD
        })
        flash("Google Drive has been disconnected.", "success")
        return redirect(url_for('main.settings'))
    except Exception as e:
        print(f"Disconnect Error: {e}")
        flash(f"Disconnect Failed: {str(e)}", "error")
        return redirect(url_for('main.settings'))

# -- Watchlist Routes -- #

@tasks_bp.route('/api/watchlist/toggle', methods=['POST'])
@login_required
def toggle_watchlist():
    # Atomic toggle for the watchlist with metadata snapshots
    uid = session['user_id']
    data = request.get_json()
    coin_id = data.get('coin_id')
    symbol = data.get('symbol', '').upper()
    action = data.get('action') 

    if not coin_id:
        return jsonify({"status": "error", "message": "Missing Token ID"}), 400

    try:
        user_ref = db.collection('users').document(uid)
        user_doc = user_ref.get()
        user_data = user_doc.to_dict() if user_doc.exists else {}
        watchlist = user_data.get('watchlist', [])

        if action == 'add':
            # Capture metadata snapshot to display metrics instantly on the watchlist
            entry = {
                "coin_id": coin_id,
                "symbol": symbol or "??",
                "name": data.get('name', 'Unknown'),
                "added_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                "price": data.get('price', '--'),
                "vtmr": data.get('vtmr', '--'),
                "mcap": data.get('mcap', '--'),
                "chg_24h": data.get('chg_24h', '--'),
                "chg_7d": data.get('chg_7d', '--'),
                "chg_30d": data.get('chg_30d', '--'),
                "chg_1y": data.get('chg_1y', '--')
            }
            
            # metrics
            watchlist = [item for item in watchlist if item.get('coin_id') != coin_id]
            watchlist.append(entry)
            user_ref.update({"watchlist": watchlist})
            return jsonify({"status": "success", "is_watched": True, "message": f"{symbol} added"})

        elif action == 'remove':
            watchlist = [item for item in watchlist if item.get('coin_id') != coin_id]
            user_ref.update({"watchlist": watchlist})
            return jsonify({"status": "success", "is_watched": False, "message": f"{symbol} removed"})

    except Exception as e:
        print(f"Watchlist Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500