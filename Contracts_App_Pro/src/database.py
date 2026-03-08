import sqlite3
import os
from typing import Optional, List, Dict, Tuple, Any
from datetime import datetime
import uuid
from path_utils import get_app_root, get_data_root
DB_PATH = os.path.join(get_data_root(), "data", "contracts.db")


def get_connection():
    """Get database connection"""
    try:
        # Ensure data directory exists
        db_dir = os.path.dirname(DB_PATH)
        if not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        # Register custom LOWER function to support Cyrillic case-insensitivity
        conn.create_function("LOWER", 1, lambda s: s.lower() if s is not None else None)
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        raise

def ensure_column_exists(table: str, column: str, type_def: str, default_val: Any = None):
    """Helper to add a column if it doesn't exist"""
    con = get_connection()
    cur = con.cursor()
    try:
        cur.execute(f"PRAGMA table_info({table})")
        cols = [c[1] for c in cur.fetchall()]
        if column not in cols:
            print(f"Adding column {column} to {table}...")
            # 1. Add column without DEFAULT to avoid syntax issues with functions in ALTER TABLE
            alter_query = f"ALTER TABLE {table} ADD COLUMN {column} {type_def}"
            cur.execute(alter_query)
            con.commit()
            
            # 2. Apply default value if provided using a separate UPDATE
            if default_val is not None:
                print(f"Setting default value for {column} in {table}...")
                if isinstance(default_val, str) and not ('(' in default_val and ')' in default_val):
                    update_val = f"'{default_val}'"
                else:
                    update_val = str(default_val)
                
                cur.execute(f"UPDATE {table} SET {column} = {update_val} WHERE {column} IS NULL")
                con.commit()
                
            print(f"Column {column} added to {table} successfully.")
    except Exception as e:
        print(f"Error adding column {column} to {table}: {e}")
    finally:
        con.close()


