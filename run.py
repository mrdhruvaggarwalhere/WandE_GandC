#!/usr/bin/env python3
"""
Entry point to launch the G&C Central Deal and Brokerage Automation Platform.
"""

import sys
import os

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import init_db
from app.core.seed_data import seed_all
from app.server import start_server

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"Initializing database and seeding master data...")
    init_db()
    seed_all()
    print(f"===========================================================")
    print(f"  G&C Central Deal and Brokerage Automation Platform")
    print(f"  Server starting at: http://localhost:{port}")
    print(f"===========================================================")
    start_server(port)
