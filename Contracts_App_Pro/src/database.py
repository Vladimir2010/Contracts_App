import sqlite3
import os
from typing import Optional, List, Dict, Tuple, Any
from datetime import datetime
from path_utils import get_app_root
DB_PATH = os.path.join(get_app_root(), "data", "contracts.db")


def get_connection():
    """Get database connection"""
    return sqlite3.connect(DB_PATH)


def init_db():
    """Initialize database with all tables"""
    con = get_connection()
    cur = con.cursor()

    # Clients table - stores company/contract information
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
            phone2 TEXT
        )
    """)

    # Devices table - stores fiscal device information
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
            FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
        )
    """)

    # Certificates table - stores certificate numbers and expiry dates from BIM
    cur.execute("""
        CREATE TABLE IF NOT EXISTS certificates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            number TEXT UNIQUE NOT NULL,
            expiry_date DATE
        )
    """)

    # Create indexes for faster searches
    cur.execute("CREATE INDEX IF NOT EXISTS idx_contract_number ON clients(contract_number)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_eik ON clients(eik)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_serial ON devices(serial_number)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_client_id ON devices(client_id)")

    # Users table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        )
    """)

    # Repair History table - stores generated repair protocols
    cur.execute("""
        CREATE TABLE IF NOT EXISTS repair_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id INTEGER NOT NULL,
            problem_description TEXT,
            repair_date DATE,
            protocol_path TEXT,
            FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE
        )
    """)

    con.commit()
    
    # Check if we need to create default admin
    cur.execute("SELECT count(*) FROM users")
    if cur.fetchone()[0] == 0:
        try:
            from auth import hash_password
            from super_admin_manager import save_super_admin
            # Default creds: vladpos / V!adp0s
            pwd_hash = hash_password("V!adp0s")
            cur.execute("""
                INSERT INTO users (username, password_hash, full_name)
                VALUES (?, ?, ?)
            """, ("vladpos", pwd_hash, "Администратор"))
            con.commit()
            
            # Save super admin to encrypted storage
            save_super_admin("vladpos", pwd_hash, "Администратор")
        except Exception as e:
            print(f"Error creating default user: {e}")
    
    # Migration: Add new columns if they don't exist
    cur.execute("PRAGMA table_info(devices)")
    columns = [col[1] for col in cur.fetchall()]
    
    new_cols = [
        ("created_at", "TIMESTAMP"),
        ("updated_at", "TIMESTAMP"),
        ("nra_report_enabled", "INTEGER DEFAULT 1"),
        ("nra_report_month", "TEXT"),
        ("nra_td", "TEXT DEFAULT 'СОФИЯ'"),
        ("bim_model", "TEXT"),
        ("bim_date", "DATE"),
        ("maintenance_price", "REAL DEFAULT 0"),
        ("last_renewed_at", "DATE")
    ]
    
    for col_name, col_type in new_cols:
        if col_name not in columns:
            cur.execute(f"ALTER TABLE devices ADD COLUMN {col_name} {col_type}")
            # Set default value for timestamps manually after adding
            if col_name in ["created_at", "updated_at"]:
                cur.execute(f"UPDATE devices SET {col_name} = CURRENT_TIMESTAMP WHERE {col_name} IS NULL")
    
    # Migration: Add contract_number and device_id to audit_logs for history tracking
    cur.execute("PRAGMA table_info(audit_logs)")
    audit_columns = [col[1] for col in cur.fetchall()]
    
    audit_new_cols = [
        ("contract_number", "TEXT"),
        ("device_id", "INTEGER")
    ]
    
    for col_name, col_type in audit_new_cols:
        if col_name not in audit_columns:
            cur.execute(f"ALTER TABLE audit_logs ADD COLUMN {col_name} {col_type}")
    
    con.commit()
    
    # Migration: Add role column to users
    cur.execute("PRAGMA table_info(users)")
    user_columns = [col[1] for col in cur.fetchall()]
    
    if "role" not in user_columns:
        cur.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'")
        # Set vladpos as admin
        cur.execute("UPDATE users SET role = 'admin' WHERE username = 'vladpos'")
        con.commit()
        
    # Products table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT,
            price REAL NOT NULL,
            currency TEXT DEFAULT 'BGN',
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    con.commit()
    con.close()


# ============= CLIENT OPERATIONS =============

def add_client(data: Dict[str, Any]) -> int:
    """Add new client and return client_id"""
    con = get_connection()
    cur = con.cursor()
    
    cur.execute("""
        INSERT INTO clients (
            contract_number, status, contract_start, contract_expiry,
            company_name, city, postal_code, address,
            eik, vat_registered, mol, phone1, phone2
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        data.get('phone2')
    ))
    
    client_id = cur.lastrowid
    con.commit()
    con.close()
    return client_id