def init_db():
    """Initialize database with all tables"""
    try:
        con = get_connection()
        cur = con.cursor()

        # 1. Table Creation (Base Schema)
        
        # Clients table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contract_number TEXT NOT NULL,
                status TEXT,
                contract_start DATE,
                contract_expiry DATE,
                company_name TEXT NOT NULL,
                city TEXT,
                postal_code TEXT,
                address TEXT,
                eik TEXT,
                vat_registered TEXT,
                mol TEXT,
                phone1 TEXT,
                phone2 TEXT,
                last_modified TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                is_deleted INTEGER DEFAULT 0
            )
        """)

        # Devices table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL,
                fdrid TEXT,
                euro_done INTEGER DEFAULT 0,
                object_name TEXT,
                object_address TEXT,
                object_phone TEXT,
                model TEXT,
                certificate_number TEXT,
                certificate_expiry DATE,
                serial_number TEXT,
                fiscal_memory TEXT,
                nra_report_enabled INTEGER DEFAULT 1,
                nra_report_month TEXT,
                nra_td TEXT DEFAULT 'СОФИЯ',
                bim_model TEXT,
                bim_date DATE,
                maintenance_price REAL DEFAULT 0,
                last_renewed_at DATE,
                created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                last_modified TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                is_deleted INTEGER DEFAULT 0,
                FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
            )
        """)

        # Certificates table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS certificates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                number TEXT UNIQUE NOT NULL,
                expiry_date DATE,
                last_modified TIMESTAMP DEFAULT (datetime('now', 'localtime'))
            )
        """)

        # Users table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT,
                role TEXT DEFAULT 'user',
                last_modified TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                created_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
            )
        """)

        # Global Settings table (Synchronized)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS global_settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                last_modified TIMESTAMP DEFAULT (datetime('now', 'localtime'))
            )
        """)

        # Products table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uuid TEXT UNIQUE,
                name TEXT NOT NULL,
                category TEXT,
                price REAL NOT NULL,
                currency TEXT DEFAULT 'BGN',
                description TEXT,
                last_modified TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
            )
        """)

        # Audit Logs table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                action TEXT NOT NULL,
                details TEXT,
                contract_number TEXT,
                device_id INTEGER,
                timestamp TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
            )
        """)

        # Repair History table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS repair_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id INTEGER NOT NULL,
                problem_description TEXT,
                repair_date DATE,
                protocol_path TEXT,
                last_modified TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE
            )
        """)

        # Invoices table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uuid TEXT UNIQUE,
                number TEXT NOT NULL,
                type TEXT DEFAULT 'INV',
                client_id INTEGER,
                client_name TEXT,
                client_eik TEXT,
                client_vat TEXT,
                client_address TEXT,
                client_mol TEXT,
                date_issued DATE,
                date_due DATE,
                total_base REAL DEFAULT 0,
                total_vat REAL DEFAULT 0,
                total_amount REAL DEFAULT 0,
                vat_rate REAL DEFAULT 20,
                currency TEXT DEFAULT 'BGN',
                payment_status TEXT DEFAULT 'PENDING',
                payment_method TEXT DEFAULT 'BANK',
                is_paid INTEGER DEFAULT 0,
                notes TEXT,
                created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                last_modified TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                is_deleted INTEGER DEFAULT 0,
                FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE SET NULL
            )
        """)

        # Counterparties table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS counterparties (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                eik TEXT,
                address TEXT,
                mol TEXT,
                phone TEXT,
                last_modified TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                is_deleted INTEGER DEFAULT 0
            )
        """)

        # Handover Protocols table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS handover_protocols (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                protocol_date DATE,
                technician_egn TEXT,
                capacity TEXT,
                counterparty_id INTEGER,
                description TEXT,
                notes TEXT,
                ref_number TEXT,
                docx_path TEXT,
                last_modified TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                is_deleted INTEGER DEFAULT 0,
                FOREIGN KEY (counterparty_id) REFERENCES counterparties(id)
            )
        """)

        # Invoice items table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS invoice_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id INTEGER,
                description TEXT,
                quantity REAL DEFAULT 1,
                unit_price REAL DEFAULT 0,
                total_price REAL DEFAULT 0,
                FOREIGN KEY(invoice_id) REFERENCES invoices(id) ON DELETE CASCADE
            )
        """)

        con.commit()
        
        # 2. Sequential Migrations (Using ensure_column_exists for total isolation)
        
        # Devices migrations
        ensure_column_exists("devices", "created_at", "TIMESTAMP", "datetime('now', 'localtime')")
        ensure_column_exists("devices", "updated_at", "TIMESTAMP", "datetime('now', 'localtime')")
        ensure_column_exists("devices", "nra_report_enabled", "INTEGER DEFAULT 1")
        ensure_column_exists("devices", "nra_report_month", "TEXT")
        ensure_column_exists("devices", "nra_td", "TEXT", "СОФИЯ")
        ensure_column_exists("devices", "bim_model", "TEXT")
        ensure_column_exists("devices", "bim_date", "DATE")
        ensure_column_exists("devices", "maintenance_price", "REAL DEFAULT 0")
        ensure_column_exists("devices", "last_renewed_at", "DATE")
        ensure_column_exists("devices", "last_modified", "TIMESTAMP", "datetime('now', 'localtime')")
        ensure_column_exists("devices", "is_deleted", "INTEGER DEFAULT 0")

        # Clients migrations
        ensure_column_exists("clients", "last_modified", "TIMESTAMP", "datetime('now', 'localtime')")
        ensure_column_exists("clients", "is_deleted", "INTEGER DEFAULT 0")

        # Audit Logs migrations
        ensure_column_exists("audit_logs", "contract_number", "TEXT")
        ensure_column_exists("audit_logs", "device_id", "INTEGER")
        ensure_column_exists("audit_logs", "last_modified", "TIMESTAMP", "datetime('now', 'localtime')")

        # Users migrations
        ensure_column_exists("users", "role", "TEXT", "user")
        ensure_column_exists("users", "last_modified", "TIMESTAMP", "datetime('now', 'localtime')")

        # Products migrations
        ensure_column_exists("products", "uuid", "TEXT")
        ensure_column_exists("products", "last_modified", "TIMESTAMP", "datetime('now', 'localtime')")
        ensure_column_exists("products", "is_deleted", "INTEGER DEFAULT 0")
        ensure_column_exists("products", "created_at", "TIMESTAMP", "datetime('now', 'localtime')")
        ensure_column_exists("products", "updated_at", "TIMESTAMP", "datetime('now', 'localtime')")
        
        # Invoices migrations
        ensure_column_exists("invoices", "uuid", "TEXT")
        ensure_column_exists("invoices", "last_modified", "TIMESTAMP", "datetime('now', 'localtime')")
        ensure_column_exists("invoices", "is_deleted", "INTEGER DEFAULT 0")

        # Invoice items migrations (simple sync: they follow parent invoice)
        ensure_column_exists("invoice_items", "last_modified", "TIMESTAMP", "datetime('now', 'localtime')")

        # Counterparties migrations
        ensure_column_exists("counterparties", "uuid", "TEXT")
        ensure_column_exists("counterparties", "last_modified", "TIMESTAMP", "datetime('now', 'localtime')")
        ensure_column_exists("counterparties", "is_deleted", "INTEGER DEFAULT 0")

        # Handover Protocols migrations
        ensure_column_exists("handover_protocols", "uuid", "TEXT")
        ensure_column_exists("handover_protocols", "last_modified", "TIMESTAMP", "datetime('now', 'localtime')")
        ensure_column_exists("handover_protocols", "is_deleted", "INTEGER DEFAULT 0")

        # Repair History migrations
        ensure_column_exists("repair_history", "last_modified", "TIMESTAMP", "datetime('now', 'localtime')")

        # Certificates migrations
        ensure_column_exists("certificates", "last_modified", "TIMESTAMP", "datetime('now', 'localtime')")

        # Global Settings migrations
        ensure_column_exists("global_settings", "last_modified", "TIMESTAMP", "datetime('now', 'localtime')")

        # Other initializations (Admin user, indexes)
        con = get_connection()
        cur = con.cursor()
        
        cur.execute("CREATE INDEX IF NOT EXISTS idx_contract_number ON clients(contract_number)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_eik ON clients(eik)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_serial ON devices(serial_number)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_client_id ON devices(client_id)")
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_product_uuid ON products(uuid)")
        
        cur.execute("SELECT count(*) FROM users")
        if cur.fetchone()[0] == 0:
            try:
                from auth import hash_password
                from super_admin_manager import save_super_admin
                pwd_hash = hash_password("V!adp0s")
                cur.execute("""
                    INSERT INTO users (username, password_hash, full_name, role, last_modified)
                    VALUES (?, ?, ?, ?, datetime('now', 'localtime'))
                """, ("vladpos", pwd_hash, "Администратор", "admin"))
                con.commit()
                save_super_admin("vladpos", pwd_hash, "Администратор")
            except Exception as e:
                print(f"Error creating default admin: {e}")
        
        con.commit()
        
        # Generate UUIDs for projects, counterparties, protocols that don't have them
        for table in ["products", "invoices", "counterparties", "handover_protocols"]:
            cur.execute(f"SELECT id FROM {table} WHERE uuid IS NULL")
            rows = cur.fetchall()
            for row in rows:
                new_uuid = str(uuid.uuid4())
                cur.execute(f"UPDATE {table} SET uuid = ? WHERE id = ?", (new_uuid, row[0]))
        con.commit()
        
        # Migrate settings from JSON if table is empty
        cur.execute("SELECT count(*) FROM global_settings")
        if cur.fetchone()[0] == 0:
            from path_utils import get_app_root, get_data_root
            settings_path = os.path.join(get_data_root(), "data", "settings.json")
            if os.path.exists(settings_path):
                import json
                try:
                    with open(settings_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        for k, v in data.items():
                            # Only migrate non-local keys
                            if k not in ['server_url', 'mode', 'last_sync_time', 'autorun']:
                                cur.execute("INSERT OR REPLACE INTO global_settings (key, value, last_modified) VALUES (?, ?, ?)", 
                                           (k, str(v), now_str))
                    con.commit()
                except Exception as e:
                    print(f"Migration error: {e}")

        con.close()
        print("Database initialization and migration completed successfully.")

    except Exception as e:
        print(f"CRITICAL: Database initialization failed: {e}")
        if con: con.close()
# ============= CLIENT OPERATIONS =============

def add_client(data: Dict[str, Any]) -> int:
    """Add new client and return client_id"""
    con = None
    try:
        con = get_connection()
        cur = con.cursor()
        
        cur.execute("""
            INSERT INTO clients (
                contract_number, status, contract_start, contract_expiry,
                company_name, city, postal_code, address,
                eik, vat_registered, mol, phone1, phone2,
                last_modified
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get('contract_number'),
            data.get('status'),
            data.get('contract_start'),
            data.get('contract_expiry'),
            data.get('company_name'),
            data.get('city'),
            data.get('postal_code'),
            data.get('address'),
            data.get('eik'),
            data.get('vat_registered'),
            data.get('mol'),
            data.get('phone1'),
            data.get('phone2'),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))
        
        client_id = cur.lastrowid
        con.commit()
        return client_id
    except Exception as e:
        print(f"Error adding client: {e}")
        if con: con.rollback()
        return -1
    finally:
        if con: con.close()


def update_client(client_id: int, data: Dict[str, Any], user_id: Optional[int] = None, username: str = "SYSTEM") -> bool:
    """Update existing client data"""
    con = None
    try:
        # Get old data for audit
        old_data = None
        con_temp = get_connection()
        cur_temp = con_temp.cursor()
        cur_temp.execute("SELECT * FROM clients WHERE id = ?", (client_id,))
        row = cur_temp.fetchone()
        if row:
            columns = [col[0] for col in cur_temp.description]
            old_data = dict(zip(columns, row))
        con_temp.close()

        con = get_connection()
        cur = con.cursor()
        
        cur.execute("""
            UPDATE clients SET
                contract_number = ?, status = ?, contract_start = ?, contract_expiry = ?,
                company_name = ?, city = ?, postal_code = ?, address = ?,
                eik = ?, vat_registered = ?, mol = ?, phone1 = ?, phone2 = ?,
                last_modified = datetime('now', 'localtime')
            WHERE id = ?
        """, (
            data.get('contract_number'), data.get('status'),
            data.get('contract_start'), data.get('contract_expiry'),
            data.get('company_name'), data.get('city'), data.get('postal_code'),
            data.get('address'), data.get('eik'), data.get('vat_registered'),
            data.get('mol'), data.get('phone1'), data.get('phone2'),
            client_id
        ))
        
        con.commit()
        
        # Log diff
        if old_data:
            log_diff(user_id, username, "UPDATE_CLIENT", old_data, data, data.get('contract_number'))

        return cur.rowcount > 0
    except Exception as e:
        print(f"Error updating client: {e}")
        if con: con.rollback()
        return False
    finally:
        if con: con.close()


def delete_client(client_id: int) -> bool:
    """Delete client and potentially their devices (handled by cascades if set, but we do it safely)"""
    con = None
    try:
        con = get_connection()
        cur = con.cursor()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # Soft delete client
        cur.execute("UPDATE clients SET is_deleted = 1, last_modified = ? WHERE id = ?", (now_str, client_id))
        # Soft delete their devices too
        cur.execute("UPDATE devices SET is_deleted = 1, last_modified = ? WHERE client_id = ?", (now_str, client_id))
        con.commit()
        return True
    except Exception as e:
        print(f"Error deleting client: {e}")
        if con: con.rollback()
        return False
    finally:
        if con: con.close()


def get_client_by_contract(contract_number: str) -> Optional[Dict[str, Any]]:
    """Get client data by contract number"""
    con = None
    try:
        con = get_connection()
        cur = con.cursor()
        
        cur.execute("""
            SELECT id, contract_number, status, contract_start, contract_expiry,
                   company_name, city, postal_code, address,
                   eik, vat_registered, mol, phone1, phone2
            FROM clients
            WHERE contract_number = ? AND is_deleted = 0
            LIMIT 1
        """, (contract_number,))
        
        row = cur.fetchone()
        
        if row:
            return {
                'id': row[0],
                'contract_number': row[1],
                'status': row[2],
                'contract_start': row[3],
                'contract_expiry': row[4],
                'company_name': row[5],
                'city': row[6],
                'postal_code': row[7],
                'address': row[8],
                'eik': row[9],
                'vat_registered': row[10],
                'mol': row[11],
                'phone1': row[12],
                'phone2': row[13]
            }
        return None
    except Exception as e:
        print(f"Error fetching client: {e}")
        return None
    finally:
        if con: con.close()


def get_devices_by_contract(contract_number: str) -> List[Dict[str, Any]]:
    """Get all devices for a specific contract number"""
    con = None
    try:
        con = get_connection()
        cur = con.cursor()
        
        cur.execute("""
            SELECT d.id, d.fdrid, d.euro_done, d.object_name, d.object_address, 
                   d.object_phone, d.model, d.certificate_number, 
                   d.certificate_expiry, d.serial_number, d.fiscal_memory,
                   c.contract_expiry
            FROM devices d
            JOIN clients c ON c.id = d.client_id
            WHERE c.contract_number = ? AND d.is_deleted = 0
        """, (contract_number,))
        
        rows = cur.fetchall()
        
        devices = []
        for row in rows:
            devices.append({
                'id': row[0],
                'fdrid': row[1],
                'euro_done': bool(row[2]),
                'object_name': row[3],
                'object_address': row[4],
                'object_phone': row[5],
                'model': row[6],
                'certificate_number': row[7],
                'certificate_expiry': row[8],
                'serial_number': row[9],
                'fiscal_memory': row[10],
                'contract_expiry': row[11]
            })
        return devices
    except Exception as e:
        print(f"Error fetching devices for contract: {e}")
        return []
    finally:
        if con: con.close()


def get_all_contract_numbers() -> List[str]:
    """Get list of all contract numbers for quick selection"""
    con = get_connection()
    cur = con.cursor()
    
    cur.execute("SELECT contract_number FROM clients WHERE is_deleted = 0 ORDER BY contract_number DESC")
    rows = cur.fetchall()
    con.close()
    
    return [row[0] for row in rows if row[0]]

def search_clients(query: str) -> List[Dict[str, Any]]:
    """Search clients by name or EIK"""
    con = get_connection()
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    
    q = f"%{query.lower()}%"
    cur.execute("""
        SELECT * FROM clients 
        WHERE (LOWER(company_name) LIKE ? OR eik LIKE ? OR contract_number LIKE ?) AND is_deleted = 0
        ORDER BY company_name ASC
    """, (q, q, q))
    
    rows = cur.fetchall()
    con.close()
    return [dict(r) for r in rows]

def get_all_clients() -> List[Dict[str, Any]]:
    """Get all clients for selection in dialogs"""
    con = get_connection()
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute("SELECT * FROM clients WHERE is_deleted = 0 ORDER BY company_name ASC")
    rows = cur.fetchall()
    con.close()
    return [dict(r) for r in rows]


# ============= DEVICE OPERATIONS =============

def add_device(client_id: int, data: Dict[str, Any]) -> int:
    """Add new device and return device_id"""
    con = get_connection()
    cur = con.cursor()
    
    # Check for duplicate serial number
    serial = data.get('serial_number')
    if serial:
        cur.execute("SELECT id FROM devices WHERE serial_number = ?", (serial,))
        if cur.fetchone():
            con.close()
            # Depending on UX, we might want to update or raise error. 
            # For now, let's treat it as error to prevent implicit overwrites or duplicates.
            raise ValueError(f"Device with serial number {serial} already exists!")
    
    cur.execute("""
        INSERT INTO devices (
            client_id, fdrid, euro_done, object_name, object_address,
            object_phone, model, certificate_number, certificate_expiry,
            serial_number, fiscal_memory,
            nra_report_enabled, nra_report_month, nra_td, bim_model, bim_date,
            maintenance_price, last_renewed_at, last_modified
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        client_id,
        data.get('fdrid'),
        1 if data.get('euro_done') else 0,
        data.get('object_name'),
        data.get('object_address'),
        data.get('object_phone'),
        data.get('model'),
        data.get('certificate_number'),
        data.get('certificate_expiry'),
        data.get('serial_number'),
        data.get('fiscal_memory'),
        1 if data.get('nra_report_enabled', True) else 0,
        data.get('nra_report_month', datetime.now().strftime('%m.%Y')),
        data.get('nra_td', 'СОФИЯ'),
        data.get('bim_model'),
        data.get('bim_date'),
        data.get('maintenance_price', 0),
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))
    
    device_id = cur.lastrowid
    con.commit()
    con.close()
    return device_id


def update_device(device_id: int, client_data: Dict[str, Any], device_data: Dict[str, Any], 
                  user_id: Optional[int] = None, username: str = "SYSTEM") -> bool:
    """Update existing device and its client data"""
    con = get_connection()
    cur = con.cursor()
    
    # Get client_id for this device
    cur.execute("SELECT client_id FROM devices WHERE id = ?", (device_id,))
    result = cur.fetchone()
    if not result:
        con.close()
        return False
    
    client_id = result[0]
    
    # Get old data for audit
    old_data = get_device_full(device_id)

    # Update client data
    cur.execute("""
        UPDATE clients SET
            contract_number = ?, status = ?, contract_start = ?, contract_expiry = ?,
            company_name = ?, city = ?, postal_code = ?, address = ?,
            eik = ?, vat_registered = ?, mol = ?, phone1 = ?, phone2 = ?,
            last_modified = ?
        WHERE id = ?
    """, (
        client_data.get('contract_number'),
        client_data.get('status'),
        client_data.get('contract_start'),
        client_data.get('contract_expiry'),
        client_data.get('company_name'),
        client_data.get('city'),
        client_data.get('postal_code'),
        client_data.get('address'),
        client_data.get('eik'),
        client_data.get('vat_registered'),
        client_data.get('mol'),
        client_data.get('phone1'),
        client_data.get('phone2'),
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        client_id
    ))
    
    # Update device data
    cur.execute("""
        UPDATE devices SET
            fdrid = ?, euro_done = ?, object_name = ?, object_address = ?,
            object_phone = ?, model = ?, certificate_number = ?, certificate_expiry = ?,
            serial_number = ?, fiscal_memory = ?,
            nra_report_enabled = ?, nra_report_month = ?, nra_td = ?, bim_model = ?, bim_date = ?,
            maintenance_price = ?,
            updated_at = datetime('now', 'localtime'),
            last_modified = ?
        WHERE id = ?
    """, (
        device_data.get('fdrid'),
        1 if device_data.get('euro_done') else 0,
        device_data.get('object_name'),
        device_data.get('object_address'),
        device_data.get('object_phone'),
        device_data.get('model'),
        device_data.get('certificate_number'),
        device_data.get('certificate_expiry'),
        device_data.get('serial_number'),
        device_data.get('fiscal_memory'),
        1 if device_data.get('nra_report_enabled') else 0,
        device_data.get('nra_report_month'),
        device_data.get('nra_td'),
        device_data.get('bim_model'),
        device_data.get('bim_date'),
        device_data.get('maintenance_price', 0),
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        device_id
    ))
    
    con.commit()

    # Log diff
    if old_data:
        merged_new = {**client_data, **device_data}
        log_diff(user_id, username, "UPDATE_DEVICE", old_data, merged_new, client_data.get('contract_number'), device_id)

    con.close()
    return True


def delete_device(device_id: int) -> bool:
    """Delete device by ID"""
    con = get_connection()
    cur = con.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    cur.execute("UPDATE devices SET is_deleted = 1, last_modified = ? WHERE id = ?", (now_str, device_id))
    deleted = cur.rowcount > 0
    
    con.commit()
    con.close()
    return deleted


def get_device_full(device_id: int) -> Optional[Dict[str, Any]]:
    """Get complete device data with client info"""
    con = get_connection()
    cur = con.cursor()
    
    cur.execute("""
        SELECT 
            d.id, d.client_id,
            c.contract_number, c.status, c.contract_start, c.contract_expiry,
            c.company_name, c.city, c.postal_code, c.address,
            c.eik, c.vat_registered, c.mol, c.phone1, c.phone2,
            d.fdrid, d.euro_done, d.object_name, d.object_address,
            d.object_phone, d.model, d.certificate_number, d.certificate_expiry,
            d.serial_number, d.fiscal_memory,
            d.nra_report_enabled, d.nra_report_month, d.nra_td, d.bim_model, d.bim_date,
            d.created_at, d.updated_at, d.maintenance_price, d.last_renewed_at
        FROM devices d
        JOIN clients c ON c.id = d.client_id
        WHERE d.id = ?
    """, (device_id,))
    
    row = cur.fetchone()
    con.close()
    
    if row:
        return {
            'device_id': row[0], 'client_id': row[1], 'contract_number': row[2],
            'status': row[3], 'contract_start': row[4], 'contract_expiry': row[5],
            'company_name': row[6], 'city': row[7], 'postal_code': row[8],
            'address': row[9], 'eik': row[10], 'vat_registered': row[11],
            'mol': row[12], 'phone1': row[13], 'phone2': row[14],
            'fdrid': row[15], 'euro_done': bool(row[16]), 'object_name': row[17],
            'object_address': row[18], 'object_phone': row[19], 'model': row[20],
            'certificate_number': row[21], 'certificate_expiry': row[22],
            'serial_number': row[23], 'fiscal_memory': row[24],
            'nra_report_enabled': bool(row[25]), 'nra_report_month': row[26],
            'nra_td': row[27], 'bim_model': row[28], 'bim_date': row[29],
            'created_at': row[30], 'updated_at': row[31],
            'maintenance_price': row[32] if len(row) > 32 else 0,
            'last_renewed_at': row[33] if len(row) > 33 else None
        }
    return None


def get_all_devices() -> List[Tuple]:
    """Get all devices with client info for main table display"""
    con = get_connection()
    cur = con.cursor()
    
    cur.execute("""
        SELECT 
            d.id,                 -- 0
            c.contract_number,    -- 1
            c.status,             -- 2
            c.company_name,       -- 3
            c.eik,                -- 4
            c.vat_registered,     -- 5
            c.mol,                -- 6
            c.city,               -- 7
            c.postal_code,        -- 8
            c.address,            -- 9
            c.phone1,             -- 10
            c.phone2,             -- 11
            c.contract_start,     -- 12
            c.contract_expiry,    -- 13
            d.object_name,        -- 14
            d.object_address,     -- 15
            d.object_phone,       -- 16
            d.model,              -- 17
            d.serial_number,      -- 18
            d.fdrid,              -- 19
            d.fiscal_memory,      -- 20
            d.certificate_number, -- 21
            d.certificate_expiry, -- 22
            d.euro_done,          -- 23
            d.nra_report_enabled  -- 24
        FROM devices d
        JOIN clients c ON c.id = d.client_id
        WHERE d.is_deleted = 0
        ORDER BY CAST(c.contract_number AS INTEGER), c.contract_number, d.id
    """)
    
    rows = cur.fetchall()
    con.close()
    return rows


def get_devices_for_nra_report() -> List[Dict[str, Any]]:
    """Get all devices flagged for the NRA report"""
    con = get_connection()
    cur = con.cursor()

    cur.execute("""
        SELECT 
            d.id, d.client_id,
            c.contract_number, c.status, c.contract_start, c.contract_expiry,
            c.company_name, c.city, c.postal_code, c.address,
            c.eik, c.vat_registered, c.mol, c.phone1, c.phone2,
            d.fdrid, d.euro_done, d.object_name, d.object_address,
            d.object_phone, d.model, d.certificate_number, d.certificate_expiry,
            d.serial_number, d.fiscal_memory,
            d.nra_report_enabled, d.nra_report_month, d.nra_td, d.bim_model, d.bim_date,
            d.created_at, d.updated_at
        FROM devices d
        JOIN clients c ON c.id = d.client_id
        WHERE d.nra_report_enabled = 1
        ORDER BY CAST(c.contract_number AS INTEGER), c.contract_number, d.id
    """)

    rows = cur.fetchall()
    con.close()

    results = []
    for row in rows:
        results.append({
            'device_id': row[0], 'client_id': row[1], 'contract_number': row[2],
            'status': row[3], 'contract_start': row[4], 'contract_expiry': row[5],
            'company_name': row[6], 'city': row[7], 'postal_code': row[8],
            'address': row[9], 'eik': row[10], 'vat_registered': row[11],
            'mol': row[12], 'phone1': row[13], 'phone2': row[14],
            'fdrid': row[15], 'euro_done': bool(row[16]), 'object_name': row[17],
            'object_address': row[18], 'object_phone': row[19], 'model': row[20],
            'certificate_number': row[21], 'certificate_expiry': row[22],
            'serial_number': row[23], 'fiscal_memory': row[24],
            'nra_report_enabled': bool(row[25]), 'nra_report_month': row[26],
            'nra_td': row[27], 'bim_model': row[28], 'bim_date': row[29],
            'created_at': row[30], 'updated_at': row[31]
        })
    return results


# ============= SEARCH & FILTER =============

def search_devices(filters: Dict[str, Any]) -> List[Tuple]:
    """Search devices with Python-side filtering for robust Unicode support"""
    con = get_connection()
    cur = con.cursor()
    
    cur.execute("""
        SELECT 
            d.id,                 -- 0
            c.contract_number,    -- 1
            c.status,             -- 2
            c.company_name,       -- 3
            c.eik,                -- 4
            c.vat_registered,     -- 5
            c.mol,                -- 6
            c.city,               -- 7
            c.postal_code,        -- 8
            c.address,            -- 9
            c.phone1,             -- 10
            c.phone2,             -- 11
            c.contract_start,     -- 12
            c.contract_expiry,    -- 13
            d.object_name,        -- 14
            d.object_address,     -- 15
            d.object_phone,       -- 16
            d.model,              -- 17
            d.serial_number,      -- 18
            d.fdrid,              -- 19
            d.fiscal_memory,      -- 20
            d.certificate_number, -- 21
            d.certificate_expiry, -- 22
            d.euro_done,          -- 23
            d.nra_report_enabled  -- 24
        FROM devices d
        JOIN clients c ON c.id = d.client_id
    """)
    
    rows = cur.fetchall()
    con.close()
    
    filtered_rows = []
    
    # Text comparisons (case-insensitive)
    for row in rows:
        match = True
        
        # company: 3
        if filters.get('company') and filters['company'].lower() not in (row[3] or "").lower(): match = False
        # eik: 4
        if filters.get('eik') and filters['eik'].lower() not in (row[4] or "").lower(): match = False
        # contract: 1
        if filters.get('contract') and filters['contract'].lower() not in (row[1] or "").lower(): match = False
        # phone: 10, 11, 16
        if filters.get('phone'):
            ph = filters['phone'].lower()
            in_ph1 = ph in (row[10] or "").lower()
            in_ph2 = ph in (row[11] or "").lower()
            in_obj_ph = ph in (row[16] or "").lower()
            if not (in_ph1 or in_ph2 or in_obj_ph): match = False
            
        # address: 9, 15
        if filters.get('address'):
            adr = filters['address'].lower()
            in_c_adr = adr in (row[9] or "").lower()
            in_obj_adr = adr in (row[15] or "").lower()
            if not (in_c_adr or in_obj_adr): match = False
            
        # serial: 18
        if filters.get('serial') and filters['serial'].lower() not in (row[18] or "").lower(): match = False
        # euro: 23
        if filters.get('euro') and not row[23]: match = False
            
        if match:
            # Return all columns
            filtered_rows.append(row)
            
    # Sort by contract number
    filtered_rows.sort(key=lambda x: (int(x[1]) if x[1] and x[1].isdigit() else 999999, x[1], x[0]))
    return filtered_rows


def get_next_contract_number() -> str:
    """Get the next available contract number (max + 1)"""
    con = get_connection()
    cur = con.cursor()
    
    cur.execute("SELECT contract_number FROM clients")
    rows = cur.fetchall()
    con.close()
    
    max_num = 0
    for row in rows:
        try:
            num = int(row[0])
            if num > max_num: max_num = num
        except:
            continue
            
    return str(max_num + 1)


def get_expiring_contracts(month: int, year: int) -> List[Tuple]:
    """Get contracts expiring in specified month/year"""
    con = get_connection()
    cur = con.cursor()
    
    # Standardize to YYYY-MM
    target = f"{year}-{month:02d}"
    
    cur.execute("""
        SELECT 
            c.contract_number, c.company_name, d.model, d.serial_number,
            c.contract_expiry, c.eik, c.phone1
        FROM devices d
        JOIN clients c ON c.id = d.client_id
        WHERE c.contract_expiry LIKE ?
        ORDER BY c.contract_expiry ASC
    """, (f"{target}%",))
    
    rows = cur.fetchall()
    con.close()
    return rows


def get_contracts_expiring_in_days(days: int) -> List[Dict[str, Any]]:
    """Get list of clients with contracts expiring in exactly N days"""
    con = get_connection()
    cur = con.cursor()
    from datetime import date, timedelta
    target_date = date.today() + timedelta(days=days)
    target_date_str = target_date.isoformat()
    
    cur.execute("SELECT * FROM clients WHERE contract_expiry = ?", (target_date_str,))
    rows = cur.fetchall()
    
    # Map to dicts
    columns = [col[0] for col in cur.description]
    results = [dict(zip(columns, row)) for row in rows]
    
    con.close()
    return results


# ============= CERTIFICATE OPERATIONS =============

# ============= CERTIFICATE OPERATIONS =============

def get_all_certificates() -> List[Tuple]:
    """Get all certificates (number, expiry_date)"""
    con = get_connection()
    cur = con.cursor()
    
    cur.execute("SELECT number, expiry_date FROM certificates ORDER BY number")
    rows = cur.fetchall()
    con.close()
    return rows


def get_certificate_expiry(number: str) -> Optional[str]:
    """Get certificate expiry date by number"""
    con = get_connection()
    cur = con.cursor()
    cur.execute("SELECT expiry_date FROM certificates WHERE number = ?", (number,))
    row = cur.fetchone()
    con.close()
    return row[0] if row else None


def add_certificate(number: str, expiry_date: str) -> bool:
    """Add or update certificate"""
    con = get_connection()
    cur = con.cursor()
    try:
        cur.execute("""
            INSERT INTO certificates (number, expiry_date, last_modified) 
            VALUES (?, ?, datetime('now', 'localtime'))
            ON CONFLICT(number) DO UPDATE SET expiry_date = excluded.expiry_date, last_modified = datetime('now', 'localtime')
        """, (number, expiry_date))
        con.commit()
        con.close()
        return True
    except Exception:
        con.close()
        return False


def clear_certificates():
    """Clear all certificates (before reimport)"""
    con = get_connection()
    cur = con.cursor()
    cur.execute("DELETE FROM certificates")
    con.commit()
    con.close()


# ============= USER OPERATIONS =============

def add_user(username: str, password_hash: str, full_name: str, role: str = "user") -> bool:
    """Add a new user"""
    con = get_connection()
    cur = con.cursor()
    try:
        cur.execute("""
            INSERT INTO users (username, password_hash, full_name, role, last_modified)
            VALUES (?, ?, ?, ?, datetime('now', 'localtime'))
        """, (username, password_hash, full_name, role))
        con.commit()
        con.close()
        return True
    except sqlite3.IntegrityError:
        con.close()
        return False


def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    """Get user details by username"""
    con = get_connection()
    cur = con.cursor()
    cur.execute("SELECT id, username, password_hash, full_name, role FROM users WHERE username = ?", (username,))
    row = cur.fetchone()
    con.close()
    
    if row:
        return {
            'id': row[0],
            'username': row[1],
            'password_hash': row[2],
            'full_name': row[3],
            'role': row[4] if len(row) > 4 else ('admin' if row[1] == 'vladpos' else 'user')
        }
    return None


def get_all_users() -> List[Dict[str, Any]]:
    """Get all users"""
    con = get_connection()
    cur = con.cursor()
    cur.execute("SELECT id, username, full_name, created_at, role FROM users ORDER BY username")
    rows = cur.fetchall()
    con.close()
    
    users = []
    for row in rows:
        users.append({
            'id': row[0],
            'username': row[1],
            'full_name': row[2],
            'created_at': row[3],
            'role': row[4] if len(row) > 4 else 'user'
        })
    return users


def update_user(user_id: int, full_name: str, role: str, password_hash: Optional[str] = None) -> bool:
    """Update user details"""
    con = get_connection()
    cur = con.cursor()
    try:
        if password_hash:
            cur.execute("""
                UPDATE users 
                SET full_name = ?, role = ?, password_hash = ?, last_modified = datetime('now', 'localtime')
                WHERE id = ?
            """, (full_name, role, password_hash, user_id))
        else:
            cur.execute("""
                UPDATE users 
                SET full_name = ?, role = ?, last_modified = datetime('now', 'localtime')
                WHERE id = ?
            """, (full_name, role, user_id))
        con.commit()
        return True
    except Exception as e:
        print(f"Error updating user: {e}")
        return False
    finally:
        con.close()


def delete_user(user_id: int) -> bool:
    """Delete a user by ID"""
    con = get_connection()
    cur = con.cursor()
    cur.execute("DELETE FROM users WHERE id = ?", (user_id,))
    deleted = cur.rowcount > 0
    con.commit()
    con.close()
    return deleted


# ============= AUDIT OPERATIONS =============

FIELD_LABELS = {
    'contract_number': '№ Договор', 'status': 'Статус', 'contract_start': 'Старт Договор',
    'contract_expiry': 'Край Договор', 'company_name': 'Фирма', 'city': 'Град',
    'postal_code': 'ПК', 'address': 'Адрес', 'eik': 'ЕИК', 'vat_registered': 'ДДС',
    'mol': 'МОЛ', 'phone1': 'Тел. 1', 'phone2': 'Тел. 2', 'fdrid': 'FDRID',
    'euro_done': 'Евро', 'object_name': 'Име Обект', 'object_address': 'Адрес Обект',
    'object_phone': 'Тел. Обект', 'model': 'Модел', 'certificate_number': '№ Свид. БИМ',
    'certificate_expiry': 'Валидност БИМ', 'serial_number': 'Сериен №',
    'fiscal_memory': '№ ФП', 'nra_report_enabled': 'НАП Отчет',
    'nra_report_month': 'НАП Месец', 'nra_td': 'НАП ТД', 'bim_model': 'Модел БИМ',
    'bim_date': 'Дата БИМ', 'maintenance_price': 'Такса поддръжка',
    'name': 'Име Продукт', 'category': 'Категория', 'price_bgn': 'Цена BGN',
    'price_eur': 'Цена EUR', 'description': 'Описание'
}

def log_diff(user_id: Optional[int], username: str, action: str, old_data: Dict[str, Any], new_data: Dict[str, Any], 
             contract_number: Optional[str] = None, device_id: Optional[int] = None):
    """Compare two dicts and log differences to audit_logs"""
    diffs = []
    for key, new_val in new_data.items():
        if key in ['last_modified', 'updated_at', 'id', 'client_id', 'created_at', 'last_renewed_at']:
            continue
        
        old_val = old_data.get(key)
        
        # Normalize types for comparison
        if isinstance(new_val, bool): old_val = bool(old_val)
        if isinstance(new_val, (int, float)) and old_val is not None:
            try: old_val = type(new_val)(old_val)
            except: pass
            
        if old_val != new_val:
            label = FIELD_LABELS.get(key, key)
            diffs.append(f"{label}: {old_val} -> {new_val}")
    
    if diffs:
        details = "Промени: " + ", ".join(diffs)
        log_action(user_id, username, action, details, contract_number, device_id)

def log_action(user_id: Optional[int], username: str, action: str, details: str = "", 
               contract_number: Optional[str] = None, device_id: Optional[int] = None):
    """Log an action to audit_logs with optional contract/device tracking"""
    con = get_connection()
    cur = con.cursor()
    try:
        # Use local time instead of UTC
        from datetime import datetime
        local_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        cur.execute("""
            INSERT INTO audit_logs (user_id, username, action, details, timestamp, contract_number, device_id, last_modified)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, username, action, details, local_time, contract_number, device_id, local_time))
        con.commit()
    except:
        pass # Logging should not break app flow
    finally:
        con.close()


def get_device_history(device_id: int):
    """Get audit history + repair history for a specific device"""
    con = get_connection()
    cur = con.cursor()
    
    # Union of audit logs and repair history for a unified view
    cur.execute("""
        SELECT timestamp, username, action, details
        FROM audit_logs
        WHERE device_id = ?
        
        UNION ALL
        
        SELECT repair_date || ' 00:00:00', 'Система', 'Ремонт', problem_description
        FROM repair_history
        WHERE device_id = ?
        
        ORDER BY timestamp DESC
    """, (device_id, device_id))
    
    rows = cur.fetchall()
    con.close()
    
    return [{"timestamp": r[0], "username": r[1], "action": r[2], "details": r[3]} for r in rows]


def get_contract_history(contract_number: str):
    """Get audit history + repair history for a specific contract"""
    con = get_connection()
    cur = con.cursor()
    
    # Union of audit logs and repair history for all devices in this contract
    cur.execute("""
        SELECT timestamp, username, action, details
        FROM audit_logs
        WHERE contract_number = ?
        
        UNION ALL
        
        SELECT r.repair_date || ' 00:00:00', 'Система', 'Ремонт', r.problem_description
        FROM repair_history r
        JOIN devices d ON r.device_id = d.id
        JOIN clients c ON d.client_id = c.id
        WHERE c.contract_number = ?
        
        ORDER BY timestamp DESC
    """, (contract_number, contract_number))
    
    rows = cur.fetchall()
    con.close()
    
    return [{"timestamp": r[0], "username": r[1], "action": r[2], "details": r[3]} for r in rows]


# ============= REPAIR HISTORY OPERATIONS =============

def add_repair_record(device_id: int, problem: str, date_str: str, path: str = "") -> int:
    """Add a new repair record and return its ID (protocol number)"""
    con = get_connection()
    cur = con.cursor()
    cur.execute("""
        INSERT INTO repair_history (device_id, problem_description, repair_date, protocol_path, last_modified)
        VALUES (?, ?, ?, ?, datetime('now', 'localtime'))
    """, (device_id, problem, date_str, path))
    record_id = cur.lastrowid
    con.commit()
    con.close()
    return record_id


def get_repair_history(device_id: int) -> List[Dict[str, Any]]:
    """Get repair history for a device"""
    con = get_connection()
    cur = con.cursor()
    cur.execute("""
        SELECT id, problem_description, repair_date, protocol_path
        FROM repair_history
        WHERE device_id = ?
        ORDER BY repair_date DESC
    """, (device_id,))
    rows = cur.fetchall()
    con.close()
    
    history = []
    for row in rows:
        history.append({
            'id': row[0],
            'problem': row[1],
            'date': row[2],
            'path': row[3]
        })
    return history


# ============= PRODUCT OPERATIONS =============

def add_product(data: Dict[str, Any]) -> int:
    """Add a new product"""
    con = get_connection()
    cur = con.cursor()
    new_uuid = str(uuid.uuid4())
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("""
        INSERT INTO products (uuid, name, category, price, currency, description, last_modified)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        new_uuid,
        data.get('name'),
        data.get('category'),
        data.get('price'),
        data.get('currency', 'BGN'),
        data.get('description'),
        now_str
    ))
    product_id = cur.lastrowid
    con.commit()
    con.close()
    return product_id


