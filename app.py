#!/usr/bin/env python3
from src import create_app

app = create_app()

if __name__ == "__main__":
    print(f"\n{'='*60}")
    print("CRYPTO VOLUME ANALYSIS TOOLKIT - CLOUD EDITION")
    print(f"{'='*60}")
    
    app.run(host="0.0.0.0", port=7860, debug=False)