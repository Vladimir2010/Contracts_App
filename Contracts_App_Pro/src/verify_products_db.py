from database import init_db, get_connection, get_all_products
import sqlite3

def verify():
    print("Initializing Database...")
    init_db()
    
    con = get_connection()
    cur = con.cursor()
    
    print("\nChecking products table schema:")
    cur.execute("PRAGMA table_info(products)")
    columns = {r[1]: r[2] for r in cur.fetchall()}
    
    required = ["name", "category", "price", "currency", "description", "last_modified", "is_deleted", "created_at", "updated_at"]
    missing = [c for c in required if c not in columns]
    
    if missing:
        print(f"❌ Missing columns: {missing}")
    else:
        print("✅ All required columns present.")
        
    print("\nTesting get_all_products()...")
    try:
        products = get_all_products()
        print(f"✅ Successfully loaded {len(products)} products.")
    except Exception as e:
        print(f"❌ Failed to load products: {e}")
        
    con.close()

if __name__ == "__main__":
    verify()