def update_product(product_id: int, data: Dict[str, Any], user_id: Optional[int] = None, username: str = "SYSTEM") -> bool:
    """Update an existing product"""
    con = None
    try:
        # Get old data for audit
        old_data = None
        con_temp = get_connection()
        cur_temp = con_temp.cursor()
        cur_temp.execute("SELECT * FROM products WHERE id = ?", (product_id,))
        row = cur_temp.fetchone()
        if row:
            columns = [col[0] for col in cur_temp.description]
            old_data = dict(zip(columns, row))
        con_temp.close()

        con = get_connection()
        cur = con.cursor()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur.execute("""
            UPDATE products SET
                name = ?, category = ?, price = ?, currency = ?, description = ?,
                updated_at = ?,
                last_modified = ?
            WHERE id = ?
        """, (
            data.get('name'),
            data.get('category'),
            data.get('price'),
            data.get('currency'),
            data.get('description'),
            now_str,
            now_str,
            product_id
        ))
        updated = cur.rowcount > 0
        con.commit()
        
        # Log diff
        if old_data:
            log_diff(user_id, username, "UPDATE_PRODUCT", old_data, data)

        return updated
    except Exception as e:
        print(f"Error updating product: {e}")
        if con: con.rollback()
        return False
    finally:
        if con: con.close()


