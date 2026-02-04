import os
import sqlite3
import sys

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from database import init_db, DB_PATH
from auth import hash_password
from super_admin_manager import save_super_admin

def setup_production_db():
    print(f"Initializing clean database at: {DB_PATH}")
    
    # If DB exists, delete it
    if os.path.exists(DB_PATH):
        print("Removing existing database...")
        os.remove(DB_PATH)
    
    # Create directory if not exists
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    # Initialize schema and default admin
    init_db()
    
    print("Database initialized with super admin (vladpos / V!adp0s)")
    print("Ready for production packaging.")

if __name__ == "__main__":
    setup_production_db()
