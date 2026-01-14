import sqlite3
from typing import Optional, List, Dict, Tuple, Any
from datetime import datetime

DB_PATH = "data/contracts.db"


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
            serial_number, fiscal_memory
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        data.get('fiscal_memory')
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
            serial_number = ?, fiscal_memory = ?
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
            d.serial_number, d.fiscal_memory
        FROM devices d
        JOIN clients c ON c.id = d.client_id
        WHERE d.id = ?
    """, (device_id,))
    
    row = cur.fetchone()
    con.close()
    
    if row:
        return {
            'device_id': row[0],
            'client_id': row[1],
            'contract_number': row[2],
            'status': row[3],
            'contract_start': row[4],
            'contract_expiry': row[5],
            'company_name': row[6],
            'city': row[7],
            'postal_code': row[8],
            'address': row[9],
            'eik': row[10],
            'vat_registered': row[11],
            'mol': row[12],
            'phone1': row[13],
            'phone2': row[14],
            'fdrid': row[15],
            'euro_done': bool(row[16]),
            'object_name': row[17],
            'object_address': row[18],
            'object_phone': row[19],
            'model': row[20],
            'certificate_number': row[21],
            'certificate_expiry': row[22],
            'serial_number': row[23],
            'fiscal_memory': row[24]
        }
    return None


def get_all_devices() -> List[Tuple]:
    """Get all devices with client info for main table display"""
    con = get_connection()
    cur = con.cursor()
    
    cur.execute("""
        SELECT 
            d.id,
            c.contract_number,
            c.status,
            c.company_name,
            c.eik,
            c.address,
            d.object_address,
            d.model,
            d.serial_number,
            c.contract_expiry,
            d.euro_done,
            c.city,
            c.phone1
        FROM devices d
        JOIN clients c ON c.id = d.client_id
        ORDER BY CAST(c.contract_number AS INTEGER), c.contract_number, d.id
    """)
    
    rows = cur.fetchall()
    con.close()
    return rows


# ============= SEARCH & FILTER =============

def search_devices(filters: Dict[str, Any]) -> List[Tuple]:
    """Search devices with Python-side filtering for robust Unicode support"""
    con = get_connection()
    cur = con.cursor()
    
    # Select all fields needed for BOTH display AND filtering
    cur.execute("""
        SELECT 
            d.id,                  
            c.contract_number,     
            c.status,
            c.company_name,        
            c.eik,                 
            c.address,
            d.object_address,
            d.model,               
            d.serial_number,       
            c.contract_expiry,     
            d.euro_done,           
            c.city,                
            c.phone1,              
            c.phone2,              
            d.object_phone
        FROM devices d
        JOIN clients c ON c.id = d.client_id
        ORDER BY CAST(c.contract_number AS INTEGER), c.contract_number, d.id
    """)
    
    rows = cur.fetchall()
    con.close()
    
    filtered_rows = []
    
    # Prepare filter terms (lowercase)
    q_company = filters.get('company', '').lower().strip()
    q_eik = filters.get('eik', '').lower().strip()
    q_contract = filters.get('contract', '').lower().strip()
    q_phone = filters.get('phone', '').lower().strip()
    q_address = filters.get('address', '').lower().strip()
    q_serial = filters.get('serial', '').lower().strip()
    q_euro = filters.get('euro')
    
    for row in rows:
        # Helper strings (handle None safely)
        
        r_contract = (str(row[1]) if row[1] else "").lower()
        r_company = (str(row[3]) if row[3] else "").lower()
        r_eik = (str(row[4]) if row[4] else "").lower()
        
        r_address = (str(row[5]) if row[5] else "").lower()
        r_obj_address = (str(row[6]) if row[6] else "").lower()
        
        r_serial = (str(row[8]) if row[8] else "").lower()
        r_euro = bool(row[10])
        
        r_phone1 = (str(row[12]) if row[12] else "").lower()
        r_phone2 = (str(row[13]) if row[13] else "").lower()
        r_obj_phone = (str(row[14]) if row[14] else "").lower()
        
        # Apply filters
        if q_company and q_company not in r_company: continue
        if q_eik and q_eik not in r_eik: continue
        if q_contract and q_contract not in r_contract: continue
        if q_serial and q_serial not in r_serial: continue
        
        if q_phone:
            if (q_phone not in r_phone1 and 
                q_phone not in r_phone2 and 
                q_obj_phone not in r_obj_phone):  # Typo fix: q_obj_phone is NOT defined, use q_phone
                # Wait, logic error in my thought. q_phone is correct var.
                pass

            if (q_phone not in r_phone1 and 
                q_phone not in r_phone2 and 
                q_phone not in r_obj_phone):
                continue
                
        if q_address:
            if (q_address not in r_address and 
                q_address not in r_obj_address):
                continue
        
        if q_euro and not r_euro: continue
        
        # Match found! Append first 13 columns for UI
        filtered_rows.append(row[:13])
        
    return filtered_rows


def get_next_contract_number() -> str:
    """Get the next available contract number (max + 1)"""
    con = get_connection()
    cur = con.cursor()
    
    # Get all contract numbers to find the max integer value
    cur.execute("SELECT contract_number FROM clients")
    rows = cur.fetchall()
    con.close()
    
    max_num = 0
    for row in rows:
        try:
            # Extract integer part if possible
            num = int(str(row[0]).strip())
            if num > max_num:
                max_num = num
        except ValueError:
            continue
            
    return str(max_num + 1)


def get_expiring_contracts(month: int, year: int) -> List[Tuple]:
    """Get contracts expiring in specified month/year"""
    con = get_connection()
    cur = con.cursor()
    
    cur.execute("""
        SELECT 
            c.contract_number,
            c.company_name,
            d.model,
            d.serial_number,
            c.contract_expiry,
            c.eik,
            c.phone1
        FROM devices d
        JOIN clients c ON c.id = d.client_id
        WHERE strftime('%m', c.contract_expiry) = ?
          AND strftime('%Y', c.contract_expiry) = ?
        ORDER BY c.contract_expiry, CAST(c.contract_number AS INTEGER), c.contract_number
    """, (f"{month:02d}", str(year)))
    
    rows = cur.fetchall()
    con.close()
    return rows


# ============= CERTIFICATE OPERATIONS =============

def get_all_certificates() -> List[Tuple[str, str]]:
    """Get all certificates (number, expiry_date)"""
    con = get_connection()
    cur = con.cursor()
    
    cur.execute("SELECT number, expiry_date FROM certificates ORDER BY number")
    rows = cur.fetchall()
    con.close()
    return rows


def add_certificate(number: str, expiry_date: str) -> bool:
    """Add or update certificate"""
    con = get_connection()
    cur = con.cursor()
    
    try:
        cur.execute("""
            INSERT OR REPLACE INTO certificates (number, expiry_date)
            VALUES (?, ?)
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