def delete_product(product_id: int) -> bool:
    """Soft-delete a product (mark as deleted)"""
    con = get_connection()
    cur = con.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("""
        UPDATE products SET
            is_deleted = 1,
            last_modified = ?
        WHERE id = ?
    """, (now_str, product_id))
    deleted = cur.rowcount > 0
    con.commit()
    con.close()
    return deleted


# ============= GLOBAL SETTINGS (Synchronized) =============

def get_setting(key: str, default=None) -> Any:
    """Get a synchronized setting from DB"""
    con = get_connection()
    cur = con.cursor()
    cur.execute("SELECT value FROM global_settings WHERE key = ?", (key,))
    row = cur.fetchone()
    con.close()
    return row[0] if row else default

def set_setting(key: str, value: Any):
    """Save a synchronized setting to DB"""
    con = get_connection()
    cur = con.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("INSERT OR REPLACE INTO global_settings (key, value, last_modified) VALUES (?, ?, ?)",
               (key, str(value), now_str))
    con.commit()
    con.close()

def get_all_settings() -> List[Dict[str, Any]]:
    """Get all synchronized settings"""
    con = get_connection()
    cur = con.cursor()
    cur.execute("SELECT key, value, last_modified FROM global_settings")
    rows = cur.fetchall()
    con.close()
    return [{'key': r[0], 'value': r[1], 'last_modified': r[2]} for r in rows]
