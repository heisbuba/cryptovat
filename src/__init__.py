import os
from datetime import timedelta
from flask import Flask
from flask_wtf import CSRFProtect
# Import our configuration logic
from .config import init_firebase, FIREBASE_WEB_API_KEY
from werkzeug.middleware.proxy_fix import ProxyFix
def create_app():
    app = Flask(__name__)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
    secret_key = os.environ.get('FLASK_SECRET_KEY')
    if not secret_key:
        print("⚠️  FLASK_SECRET_KEY not set — using a random key for this process. "
              "All sessions will be invalidated on every restart. Set FLASK_SECRET_KEY "
              "in your environment for stable, persistent sessions.")
        secret_key = os.urandom(24).hex()
    app.secret_key = secret_key
    # Cookie settings
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
    app.config['SESSION_REFRESH_EACH_REQUEST'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['SESSION_COOKIE_SECURE'] = True
    # Cap request body size (uploads, JSON payloads)
    app.config['MAX_CONTENT_LENGTH'] = 25 * 1024 * 1024
    # CSRF protection for all state-changing (POST/PUT/PATCH/DELETE) routes.
    app.config['WTF_CSRF_TIME_LIMIT'] = None
    CSRFProtect(app)
    # Baseline security headers.
    @app.after_request
    def set_security_headers(response):
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        # frame-ancestors allowlist instead of X-Frame-Options
        response.headers.setdefault(
            'Content-Security-Policy',
            "frame-ancestors 'self' https://huggingface.co https://*.hf.space"
        )
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        return response
    # Initialize Database
    try:
        init_firebase()
    except Exception as e:
        print(f"❌ FATAL: {e}")
    
    # Register Blueprints
    from .blueprints.auth import auth_bp
    from .blueprints.main import main_bp
    from .blueprints.tasks import tasks_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(tasks_bp)
    return app