def get_client_by_contract(contract_number: str) -> Optional[Dict[str, Any]]:
    """Get client data by contract number"""
    con = get_connection()
    cur = con.cursor()
    
    cur.execute("""
        SELECT id, contract_number, status, contract_start, contract_expiry,
               company_name, city, postal_code, address,
               eik, vat_registered, mol, phone1, phone2
        FROM clients
        WHERE contract_number = ?
        LIMIT 1
    """, (contract_number,))
    
    row = cur.fetchone()
    con.close()
    
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


def get_devices_by_contract(contract_number: str) -> List[Dict[str, Any]]:
    """Get all devices for a specific contract number"""
    con = get_connection()
    cur = con.cursor()
    
    cur.execute("""
        SELECT d.id, d.fdrid, d.euro_done, d.object_name, d.object_address, 
               d.object_phone, d.model, d.certificate_number, 
               d.certificate_expiry, d.serial_number, d.fiscal_memory,
               c.contract_expiry
        FROM devices d
        JOIN clients c ON c.id = d.client_id
        WHERE c.contract_number = ?
    """, (contract_number,))
    
    rows = cur.fetchall()
    con.close()
    
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


def get_all_contract_numbers() -> List[str]:
    """Get list of all contract numbers for quick selection"""
    con = get_connection()
    cur = con.cursor()
    
    cur.execute("SELECT DISTINCT contract_number FROM clients ORDER BY contract_number")
    rows = cur.fetchall()
    con.close()
    
    return [row[0] for row in rows if row[0]]


# ============= DEVICE OPERATIONS =============

def add_device(client_id: int, data: Dict[str, Any]) -> int:
    """Add new device and return device_id"""
    con = get_connection()
    cur = con.cursor()
    
    cur.execute("""
        INSERT INTO devices (
            client_id, fdrid, euro_done, object_name, object_address,
            object_phone, model, certificate_number, certificate_expiry,
            serial_number, fiscal_memory,
            nra_report_enabled, nra_report_month, nra_td, bim_model, bim_date,
            maintenance_price, last_renewed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        datetime.now().strftime('%Y-%m-%d')
    ))
    
    device_id = cur.lastrowid
    con.commit()
    con.close()
    return device_id


def update_device(device_id: int, client_data: Dict[str, Any], device_data: Dict[str, Any]) -> bool:
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
    
    # Update client data
    cur.execute("""
        UPDATE clients SET
            contract_number = ?, status = ?, contract_start = ?, contract_expiry = ?,
            company_name = ?, city = ?, postal_code = ?, address = ?,
            eik = ?, vat_registered = ?, mol = ?, phone1 = ?, phone2 = ?
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
            updated_at = CURRENT_TIMESTAMP
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
        device_id
    ))
    
    con.commit()
    con.close()
    return True


def delete_device(device_id: int) -> bool:
    """Delete device by ID"""
    con = get_connection()
    cur = con.cursor()
    
    cur.execute("DELETE FROM devices WHERE id = ?", (device_id,))
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
            INSERT INTO certificates (number, expiry_date) 
            VALUES (?, ?)
            ON CONFLICT(number) DO UPDATE SET expiry_date = excluded.expiry_date
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
            INSERT INTO users (username, password_hash, full_name, role)
            VALUES (?, ?, ?, ?)
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
                SET full_name = ?, role = ?, password_hash = ?
                WHERE id = ?
            """, (full_name, role, password_hash, user_id))
        else:
            cur.execute("""
                UPDATE users 
                SET full_name = ?, role = ?
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
            INSERT INTO audit_logs (user_id, username, action, details, timestamp, contract_number, device_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, username, action, details, local_time, contract_number, device_id))
        con.commit()
    except:
        pass # Logging should not break app flow
    finally:
        con.close()


def get_device_history(device_id: int):
    """Get audit history for a specific device"""
    con = get_connection()
    cur = con.cursor()
    
    cur.execute("""
        SELECT timestamp, username, action, details
        FROM audit_logs
        WHERE device_id = ?
        ORDER BY id DESC
    """, (device_id,))
    
    rows = cur.fetchall()
    con.close()
    
    return [{"timestamp": r[0], "username": r[1], "action": r[2], "details": r[3]} for r in rows]