def get_all_products() -> List[Dict[str, Any]]:
    """Get all products"""
    con = get_connection()
    cur = con.cursor()
    cur.execute("""
        SELECT id, uuid, name, category, price, currency, description, created_at 
        FROM products 
        WHERE is_deleted = 0
        ORDER BY category, name
    """)
    rows = cur.fetchall()
    con.close()
    
    products = []
    for row in rows:
        products.append({
            'id': row[0],
            'uuid': row[1],
            'name': row[2],
            'category': row[3],
            'price': row[4],
            'currency': row[5],
            'description': row[6],
            'created_at': row[7]
        })
    return products

def search_products(query: str) -> List[Dict[str, Any]]:
    """Search products by name or category"""
    con = get_connection()
    cur = con.cursor()
    search = f"%{query}%"
    cur.execute("""
        SELECT id, uuid, name, category, price, currency, description, created_at 
        FROM products 
        WHERE (name LIKE ? OR category LIKE ? OR description LIKE ?) AND is_deleted = 0
        ORDER BY category, name
    """, (search, search, search))
    rows = cur.fetchall()
    con.close()
    
    products = []
    for row in rows:
        products.append({
            'id': row[0],
            'uuid': row[1],
            'name': row[2],
            'category': row[3],
            'price': row[4],
            'currency': row[5],
            'description': row[6],
            'created_at': row[7]
        })
    return products

