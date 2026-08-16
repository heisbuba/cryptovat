import os
from datetime import datetime
from flask import Blueprint, render_template, session, redirect, url_for, request, flash, send_from_directory, make_response, jsonify
from googleapiclient.errors import HttpError

from ..config import get_user_keys, update_user_keys, is_user_setup_complete, db, get_global_stats, increment_global_stat, firestore
from ..state import USER_PROGRESS, get_user_temp_dir, TEMP_DIR
from .auth import login_required
from ..services.journal_engine import JournalEngine
from ..services.ai_modal_engine import AiModalEngine
from ..services import screener_engine

main_bp = Blueprint('main', __name__)

# --- Navigation & Dashboard --- #

@main_bp.route("/")
def index():
    if session.get('user_id') and not request.args.get('no_redirect'):
        response = redirect(url_for('main.home'))
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        return response
    
    response = make_response(render_template("index.html"))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response

@main_bp.route("/dashboard")
@login_required
def home():
    uid = session['user_id']
    if not is_user_setup_complete(uid):
        return redirect(url_for('main.setup'))

    user_data = get_user_keys(uid) or {}  
    filters = user_data.get("engine_settings", {}) 

    admin_id = os.environ.get('ADMIN_UID', '')
    is_admin = uid == admin_id or uid in admin_id.split(',')

    return render_template("dashboard/home.html", is_admin=is_admin, filters=filters)
    

# --- Configuration & Setup --- #

@main_bp.route("/setup")
@login_required
def setup():
    uid = session['user_id']
    current_keys = get_user_keys(uid)
    return render_template("includes/partials/setup.html",
        cmc=current_keys.get("CMC_API_KEY", ""),
        cg=current_keys.get("COINGECKO_API_KEY", ""),
        lcw=current_keys.get("LIVECOINWATCH_API_KEY", ""),
        vtmr=current_keys.get("COINALYZE_VTMR_URL", "")
    )

@main_bp.route("/settings")
@login_required
def settings():
    uid = session['user_id']
    current_keys = get_user_keys(uid)
    # Check if Google OAuth flow was completed
    drive_linked = "google_refresh_token" in current_keys
    return render_template("dashboard/settings.html",
        cmc=current_keys.get("CMC_API_KEY", ""),
        cg=current_keys.get("COINGECKO_API_KEY", ""),
        lcw=current_keys.get("LIVECOINWATCH_API_KEY", ""),
        vtmr=current_keys.get("COINALYZE_VTMR_URL", ""),
        drive_linked=drive_linked,
        user_settings=current_keys
    )

@main_bp.route("/save-config", methods=["POST"])
@login_required
def save_config():
    uid = session['user_id']
    source = request.form.get("source", "setup")
    is_autosave = request.form.get("autosave") == "1"
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    keys = {
        "CMC_API_KEY": request.form.get("cmc_key", "").strip(),
        "COINGECKO_API_KEY": request.form.get("cg_key", "").strip(),
        "LIVECOINWATCH_API_KEY": request.form.get("lcw_key", "").strip(),
        "COINALYZE_VTMR_URL": request.form.get("vtmr_url", "").strip()
    }
    
    if not update_user_keys(uid, keys):
        if is_ajax:
            return jsonify({"status": "error", "message": "Could not save configuration."}), 500
        
        flash("System Error: Could not save configuration.", "error")
        # Preserve typed inputs by re-rendering the form
        if source == 'settings':
            current_keys = get_user_keys(uid)
            drive_linked = "google_refresh_token" in current_keys
            return render_template("dashboard/settings.html",
                cmc=keys["CMC_API_KEY"],
                cg=keys["COINGECKO_API_KEY"],
                lcw=keys["LIVECOINWATCH_API_KEY"],
                vtmr=keys["COINALYZE_VTMR_URL"],
                drive_linked=drive_linked,
                user_settings=current_keys
            )
        return render_template("includes/partials/setup.html",
            cmc=keys["CMC_API_KEY"],
            cg=keys["COINGECKO_API_KEY"],
            lcw=keys["LIVECOINWATCH_API_KEY"],
            vtmr=keys["COINALYZE_VTMR_URL"]
        )

    # For AJAX auto-save, just return JSON 
    if is_ajax:
        return jsonify({"status": "success", "message": "Saved"})

    if source == 'settings':
        flash("Configuration updated successfully!", "success")
        return redirect(url_for('main.settings'))

    # Redirect based on setup completion status
    if is_user_setup_complete(uid):
        flash("Setup Complete! Welcome to your Dashboard.", "success")
        return redirect(url_for('main.home'))
    
    flash("Progress saved! Please enter the remaining keys to continue.", "success")
    return redirect(url_for('main.setup'))

