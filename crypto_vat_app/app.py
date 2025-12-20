import os
import threading
from flask import Flask
import config
from utils import setup_logging, load_config_from_file
from routes.auth import auth_bp
from routes.setup import setup_bp
from routes.core import core_bp

# Initialize Flask App
app = Flask(__name__)
app.secret_key = "v5_cloud_ultra_secret"

# Register Blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(setup_bp)
app.register_blueprint(core_bp)

# Run Startup Tasks
setup_logging()
load_config_from_file()
config.FirebaseHelper.initialize()

if __name__ == "__main__":
    print(f"\n{'='*60}")
    print("CRYPTO VOLUME ANALYSIS TOOLKIT v5.0 (CLOUD EDITION)")
    print(f"{'='*60}")
    print("Dashboard accessible via Deployment URL")
    print(f"{'='*60}")
    
    # Get PORT from environment (Required for Koyeb/Render)
    port = int(os.environ.get("PORT", 5000))
    
    # Run Server
    app.run(host="0.0.0.0", port=port, debug=True, use_reloader=False)