# ============= INVOICES & FINANCIALS =============

def get_next_invoice_number(doc_type: str = 'INV') -> str:
    """Generate the next sequence number for invoices"""
    con = get_connection()
    cur = con.cursor()
    cur.execute("SELECT MAX(CAST(number AS INTEGER)) FROM invoices WHERE type = ?", (doc_type,))
    last_num = cur.fetchone()[0]
    con.close()
    
    if last_num is None:
        return "0000000001"
    return str(int(last_num) + 1).zfill(10)

def add_invoice(data: Dict[str, Any], items: List[Dict[str, Any]]) -> int:
    """Create a new invoice with items"""
    con = get_connection()
    cur = con.cursor()
    try:
        new_uuid = str(uuid.uuid4())
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Calculate totals
        total_base = sum(item['quantity'] * item['unit_price'] for item in items)
        vat_rate = data.get('vat_rate', 20)
        total_vat = total_base * (vat_rate / 100)
        total_amount = total_base + total_vat
        
        cur.execute("""
            INSERT INTO invoices (
                uuid, number, type, client_id, client_name, client_eik, client_vat,
                client_address, client_mol, date_issued, date_due,
                total_base, total_vat, total_amount, vat_rate, currency,
                payment_status, payment_method, notes, last_modified
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            new_uuid, data.get('number'), data.get('type', 'INV'), data.get('client_id'),
            data.get('client_name'), data.get('client_eik'), data.get('client_vat'),
            data.get('client_address'), data.get('client_mol'), data.get('date_issued'),
            data.get('date_due'), total_base, total_vat, total_amount, vat_rate,
            data.get('currency', 'BGN'), data.get('payment_status', 'PENDING'),
            data.get('payment_method', 'BANK'), data.get('notes'), now_str
        ))
        
        invoice_id = cur.lastrowid
        
        # Add items
        for item in items:
            cur.execute("""
                INSERT INTO invoice_items (invoice_id, description, quantity, unit_price, total_price)
                VALUES (?, ?, ?, ?, ?)
            """, (
                invoice_id, item['description'], item['quantity'],
                item['unit_price'], item['quantity'] * item['unit_price']
            ))
            
        con.commit()
        return invoice_id
    except Exception as e:
        con.rollback()
        raise e
    finally:
        con.close()

def update_invoice(invoice_id: int, data: Dict[str, Any], items: List[Dict[str, Any]], 
                   user_id: Optional[int] = None, username: str = "SYSTEM") -> bool:
    """Update an existing invoice and its items"""
    con = get_connection()
    cur = con.cursor()
    try:
        # Get old data for audit
        cur.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,))
        row = cur.fetchone()
        old_data = None
        if row:
            columns = [col[0] for col in cur.description]
            old_data = dict(zip(columns, row))

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Calculate totals
        total_base = sum(item['quantity'] * item['unit_price'] for item in items)
        vat_rate = data.get('vat_rate', 20)
        total_vat = total_base * (vat_rate / 100)
        total_amount = total_base + total_vat
        
        # Update invoice header
        cur.execute("""
            UPDATE invoices SET
                number = ?, type = ?, client_id = ?, client_name = ?, client_eik = ?, client_vat = ?,
                client_address = ?, client_mol = ?, date_issued = ?, date_due = ?,
                total_base = ?, total_vat = ?, total_amount = ?, vat_rate = ?, currency = ?,
                payment_status = ?, payment_method = ?, notes = ?, last_modified = ?
            WHERE id = ?
        """, (
            data.get('number'), data.get('type', 'INV'), data.get('client_id'),
            data.get('client_name'), data.get('client_eik'), data.get('client_vat'),
            data.get('client_address'), data.get('client_mol'), data.get('date_issued'),
            data.get('date_due'), total_base, total_vat, total_amount, vat_rate,
            data.get('currency', 'BGN'), data.get('payment_status', 'PENDING'),
            data.get('payment_method', 'BANK'), data.get('notes'), now_str,
            invoice_id
        ))
        
        # Delete old items and insert new ones
        cur.execute("DELETE FROM invoice_items WHERE invoice_id = ?", (invoice_id,))
        for item in items:
            cur.execute("""
                INSERT INTO invoice_items (invoice_id, description, quantity, unit_price, total_price)
                VALUES (?, ?, ?, ?, ?)
            """, (
                invoice_id, item['description'], item['quantity'],
                item['unit_price'], item['quantity'] * item['unit_price']
            ))
            
        con.commit()

        # Log diff for header
        if old_data:
            log_diff(user_id, username, "UPDATE_INVOICE", old_data, data, data.get('number'))

        return True
    except Exception as e:
        print(f"Error updating invoice: {e}")
        con.rollback()
        return False
    finally:
        con.close()

def get_all_invoices(filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    """Get list of invoices with optional filtering"""
    con = get_connection()
    cur = con.cursor()
    
    query = "SELECT * FROM invoices WHERE is_deleted = 0"
    params = []
    
    if filters:
        if filters.get('type'):
            query += " AND type = ?"
            params.append(filters['type'])
        if filters.get('payment_status'):
            query += " AND payment_status = ?"
            params.append(filters['payment_status'])
            
    query += " ORDER BY number DESC"
    
    cur.execute(query, params)
    # Convert to list of dicts
    columns = [column[0] for column in cur.description]
    results = [dict(zip(columns, row)) for row in cur.fetchall()]
    con.close()
    return results

def get_invoice_details(invoice_id: int) -> Dict[str, Any]:
    """Get full invoice data including items"""
    con = get_connection()
    cur = con.cursor()
    
    # Invoice header
    cur.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,))
    row = cur.fetchone()
    if not row:
        con.close()
        return None
        
    columns = [column[0] for column in cur.description]
    invoice = dict(zip(columns, row))
    
    # Items
    cur.execute("SELECT * FROM invoice_items WHERE invoice_id = ?", (invoice_id,))
    item_columns = [column[0] for column in cur.description]
    invoice['items'] = [dict(zip(item_columns, r)) for r in cur.fetchall()]
    
    con.close()
    return invoice

def update_invoice_payment(invoice_id: int, status: str, is_paid: bool = False) -> bool:
    """Update payment status of an invoice"""
    con = get_connection()
    cur = con.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    cur.execute("""
        UPDATE invoices SET payment_status = ?, is_paid = ?, last_modified = ?
        WHERE id = ?
    """, (status, 1 if is_paid else 0, now_str, invoice_id))
    
    updated = cur.rowcount > 0
    con.commit()
    con.close()
    return updated

def delete_invoice(invoice_id: int) -> bool:
    """Soft-delete an invoice"""
    con = get_connection()
    cur = con.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    cur.execute("UPDATE invoices SET is_deleted = 1, last_modified = ? WHERE id = ?", (now_str, invoice_id))
    
    deleted = cur.rowcount > 0
    con.commit()
    con.close()
    return deleted

def restore_database_from_backup(backup_path):
    """
    Restore database from a ZIP backup file.
    """
    import zipfile
    import shutil
    import os
    from path_utils import get_app_root, get_data_root
    
    app_root = get_app_root()
    db_path = os.path.join(app_root, "data", "contracts.db")
    
    try:
        if not os.path.exists(backup_path):
            return False, "Файлът на бекъпа не съществува."
            
        # Create a safety backup of current DB
        safety_path = db_path + ".safety"
        if os.path.exists(db_path):
            shutil.copy2(db_path, safety_path)
            
        with zipfile.ZipFile(backup_path, 'r') as zip_ref:
            # Look for contracts.db inside the zip
            if 'contracts.db' in zip_ref.namelist():
                zip_ref.extract('contracts.db', os.path.join(app_root, "data"))
                return True, "Базата данни е възстановена успешно."
            else:
                return False, "В архива не беше намерен файл contracts.db."
    except Exception as e:
        return False, f"Грешка при възстановяване: {str(e)}"

def reset_database():
    """
    Clear all data from the database but preserve the super admin.
    """
    import os
    from path_utils import get_app_root, get_data_root
    from super_admin_manager import load_super_admin
    
    app_root = get_app_root()
    db_path = os.path.join(app_root, "data", "contracts.db")
    
    try:
        # 1. Load super admin from encrypted storage
        admin_data = load_super_admin()
        if not admin_data:
            return False, "Не бе намерена информация за супер администратора."
            
        # 2. Delete current DB
        if os.path.exists(db_path):
            # We might need to ensure connections are closed, but in this app 
            # we usually open/close per operation or rely on the fact that 
            # this will be called from a controlled state.
            os.remove(db_path)
            
        # 3. Re-initialize empty DB
        init_db()
        
        # 4. Restore super admin into the fresh DB
        con = sqlite3.connect(db_path)
        cur = con.cursor()
        
        # Check if vladpos already exists (init_db might have created it)
        cur.execute("SELECT id FROM users WHERE username = 'vladpos'")
        existing = cur.fetchone()
        
        if existing:
            cur.execute("""
                UPDATE users SET password_hash = ?, full_name = ? WHERE username = 'vladpos'
            """, (admin_data['password_hash'], admin_data['full_name']))
        else:
            cur.execute("""
                INSERT INTO users (username, password_hash, full_name, role)
                VALUES (?, ?, ?, 'admin')
            """, (admin_data['username'], admin_data['password_hash'], admin_data['full_name']))
            
        con.commit()
        con.close()
        
        return True, "Базата данни бе изчистена успешно. Супер администраторът е запазен."
    except Exception as e:
        return False, f"Грешка при изтриване на базата: {str(e)}"


def get_db_stats() -> Dict[str, Any]:
    """Calculate various statistics from the database"""
    con = get_connection()
    cur = con.cursor()
    
    from datetime import date, timedelta
    today = date.today()
    tomorrow = today + timedelta(days=1)
    thirty_days_later = today + timedelta(days=30)
    
    today_str = today.isoformat()
    tomorrow_str = tomorrow.isoformat()
    thirty_days_later_str = thirty_days_later.isoformat()
    
    stats = {}
    
    # Helper for case-insensitive status matching in standard SQLite
    def status_is(status_val):
        return f"(LOWER({status_val}) = 'активен' OR {status_val} = 'Активен')"
    
    def status_is_expired(status_val):
        return f"(LOWER({status_val}) = 'изтекъл' OR {status_val} = 'Изтекъл')"

    # 1. Active Contracts: expiry >= tomorrow
    cur.execute("""
        SELECT COUNT(*) FROM clients 
        WHERE (contract_expiry IS NOT NULL AND contract_expiry >= ?)
    """, (tomorrow_str,))
    stats['active_contracts'] = cur.fetchone()[0]
    
    # 2. Expired Contracts: status 'изтекъл' OR expiry < today
    cur.execute(f"""
        SELECT COUNT(*) FROM clients 
        WHERE ({status_is_expired('status')})
        OR (contract_expiry IS NOT NULL AND contract_expiry < ?)
    """, (today_str,))
    stats['expired_contracts'] = cur.fetchone()[0]
    
    # 3. Expiring Soon: today <= expiry <= thirty_days_later
    cur.execute("""
        SELECT COUNT(*) FROM clients 
        WHERE (contract_expiry IS NOT NULL AND contract_expiry >= ? AND contract_expiry <= ?)
    """, (today_str, thirty_days_later_str))
    stats['expiring_soon'] = cur.fetchone()[0]
    
    # 2. Financials (Monthly Revenue from maintenance_price)
    # Using date-based definition for revenue
    cur.execute("""
        SELECT SUM(maintenance_price) 
        FROM devices d 
        JOIN clients c ON d.client_id = c.id 
        WHERE (c.contract_expiry IS NOT NULL AND c.contract_expiry >= ?)
    """, (tomorrow_str,))
    result = cur.fetchone()
    stats['monthly_revenue'] = result[0] if result[0] else 0.0
    
    # 3. Model distribution
    cur.execute("SELECT model, COUNT(*) as count FROM devices GROUP BY model ORDER BY count DESC LIMIT 5")
    stats['model_dist'] = {row[0]: row[1] for row in cur.fetchall()}
    
    # 4. Total devices
    cur.execute("SELECT COUNT(*) FROM devices")
    stats['total_devices'] = cur.fetchone()[0]
    
    con.close()
    return stats
# --- Counterparty Management ---

def add_counterparty(name: str, eik: str = '', address: str = '', mol: str = '', phone: str = ''):
    """Add a new counterparty for protocols/invoices"""
    con = get_connection()
    cur = con.cursor()
    try:
        new_uuid = str(uuid.uuid4())
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur.execute("""
            INSERT INTO counterparties (uuid, name, eik, address, mol, phone, last_modified)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (new_uuid, name, eik, address, mol, phone, now_str))
        con.commit()
        return cur.lastrowid
    except Exception as e:
        print(f"Error adding counterparty: {e}")
        return None
    finally:
        con.close()

