# ==============================
# WEB UI TEMPLATES
# ==============================
COMMON_HEAD = """
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Crypto Volume Analysis Toolkit</title>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Inter:wght@400;600;800&display=swap" rel="stylesheet">
    <style>
        :root { --bg-dark:#0b0e11; --bg-card:#151a1e; --text-main:#eaecef; --text-dim:#848e9c; --accent-green:#0ecb81; --accent-blue:#3b82f6; --accent-orange:#f59e0b; --accent-red:#f6465d; --border:#2b3139; --input-bg:#1e252a; }
        body { margin:0; background:var(--bg-dark); color:var(--text-main); font-family:'Inter',sans-serif; }
        .container { max-width:600px; margin:0 auto; padding:20px; }
        .card { background:var(--bg-card); padding:25px; border-radius:12px; border:1px solid var(--border); margin-bottom:20px; }
        h1 { color:var(--accent-green); text-align:center; font-size:1.4rem; margin-bottom:10px; }
        h2 { color:var(--accent-blue); font-size:1.1rem; margin-top:20px; }
        input[type="text"], input[type="email"], input[type="password"] { width:100%; padding:12px; background:var(--input-bg); border:1px solid var(--border); color:#fff; border-radius:8px; font-family:monospace; margin-top:5px; box-sizing:border-box; }
        .btn, .btn-reset, .btn-share, .btn-update {display:block; width:100%; padding:15px; border:none; border-radius:8px; font-weight:800; cursor:pointer; text-align:center; text-decoration:none; margin-top:10px; font-size:0.95rem; }
        .btn-green { background:var(--accent-green); color:#000; }
        .btn-blue { background:var(--bg-card); border:1px solid var(--accent-blue); color:var(--accent-blue); }
        .btn-red { background:rgba(246,70,93,0.1); border:1px solid var(--accent-red); color:var(--accent-red); }
        .link { color:var(--accent-blue); text-decoration:none; font-size:0.85rem; float:right; }
        .error { color:var(--accent-red); margin-bottom:10px; text-align:center; }
        .grid-buttons { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
        .back-link { display:block; text-align:center; margin-top:20px; color:var(--text-dim); text-decoration:none; }
    </style>
</head>
"""

# [FIX] Added COMMON_HEAD to Auth Templates to ensure they inherit the styles
LOGIN_TEMPLATE = f"""<!DOCTYPE html><html>{COMMON_HEAD}<body>
    <div style="display:flex; height:100vh; align-items:center; justify-content:center;">
        <div class="card" style="width:100%; max-width:400px;">
            <h1>🔐 Login</h1>
            {{% if error %}}<div class="error">{{{{ error }}}}</div>{{% endif %}}
            <form method="POST">
                <label>Email</label>
                <input type="email" name="email" required>
                <label style="margin-top:10px; display:block;">Password</label>
                <input type="password" name="password" required>
                <button class="btn btn-green" type="submit">ENTER TOOLKIT</button>
            </form>
            <a href="/signup" class="link" style="float:none; display:block; text-align:center; margin-top:15px;">Create an Account</a>
        </div>
    </div>
</body></html>"""

SIGNUP_TEMPLATE = f"""<!DOCTYPE html><html>{COMMON_HEAD}<body>
    <div style="display:flex; height:100vh; align-items:center; justify-content:center;">
        <div class="card" style="width:100%; max-width:400px;">
            <h1>🚀 New Account</h1>
            {{% if error %}}<div class="error">{{{{ error }}}}</div>{{% endif %}}
            <form method="POST">
                <label>Email</label>
                <input type="email" name="email" required>
                <label style="margin-top:10px; display:block;">Password</label>
                <input type="password" name="password" required>
                <button class="btn btn-green" type="submit">SIGN UP</button>
            </form>
            <a href="/login" class="link" style="float:none; display:block; text-align:center; margin-top:15px;">Back to Login</a>
        </div>
    </div>
</body></html>"""