@main_bp.route("/factory-reset", methods=["POST"])
@login_required
def factory_reset():
    # Clear all API configuration keys for user
    uid = session['user_id']
    update_user_keys(uid, {
        "CMC_API_KEY": "",
        "COINGECKO_API_KEY": "",
        "LIVECOINWATCH_API_KEY": "",
        "COINALYZE_VTMR_URL": "",
        "gemini_key": "",         
        "ai_history": []
    })
    return redirect(url_for('main.setup'))

@main_bp.route("/help")
def help_page():
    setup_status = is_user_setup_complete(session['user_id']) if 'user_id' in session else False
    return render_template("pages/help.html", is_setup_complete=setup_status)
    
@main_bp.route("/privacy-policy")
def privacy_policy():
    setup_status = is_user_setup_complete(session['user_id']) if 'user_id' in session else False
    return render_template("pages/privacy-policy.html", is_setup_complete=setup_status)

@main_bp.route("/deep-diver")
@login_required
def deep_diver():
    uid = session['user_id']
    if not is_user_setup_complete(uid):
        return redirect(url_for('main.setup'))
    return render_template("dashboard/deep_diver.html")

# --- Token Screener --- #

@main_bp.route("/screener")
@login_required
def token_screener():
    uid = session['user_id']
    if not is_user_setup_complete(uid):
        return redirect(url_for('main.setup'))

    user_data = get_user_keys(uid)
    api_key = user_data.get("COINGECKO_API_KEY", "")
    watchlist = user_data.get('watchlist', [])
    watched_ids = {item.get('coin_id') for item in watchlist}

    # Filter form is a GET submit — presence of any DEFAULT_FILTERS keys
    for key in screener_engine.DEFAULT_FILTERS:
        if key in request.args:
            session[f"{screener_engine.SESSION_PREFIX}{key}"] = request.args[key]

    form_submitted = any(k in request.args for k in screener_engine.DEFAULT_FILTERS)
    if form_submitted:
        session[f"{screener_engine.SESSION_PREFIX}{screener_engine.INCLUDE_NO_1Y_KEY}"] = (
            "1" if screener_engine.INCLUDE_NO_1Y_KEY in request.args else "0"
        )
        
        profile_updates = {
            f"{screener_engine.PROFILE_PREFIX}{key}": request.args[key]
            for key in screener_engine.DEFAULT_FILTERS if key in request.args
        }
        profile_updates[f"{screener_engine.PROFILE_PREFIX}{screener_engine.INCLUDE_NO_1Y_KEY}"] = (
            "1" if screener_engine.INCLUDE_NO_1Y_KEY in request.args else "0"
        )
        update_user_keys(uid, profile_updates)
        flash("Filters applied and saved.", "success")

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

    for t in tokens:
        t["starred"] = t.get("id", "") in watched_ids

    tokens.sort(key=lambda x: x.get("vtmr_raw", 0.0), reverse=True)

    return render_template(
        "dashboard/screener.html",
        tokens=tokens,
        total=len(raw_tokens),
        filters=filters,
        include_no_1y=include_no_1y,
    )

# --- Administration --- #

@main_bp.route("/admin")
@login_required
def admin_dashboard():
    uid = session['user_id']
    admin_id = os.environ.get('ADMIN_UID', '')
    is_admin = uid == admin_id or uid in admin_id.split(',')
    if not is_admin:
        return redirect(url_for('main.home'))
    # Query user count from Firestore
    try:
        if db:
            all_users = db.collection('users').stream()
            user_count = len(list(all_users))
        else:
            user_count = "DB Error"
    except Exception:
        user_count = "DB Error"

    stats = get_global_stats()
    lifetime_scans = stats.get('lifetime_scans', 0)
    report_views = stats.get('report_views', 0)

    # Calculate total disk usage of temp directory
    total_size = 0
    if TEMP_DIR.exists():
        for dirpath, _, filenames in os.walk(TEMP_DIR):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if not os.path.islink(fp):
                    total_size += os.path.getsize(fp)
    storage_mb = round(total_size / (1024 * 1024), 2)

    return render_template("admin/admin.html", 
        user_count=user_count,
        active_tasks=lifetime_scans, 
        report_views=report_views,  
        storage_usage=storage_mb,
        progress=USER_PROGRESS,
        server_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )

# --- Reports Management --- #

@main_bp.route("/reports-list")
@login_required
def reports_list():
    uid = session['user_id']
    user_dir = get_user_temp_dir(uid)
    report_files = []
    # Collect all generated artifacts for listing
    if user_dir.exists():
        for pattern in ['*.html', '*.pdf', '*.csv']:
            for f in user_dir.glob(pattern):
                if f.is_file():
                    report_files.append(f.name)
    
    return render_template("reports/list.html", report_files=sorted(report_files, reverse=True))

@main_bp.route("/reports/<path:filename>")
@login_required
def serve_report(filename):
    uid = session['user_id']
    user_dir = get_user_temp_dir(uid) 
    is_download = request.args.get('dl') == '1'
    increment_global_stat("report_views")
    
    if filename.lower().endswith('.pdf'):
        mimetype = 'application/pdf'
    elif filename.lower().endswith('.csv'):
        mimetype = 'text/csv'
    else:
        mimetype = None
    
    return send_from_directory(
        str(user_dir), 
        filename, 
        as_attachment=is_download,
        mimetype=mimetype 
    )

@main_bp.route("/reports/delete/<path:filename>", methods=["POST"])
@login_required
def delete_report(filename):
    uid = session['user_id']
    user_dir = get_user_temp_dir(uid).resolve()

    # Reject any filename that isn't a plain, single-segment name
    if not filename or filename != os.path.basename(filename) or filename in ('.', '..'):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return 'Not Found', 404
        flash("File not found.", "error")
        return redirect(url_for('main.reports_list'))

    file_path = (user_dir / filename).resolve()

    # Defense in depth: even after the basename check above, then verify
    if user_dir not in file_path.parents:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return 'Not Found', 404
        flash("File not found.", "error")
        return redirect(url_for('main.reports_list'))

    if file_path.exists() and file_path.is_file():
        try:
            os.remove(file_path)
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return '', 200
            flash("Report deleted successfully.", "success")
        except Exception:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return 'Error', 500
            flash("Error: Could not delete file.", "error")
    else:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return 'Not Found', 404
        flash("File not found.", "error")

    return redirect(url_for('main.reports_list'))

# --- Trading Journal --- #

@main_bp.route("/journal")
@login_required
def trading_journal():
    uid = session['user_id']
    user_keys = get_user_keys(uid)
    drive_linked = "google_refresh_token" in user_keys
    
    stats = {"winrate": "0%", "best_trade": "--", "bias": "Neutral"}
    journal_history = [] 

    if drive_linked:
        try:
            # Sync journal data from Google Drive AppData folder
            creds = JournalEngine.get_creds(uid)
            if creds:
                service = JournalEngine.get_drive_service(creds)
                file_id = JournalEngine.initialize_journal(service, uid=uid)
                try:
                    journal_history = JournalEngine.load_journal(service, file_id)
                except HttpError:
                    # Cached file_id was stale 
                    update_user_keys(uid, {"journal_drive_file_id": firestore.DELETE_FIELD})
                    file_id = JournalEngine.initialize_journal(service, uid=uid)
                    journal_history = JournalEngine.load_journal(service, file_id)
                stats = JournalEngine.calculate_stats(journal_history)
                journal_history.reverse() 
        except Exception as e:
            print(f"⚠️ Journal Error: {e}")

    return render_template(
        "dashboard/trading_journal.html", 
        drive_linked=drive_linked,
        stats=stats,
        trades=journal_history,
        user_settings=user_keys
    )

# --- Service Worker & PWA --- #

@main_bp.route('/manifest.json')
def serve_manifest():
    return send_from_directory('static', 'manifest.json')