def get_all_counterparties():
    """Get all non-deleted counterparties"""
    con = get_connection()
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    try:
        cur.execute("SELECT * FROM counterparties WHERE is_deleted = 0 ORDER BY name")
        return [dict(row) for row in cur.fetchall()]
    finally:
        con.close()

def update_counterparty(cp_id: int, name: str, eik: str, address: str, mol: str, phone: str):
    """Update existing counterparty"""
    con = get_connection()
    cur = con.cursor()
    try:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur.execute("""
            UPDATE counterparties 
            SET name = ?, eik = ?, address = ?, mol = ?, phone = ?, 
                last_modified = ?
            WHERE id = ?
        """, (name, eik, address, mol, phone, now_str, cp_id))
        con.commit()
        return True
    finally:
        con.close()

def delete_counterparty(cp_id: int):
    """Soft-delete a counterparty"""
    con = get_connection()
    cur = con.cursor()
    try:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur.execute("UPDATE counterparties SET is_deleted = 1, last_modified = ? WHERE id = ?", (now_str, cp_id))
        con.commit()
        return True
    except Exception as e:
        print(f"Error deleting counterparty: {e}")
        return False
    finally:
        con.close()

# --- Handover Protocols ---

def add_handover_protocol(data: dict):
    """Save a new protocol record"""
    con = get_connection()
    cur = con.cursor()
    try:
        new_uuid = str(uuid.uuid4())
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur.execute("""
            INSERT INTO handover_protocols (
                uuid, protocol_date, technician_egn, capacity, counterparty_id,
                description, notes, ref_number, docx_path, last_modified
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            new_uuid,
            data.get('protocol_date'),
            data.get('technician_egn'),
            data.get('capacity'),
            data.get('counterparty_id'),
            data.get('description'),
            data.get('notes'),
            data.get('ref_number'),
            data.get('docx_path'),
            now_str
        ))
        con.commit()
        return cur.lastrowid
    finally:
        con.close()

def get_all_handover_protocols():
    """Get all non-deleted handover protocols"""
    con = get_connection()
    cur = con.cursor()
    try:
        cur.execute("""
            SELECT p.*, cp.name as counterparty_name 
            FROM handover_protocols p
            LEFT JOIN counterparties cp ON p.counterparty_id = cp.id
            WHERE p.is_deleted = 0
            ORDER BY protocol_date DESC
        """)
        columns = [column[0] for column in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]
    finally:
        con.close()

def delete_handover_protocol(protocol_id: int):
    """Soft-delete a handover protocol"""
    con = get_connection()
    cur = con.cursor()
    try:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur.execute("UPDATE handover_protocols SET is_deleted = 1, last_modified = ? WHERE id = ?", (now_str, protocol_id))
        con.commit()
        return True
    except Exception as e:
        print(f"Error deleting protocol: {e}")
        return False
    finally:
        con.close()
