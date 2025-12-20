import os
import signal
import threading
import time
from flask import Blueprint, request, redirect, render_template_string, url_for
from utils import update_config_file
import config
from templates import SETUP_TEMPLATE, SETTINGS_TEMPLATE

setup_bp = Blueprint('setup', __name__)

@setup_bp.route("/setup")
def setup_page():
    return render_template_string(SETUP_TEMPLATE, 
        cmc=config.CMC_API_KEY, lcw=config.LIVECOINWATCH_API_KEY, 
        cr=config.COINRANKINGS_API_KEY, html2pdf=config.HTML2PDF_API_KEY, vtmr=config.COINALYZE_VTMR_URL)

@setup_bp.route("/settings")
def settings_page():
    return render_template_string(SETTINGS_TEMPLATE, 
        cmc=config.CMC_API_KEY, lcw=config.LIVECOINWATCH_API_KEY, 
        cr=config.COINRANKINGS_API_KEY, html2pdf=config.HTML2PDF_API_KEY, vtmr=config.COINALYZE_VTMR_URL)

@setup_bp.route("/save-config", methods=["POST"])
def save_config():
    action = request.form.get("action")
    update_config_file({
        "CMC_API_KEY": request.form.get("cmc_key"),
        "LIVECOINWATCH_API_KEY": request.form.get("lcw_key"),
        "COINRANKINGS_API_KEY": request.form.get("cr_key"),
        "HTML2PDF_API_KEY": request.form.get("html2pdf_key"),
        "COINALYZE_VTMR_URL": request.form.get("vtmr_url")
    })
    
    if action == "quit":
        return redirect(url_for('setup.shutdown_page_visual'))
    
    return redirect('/')

@setup_bp.route("/factory-reset")
def factory_reset():
    update_config_file({
        "CMC_API_KEY": "CONFIG_REQUIRED_CMC",
        "LIVECOINWATCH_API_KEY": "CONFIG_REQUIRED_LCW",
        "COINRANKINGS_API_KEY": "CONFIG_REQUIRED_CR",
        "HTML2PDF_API_KEY": "CONFIG_REQUIRED_HTML2PDF",
        "COINALYZE_VTMR_URL": "CONFIG_VTMR_URL"
    })
    return redirect(url_for('setup.setup_page'))

@setup_bp.route("/shutdown", methods=['GET', 'POST'])
def shutdown():
    os.kill(os.getpid(), signal.SIGINT)
    return "Server shutting down..."

@setup_bp.route("/shutdown-page")
def shutdown_page_visual():
    def kill_me():
        time.sleep(1)
        os.kill(os.getpid(), signal.SIGINT)
    threading.Thread(target=kill_me).start()
    
    return f"""<!DOCTYPE html><html>
    <head><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{{background:#0b0e11;color:#eaecef;font-family:sans-serif;display:flex;justify-content:center;align-items:center;height:100vh;flex-direction:column;text-align:center;}}</style></head>
    <body><h2 style='color:#0ecb81;'>Configuration Saved</h2><p>Application Terminated.<br>You can close this window now.</p></body></html>"""