@main_bp.route('/sw.js')
def serve_sw():
    # Serve Service Worker from root to permit broad caching scope
    response = make_response(send_from_directory('static', 'sw.js'))
    response.headers['Content-Type'] = 'application/javascript'
    response.headers['Service-Worker-Allowed'] = '/'
    return response

# --- API & AI Integration --- #

@main_bp.route('/settings/save_ai_key', methods=['POST'])
@login_required
def save_ai_key():
    # Native form submission for Gemini API key persistence
    api_key = request.form.get('api_key', '').strip()
    
    if not api_key:
        flash('API Key cannot be empty.', 'error')
        return redirect(url_for('main.settings'))
        
    try:
        uid = session.get('user_id')
        update_user_keys(uid, {'gemini_key': api_key})
        flash('Gemini API Key saved successfully!', 'success')
    except Exception as e:
        print(f"Surgery Log Error: {e}")
        flash('Failed to update AI settings.', 'error')
        
    return redirect(url_for('main.settings'))

@main_bp.route("/journal/ai_context", methods=["POST"])
@login_required
def get_journal_ai_context():
    # Format filtered journal data for AI prompt injection
    try:
        data = request.get_json()
        filtered_trades = data.get('trades', [])
        context_markdown = JournalEngine.prepare_ai_payload(filtered_trades)
        
        return jsonify({
            "status": "success",
            "payload": context_markdown
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@main_bp.route("/api/ai/init_audit", methods=["POST"])
@login_required
def init_audit():
    data = request.get_json()
    csv_context = data.get('csv_context', '') 
    uid = session['user_id']
    
    # Validation: Ensure we aren't sending empty prompts
    if not csv_context:
        return jsonify({"status": "error", "message": "No data provided for audit."}), 400

    #  Frontend is now the source of truth for formatting.
    response_text = AiModalEngine.initialize_firebase_session(uid, csv_context)
    
    if "Error" in response_text:
        return jsonify({"status": "error", "message": response_text}), 400
        
    return jsonify({"status": "success", "response": response_text})

@main_bp.route("/api/ai/chat", methods=["POST"])
@login_required
def ai_chat():
    # Handle multi-turn conversation using Firebase-stored chat history
    prompt = request.get_json().get('prompt')
    uid = session['user_id']
    response_text = AiModalEngine.continue_firebase_chat(uid, prompt)
    
    return jsonify({"status": "success", "response": response_text})

@main_bp.route('/sitemap.xml')
def sitemap():
    pages = []
    today = datetime.now().strftime('%Y-%m-%d')
    
    # List of only PUBLIC endpoints for indexing
    public_endpoints = [
        ('main.index', '1.0', 'daily'),
        ('auth.login', '0.8', 'monthly'),
        ('auth.register', '0.8', 'monthly'),
        ('main.help_page', '0.7', 'weekly'),
        ('main.privacy_policy', '0.7', 'weekly')
    ]

    for endpoint, priority, freq in public_endpoints:
        pages.append({
            "loc": url_for(endpoint, _external=True),
            "lastmod": today,
            "changefreq": freq,
            "priority": priority
        })

    # Render from your new SEO template
    sitemap_xml = render_template('includes/sitemap_template.xml', pages=pages)
    response = make_response(sitemap_xml)
    response.headers["Content-Type"] = "application/xml"
    return response

@main_bp.route('/robots.txt')
def robots():
    sitemap_url = url_for('main.sitemap', _external=True)
    lines = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /dashboard", 
        "Disallow: /api/",
        f"Sitemap: {sitemap_url}"
    ]
    return make_response("\n".join(lines), 200, {'Content-Type': 'text/plain'})

@main_bp.route('/googlea10aea7d2db78dd5.html')
def google_verify():
    return send_from_directory('static', 'googlea10aea7d2db78dd5.html')

@main_bp.route('/watchlist')
@login_required
def watchlist_page():
    uid = session.get('user_id')
    user_data = get_user_keys(uid)
    if not isinstance(user_data, dict):
        user_data = {}
    watchlist = user_data.get('watchlist', [])
    try:
        watchlist = sorted(watchlist, key=lambda x: x.get('added_at', ""), reverse=True)
    except Exception as e:
        print(f"Sort Error: {e}")
        watchlist = []
    return render_template('reports/watchlist.html', watchlist=watchlist)