def get_contract_history(contract_number: str):
    """Get audit history for a specific contract"""
    con = get_connection()
    cur = con.cursor()
    
    cur.execute("""
        SELECT timestamp, username, action, details
        FROM audit_logs
        WHERE contract_number = ?
        ORDER BY id DESC
    """, (contract_number,))
    
    rows = cur.fetchall()
    con.close()
    
    return [{"timestamp": r[0], "username": r[1], "action": r[2], "details": r[3]} for r in rows]


# ============= REPAIR HISTORY OPERATIONS =============

def add_repair_record(device_id: int, problem: str, date_str: str, path: str = "") -> int:
    """Add a new repair record and return its ID (protocol number)"""
    con = get_connection()
    cur = con.cursor()
    cur.execute("""
        INSERT INTO repair_history (device_id, problem_description, repair_date, protocol_path)
        VALUES (?, ?, ?, ?)
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
    cur.execute("""
        INSERT INTO products (name, category, price, currency, description)
        VALUES (?, ?, ?, ?, ?)
    """, (
        data.get('name'),
        data.get('category'),
        data.get('price'),
        data.get('currency', 'BGN'),
        data.get('description')
    ))
    product_id = cur.lastrowid
    con.commit()
    con.close()
    return product_id


def update_product(product_id: int, data: Dict[str, Any]) -> bool:
    """Update an existing product"""
    con = get_connection()
    cur = con.cursor()
    cur.execute("""
        UPDATE products SET
            name = ?, category = ?, price = ?, currency = ?, description = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (
        data.get('name'),
        data.get('category'),
        data.get('price'),
        data.get('currency'),
        data.get('description'),
        product_id
    ))
    updated = cur.rowcount > 0
    con.commit()
    con.close()
    return updated


def delete_product(product_id: int) -> bool:
    """Delete a product"""
    con = get_connection()
    cur = con.cursor()
    cur.execute("DELETE FROM products WHERE id = ?", (product_id,))
    deleted = cur.rowcount > 0
    con.commit()
    con.close()
    return deleted


def get_all_products() -> List[Dict[str, Any]]:
    """Get all products"""
    con = get_connection()
    cur = con.cursor()
    cur.execute("SELECT id, name, category, price, currency, description, created_at FROM products ORDER BY category, name")
    rows = cur.fetchall()
    con.close()
    
    products = []
    for row in rows:
        products.append({
            'id': row[0],
            'name': row[1],
            'category': row[2],
            'price': row[3],
            'currency': row[4],
            'description': row[5],
            'created_at': row[6]
        })
    return products

def search_products(query: str) -> List[Dict[str, Any]]:
    """Search products by name or category"""
    con = get_connection()
    cur = con.cursor()
    search = f"%{query}%"
    cur.execute("""
        SELECT id, name, category, price, currency, description, created_at 
        FROM products 
        WHERE name LIKE ? OR category LIKE ? OR description LIKE ?
        ORDER BY category, name
    """, (search, search, search))
    rows = cur.fetchall()
    con.close()
    
    products = []
    for row in rows:
        products.append({
            'id': row[0],
            'name': row[1],
            'category': row[2],
            'price': row[3],
            'currency': row[4],
            'description': row[5],
            'created_at': row[6]
        })
    return products

def restore_database_from_backup(backup_path):
    """
    Restore database from a ZIP backup file.
    """
    import zipfile
    import shutil
    import os
    from path_utils import get_app_root
    
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
    from path_utils import get_app_root
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
    today = date.today().isoformat()
    thirty_days_later = (date.today() + timedelta(days=30)).isoformat()
    
    stats = {}
    
    # 1. Contract counts
    cur.execute("SELECT COUNT(*) FROM clients WHERE status = 'Активен'")
    stats['active_contracts'] = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM clients WHERE status = 'Изтекъл' OR (contract_expiry IS NOT NULL AND contract_expiry < ?)", (today,))
    stats['expired_contracts'] = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM clients WHERE status = 'Активен' AND contract_expiry >= ? AND contract_expiry <= ?", 
                (today, thirty_days_later))
    stats['expiring_soon'] = cur.fetchone()[0]
    
    # 2. Financials (Monthly Revenue from maintenance_price)
    cur.execute("SELECT SUM(maintenance_price) FROM devices d JOIN clients c ON d.client_id = c.id WHERE c.status = 'Активен'")
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