ADMIN_TEMPLATE = f"""<!DOCTYPE html><html>{COMMON_HEAD}<body>
    <div class="container">
        <h1>🛡️ Admin Dashboard</h1>
        <div class="card">
            <h3>Statistics</h3>
            <p>Recent Actions: <strong>{{{{ log_count }}}}</strong></p>
        </div>
        <div class="card">
            <h3>Live Activity Log</h3>
            <div style="max-height:400px; overflow-y:auto;">
                {{% for log in logs %}}
                <div style="border-bottom:1px solid var(--border); padding:10px 0;">
                    <span style="color:var(--accent-blue);">{{{{ log.uid[:8] }}}}...</span> 
                    <span style="float:right; color:var(--text-dim);">{{{{ log.timestamp }}}}</span>
                    <br>{{{{ log.action }}}}
                </div>
                {{% endfor %}}
            </div>
        </div>
        <a href="/" class="link" style="float:none; text-align:center; display:block;">← Back to App</a>
    </div>
</body></html>"""

# Original Templates from your upload (retained)
HOME_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Crypto VAT Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Inter:wght@400;600;800&display=swap" rel="stylesheet">
    <style>
        :root { --bg-dark: #0b0e11; --bg-card: #151a1e; --text-main: #eaecef; --text-dim: #848e9c; --accent-green: #0ecb81; --accent-blue: #3b82f6; --accent-purple: #9333ea; --accent-orange: #f59e0b; --border: #2b3139; --accent-red: #f6465d; }
        * { box-sizing: border-box; }
        body { margin:0; background:var(--bg-dark); color:var(--text-main); font-family:'Inter', sans-serif; display:flex; flex-direction:column; min-height:100vh; }
        .header, .footer { padding:20px; background:var(--bg-card); border-bottom:1px solid var(--border); display:flex; justify-content:space-between; align-items:center; }
        .header h1 { margin:0; font-size:1.1rem; color:var(--accent-green); }
        .icon-btn { color:var(--text-dim); text-decoration:none; font-size:1.2rem; padding:0 10px; }
        .footer p { margin:0; text-align:center; font-size:0.9rem; color:var(--accent-green); }
        .container { flex:1; padding:20px; max-width:600px; margin:0 auto; width:100%; }
        .grid { display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-top:20px; }
        .btn { background:var(--bg-card); border:1px solid var(--border); color:var(--text-main); padding:20px; border-radius:12px; font-weight:600; text-align:center; cursor:pointer; text-decoration:none; display:flex; flex-direction:column; align-items:center; gap:8px; }
        .btn svg { width:24px; height:24px; margin-bottom:5px; }
        .btn-spot { border-color:var(--accent-blue); color:var(--accent-blue); }
        .btn-futures { border-color:var(--accent-orange); color:var(--accent-orange); }
        .btn-adv { border-color:var(--accent-green); color:var(--accent-green); }
        .btn-report { border-color:var(--accent-purple); color:var(--accent-purple); }
        .terminal { background:#000; padding:15px; border-radius:12px; border:1px solid var(--border); font-family:'JetBrains Mono', monospace; font-size:0.75rem; color:var(--text-dim); height:200px; overflow-y:auto; margin-top:20px; }
        .log-line { margin-bottom:4px; }
        .log-line.highlight { color:#fff; border-left:2px solid var(--accent-green); padding-left:5px; }
        .log-line.error { color:#f6465d; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Crypto VAT v5.0</h1>
        <div>
            <a href="/help" class="icon-btn">?</a>
            <a href="/settings" class="icon-btn">⚙️</a>
            <a href="/logout" class="icon-btn" title="Logout">🚪</a>
        </div>
    </div>
    
    <div class="container">
        <div class="grid">
            <button class="btn btn-spot" onclick="trigger('/run-spot')">
                <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"></path></svg>
                SPOT SCAN
            </button>
            <a class="btn btn-futures" href="/get-futures-data">
                <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"></path></svg>
                GET FUTURES
            </a>
            <button class="btn btn-adv" onclick="trigger('/run-advanced')">
                <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path></svg>
                ADVANCED
            </button>
            <a class="btn btn-report" href="/reports-list">
                <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>
                REPORTS
            </a>
        </div>

        <div style="margin-top:20px; display:flex; justify-content:space-between; align-items:center;">
            <span style="font-size:0.8rem; color:var(--text-dim);">STATUS</span>
            <span id="percent" style="font-size:0.8rem; font-weight:bold; color:var(--accent-green);">0%</span>
        </div>
        <div style="height:4px; background:#2b3139; border-radius:2px; margin-top:5px; overflow:hidden;">
            <div id="bar" style="height:100%; width:0%; background:var(--accent-green); transition:width 0.3s;"></div>
        </div>

        <div class="terminal" id="term">
            <div class="log-line">> System Initialized...</div>
        </div>
        <br>

   <div class="footer">
        <p style="color:#fff;">© 2025 | Made with 💚 4rm Nigeria.</p>
    </div>
    <script>
        let busy = false; let lastIdx = 0;
        
        function trigger(url) {
            if (busy) return;
            busy = true; 
            document.getElementById('term').innerHTML = ''; 
            lastIdx = 0; 
            document.getElementById('bar').style.width='5%';
            document.getElementById('percent').innerText='5%';
            fetch(url).then(r=>r.json()).then(()=>{ poll(); logs(); }).catch(()=>{ busy=false; });
        }
        function poll() {
            fetch('/progress').then(r=>r.json()).then(d=>{
                document.getElementById('bar').style.width=d.percent+'%';
                document.getElementById('percent').innerText=d.percent+'%';
                if(d.status==='active') setTimeout(poll,800); else busy=false;
            });
        }
        function logs() {
            fetch('/logs-chunk?last='+lastIdx).then(r=>r.json()).then(d=>{
                if(d.logs.length){
                    lastIdx=d.last_index;
                    d.logs.forEach(l=>{
                        let div=document.createElement('div');
                        div.className='log-line '+(l.includes('Error')?'error':l.includes('Found')?'highlight':'');
                        div.innerText='> '+l;
                        document.getElementById('term').appendChild(div);
                    });
                    document.getElementById('term').scrollTop=9999;
                }
                if(busy) setTimeout(logs,1000);
            });
        }
    </script>
</body></html>"""

FUTURES_INSTRUCTIONS_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Get Futures Data</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap" rel="stylesheet">
    <style>
        body { background-color: #0b0e11; color: #eaecef; font-family: 'Inter', sans-serif; padding: 20px; text-align: center; }
        .container { max-width: 640px; margin: 0 auto; background: #151a1e; padding: 30px; border-radius: 12px; border: 1px solid #2b3139; }
        h1 { color: #f59e0b; }
        .btn { background: #f59e0b; color: #000; padding: 15px 25px; border-radius: 8px; text-decoration: none; font-weight: bold; display: inline-block; margin-top: 20px; border: none; cursor: pointer; font-size: 1rem; }
        .btn-upload { background: transparent; border: 1px solid #f59e0b; color: #f59e0b; width: 100%; margin-top: 10px; }
        .instruction-list { text-align: left; margin-top: 20px; line-height: 1.6; color: #848e9c; }
        li { margin-bottom: 10px; }
        input[type="file"] { background: #1e252a; color: #848e9c; padding: 10px; border-radius: 8px; border: 1px dashed #2b3139; width: 100%; margin-top: 15px; box-sizing: border-box; }
        .divider { height: 1px; background: #2b3139; margin: 30px 0; position: relative; }
        .divider span { position: absolute; top: -12px; left: 50%; transform: translateX(-50%); background: #151a1e; padding: 0 15px; color: #2b3139; font-weight: bold; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 Get Futures Data</h1>
        <p>Follow these steps to analyze futures data.</p>
        
        <div class="instruction-list">
            <ol>
                <li>Click <strong>Open VTMR View</strong> to view data on Coinalyze.</li>
                <li>In Chrome: <strong>Menu (⋮) → Share → Print → Save as PDF</strong>.</li>
                <li>Return here and <strong>Upload</strong> that PDF file below.</li>
                <li>Go back to Dashboard and run <strong>Advanced Analysis</strong>.</li>
            </ol>
        </div>

        <a href="{{ FUTURES_URL }}" target="_blank" class="btn">1. OPEN VTMR VIEW</a>

        <div class="divider"><span>THEN</span></div>

        <form action="/upload-futures" method="POST" enctype="multipart/form-data">
            <p style="text-align:left; font-size:0.9rem; color:#848e9c; margin-bottom:5px;">2. Upload the saved PDF:</p>
            <input type="file" name="futures_pdf" accept=".pdf" required>
            <button type="submit" class="btn btn-upload">UPLOAD & CONTINUE</button>
        </form>

        <br>
        <a href="/" style="color: #3b82f6; text-decoration:none; font-size:0.9rem;">← Back to Dashboard</a>
    </div>
</body>
</html>
"""

REPORT_LIST_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Reports</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap" rel="stylesheet">
    <style>
        body { background-color: #0b0e11; color: #eaecef; font-family: 'Inter', sans-serif; padding: 20px; }
        .container { max-width: 600px; margin: 0 auto; }
        h1 { text-align: center; color: #9333ea; }
        .file-item { background: #151a1e; padding: 15px; border-radius: 8px; border: 1px solid #2b3139; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; }
        .btn { background: #9333ea; color: #fff; padding: 8px 12px; border-radius: 4px; text-decoration: none; font-size: 0.8rem; }
        .back { display: block; text-align: center; margin-top: 20px; color: #3b82f6; text-decoration: none; }
    </style>
</head>
<body>
    <div class="container">
        <h1>All Analysis Reports</h1>
        {% for file in files %}
        <div class="file-item">
            <span>{{ file.name }}</span>
            <a href="{{ file.url }}" target="_blank" class="btn">OPEN</a>
        </div>
        {% else %}
        <p style="text-align:center; color:#848e9c;">No reports found.</p>
        {% endfor %}
        <a href="/" class="back">← Back to Dashboard</a>
    </div>
</body>
</html>
"""

SETUP_TEMPLATE = f"""<!DOCTYPE html><html>{COMMON_HEAD}<body>
    <div class="container">
        <h1>⚙️ Setup Wizard</h1>
        <form action="/save-config" method="POST">
            <div class="card">
                <h2>1. API Keys Setup</h2>
                <label>CoinMarketCap Key</label>
                <input type="text" name="cmc_key" value="{{{{ cmc }}}}" placeholder="Paste CMC Key...">
                <label style="margin-top:15px; display:block;">LiveCoinWatch Key</label>
                <input type="text" name="lcw_key" value="{{{{ lcw }}}}" placeholder="Paste LCW Key...">
                <label style="margin-top:15px; display:block;">CoinRanking Key</label>
                <input type="text" name="cr_key" value="{{{{ cr }}}}" placeholder="Paste CR Key...">
                <label style="margin-top:15px; display:block;">HTML2PDF Key</label>
                <input type="text" name="html2pdf_key" value="{{{{ html2pdf }}}}" placeholder="Paste HTML2PDF Key...">
            </div>
            <div class="card">
                <h2>2. CoinAlyze Setup</h2>
                <label>VTMR URL</label>
                <input type="text" name="vtmr_url" value="{{{{ vtmr }}}}" placeholder="https://coinalyze.net/?columns=...">
            </div>
            <button type="submit" class="btn btn-green">SAVE CONFIGURATION</button>
        </form>
    </div>
</body></html>"""

SETTINGS_TEMPLATE = SETUP_TEMPLATE.replace("Setup Wizard", "Settings").replace("SAVE CONFIGURATION", "UPDATE SETTINGS")

HELP_TEMPLATE = f"""<!DOCTYPE html><html>{COMMON_HEAD}<body>
    <div class="container">
        <h1>📚 Help & Info</h1>
        <div class="card">
            <h2>About Crypto VAT v5.0</h2>
            <p><strong>Crypto Volume Analysis Toolkit v5.0 (Cloud)</strong><br>Tracks high-volume tokens using Spot + Futures cross-market analysis.</p>
        </div>
        <div class="card">
            <h2>Links</h2>
            <a href="https://github.com/heisbuba/crypto-volume-analysis-toolkit" class="btn btn-blue" target="_blank">GitHub</a>
        </div>
        <a href="/" style="color:#3b82f6;" class="link" style="float:none;text-align:center;display:block;">← Back to Dashboard</a>
    </div>
</body></html>"""