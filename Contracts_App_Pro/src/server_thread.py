import threading
import uvicorn
import os
import sys
import uuid
import sqlite3
import traceback
from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Depends, Security
from fastapi.security.api_key import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from PyQt6.QtCore import QObject, pyqtSignal
import json

# Setup server-side file logging for debugging EXE mode
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "server_sync.log")

def server_log(msg, use_traceback=False):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] {msg}"
    if use_traceback:
        log_line += "\n" + traceback.format_exc()
    print(log_line)
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_line + "\n")
    except:
        pass

app = FastAPI(title="Contracts App Sync Server")

# CORS setup for Web App interaction
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

def get_api_key(api_key: str = Security(api_key_header)):
    # For now, we use a simple env var or default. 
    # In a real app, this would be set in Desktop App settings.
    authorized_key = os.getenv("CONTRACTS_API_KEY", "vladpos_secret_123")
    if api_key == authorized_key:
        return api_key
    raise HTTPException(status_code=403, detail="Invalid API Key")

# Models
class SyncPullRequest(BaseModel):
    last_sync_time: str

class SyncPushItem(BaseModel):
    table: str
    data: Dict[str, Any]

class SyncPushRequest(BaseModel):
    client_id: str
    items: List[SyncPushItem]

# Signals for UI updates
class ServerSignals(QObject):
    data_pushed = pyqtSignal()

signals = ServerSignals()

@app.get("/status")
def status():
    return {"status": "running", "server_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

# --- CRUD Endpoints for Web App ---

@app.get("/api/clients")
def get_clients_api(api_key: str = Depends(get_api_key)):
    from database import get_all_clients
    return get_all_clients()

@app.get("/api/clients/{contract_number}")
def get_client_api(contract_number: str, api_key: str = Depends(get_api_key)):
    from database import get_client_by_contract
    client = get_client_by_contract(contract_number)
    if not client: raise HTTPException(status_code=404, detail="Client not found")
    return client

@app.get("/api/devices")
def get_devices_api(api_key: str = Depends(get_api_key)):
    con = None
    try:
        from database import get_connection
        con = get_connection()
        cur = con.cursor()
        cur.execute("""
            SELECT d.id, c.contract_number, d.status, c.company_name, c.eik,
                   c.vat_registered, c.mol, c.city, c.postal_code, c.address,
                   c.phone1, c.phone2, c.contract_start, c.contract_expiry,
                   d.object_name, d.object_address, d.object_phone, d.model,
                   d.serial_number, d.fdrid, d.fiscal_memory, d.certificate_number,
                   d.certificate_expiry, d.euro_done, d.nra_report_enabled
            FROM devices d
            JOIN clients c ON c.id = d.client_id
            WHERE d.is_deleted = 0
        """)
        cols = [description[0] for description in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        if con: con.close()

@app.post("/api/devices")
def add_device_api(data: Dict[str, Any], api_key: str = Depends(get_api_key)):
    from database import add_device
    client_id = data.get('client_id')
    if not client_id: raise HTTPException(status_code=400, detail="client_id required")
    try:
        did = add_device(client_id, data)
        signals.data_pushed.emit()
        return {"id": did}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/devices/{device_id}")
def update_device_api(device_id: int, data: Dict[str, Any], api_key: str = Depends(get_api_key)):
    from database import update_device
    if update_device(device_id, data, data):
        signals.data_pushed.emit()
        return {"message": "Success"}
    raise HTTPException(status_code=404)

@app.delete("/api/devices/{device_id}")
def delete_device_api(device_id: int, api_key: str = Depends(get_api_key)):
    from database import delete_device
    if delete_device(device_id):
        signals.data_pushed.emit()
        return {"message": "Success"}
    raise HTTPException(status_code=404)

@app.post("/api/clients")
def add_client_api(data: Dict[str, Any], api_key: str = Depends(get_api_key)):
    from database import add_client
    cid = add_client(data)
    if cid == -1: raise HTTPException(status_code=500, detail="Failed to add client")
    signals.data_pushed.emit() # Refresh desktop UI
    return {"id": cid}

@app.put("/api/clients/{client_id}")
def update_client_api(client_id: int, data: Dict[str, Any], api_key: str = Depends(get_api_key)):
    from database import update_client
    if update_client(client_id, data):
        signals.data_pushed.emit()
        return {"message": "Success"}
    raise HTTPException(status_code=404)

@app.delete("/api/clients/{client_id}")
def delete_client_api(client_id: int, api_key: str = Depends(get_api_key)):
    from database import delete_client
    if delete_client(client_id):
        signals.data_pushed.emit()
        return {"message": "Success"}
    raise HTTPException(status_code=404)

@app.get("/api/products")
def get_products_api(api_key: str = Depends(get_api_key)):
    con = None
    try:
        from database import get_connection
        con = get_connection()
        cur = con.cursor()
        cur.execute("SELECT * FROM products WHERE is_deleted = 0")
        cols = [description[0] for description in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        if con: con.close()

@app.get("/api/invoices")
def get_invoices_api(api_key: str = Depends(get_api_key)):
    con = None
    try:
        from database import get_connection
        con = get_connection()
        cur = con.cursor()
        cur.execute("SELECT * FROM invoices WHERE is_deleted = 0")
        cols = [description[0] for description in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        if con: con.close()

@app.post("/sync/pull")
def pull_changes(req: SyncPullRequest):
    """Client asks for changes since last_sync_time"""
    server_log(f"PULL REQUEST received since {req.last_sync_time}")
    con = None
    try:
        try:
            from database import get_connection
        except ImportError:
            server_log("CRITICAL: Could not import get_connection from database.py", use_traceback=True)
            raise HTTPException(status_code=500, detail="Database import error")

        con = get_connection()
        cur = con.cursor()
        response = {"clients": [], "devices": [], "users": [], "products": [], "repair_history": [], "certificates": [], "audit_logs": [], "global_settings": []}
        
        last_sync = req.last_sync_time
        # Use > to avoid circular sync of same records
        
        tables = {
            "clients": "SELECT * FROM clients WHERE last_modified >= ?",
            "users": "SELECT * FROM users WHERE last_modified >= ?",
            "products": "SELECT * FROM products WHERE last_modified >= ?",
            "repair_history": "SELECT * FROM repair_history WHERE last_modified >= ?",
            "certificates": "SELECT * FROM certificates WHERE last_modified >= ?",
            "audit_logs": "SELECT * FROM audit_logs WHERE last_modified >= ?",
            "global_settings": "SELECT * FROM global_settings WHERE last_modified >= ?",
            "invoices": "SELECT * FROM invoices WHERE last_modified >= ?",
            "counterparties": "SELECT * FROM counterparties WHERE last_modified >= ?"
        }

        for key, query in tables.items():
            cur.execute(query, (last_sync,))
            cols = [description[0] for description in cur.description]
            response[key] = [dict(zip(cols, row)) for row in cur.fetchall()]

        # Special case for devices - need parent_contract_number
        cur.execute("""
            SELECT d.*, c.contract_number as parent_contract_number 
            FROM devices d
            JOIN clients c ON d.client_id = c.id
            WHERE d.last_modified >= ?
        """, (last_sync,))
        cols = [description[0] for description in cur.description]
        response["devices"] = [dict(zip(cols, row)) for row in cur.fetchall()]

        # Special case for invoice_items - need parent_invoice_uuid
        cur.execute("""
            SELECT i.*, inv.uuid as parent_invoice_uuid 
            FROM invoice_items i
            JOIN invoices inv ON i.invoice_id = inv.id
            WHERE i.last_modified >= ?
        """, (last_sync,))
        cols = [description[0] for description in cur.description]
        response["invoice_items"] = [dict(zip(cols, row)) for row in cur.fetchall()]

        # Special case for handover_protocols - need counterparty_uuid
        cur.execute("""
            SELECT p.*, cp.uuid as counterparty_uuid 
            FROM handover_protocols p
            LEFT JOIN counterparties cp ON p.counterparty_id = cp.id
            WHERE p.last_modified >= ?
        """, (last_sync,))
        cols = [description[0] for description in cur.description]
        response["handover_protocols"] = [dict(zip(cols, row)) for row in cur.fetchall()]
        
    finally:
        con.close()
    return response

@app.post("/sync/push")
def push_changes(req: SyncPushRequest):
    """Client sends local changes to be merged"""
    server_log(f"PUSH REQUEST received with {len(req.items)} items")
    con = None
    try:
        try:
            from database import get_connection
        except ImportError:
            server_log("CRITICAL: Could not import get_connection from database.py", use_traceback=True)
            raise HTTPException(status_code=500, detail="Database import error")
            
        con = get_connection()
        cur = con.cursor()
        data_changed = False
        stats = {"clients": 0, "devices": 0, "users": 0, "products": 0, "repairs": 0, "audit_logs": 0, "certificates": 0, "global_settings": 0, "errors": 0}

        for item in req.items:
            table = item.table
            data = item.data
            if not data: continue
            
            data_to_save = {k: v for k, v in data.items() if k not in ['id', 'parent_contract_number']}
            server_log(f"SERVER SYNC DEBUG: Processing {table} data for {data.get('contract_number') or data.get('serial_number') or 'unknown'}")
            
            try:
                if table == "clients":
                    contract_num = data.get('contract_number')
                    if contract_num:
                        cur.execute("SELECT id FROM clients WHERE contract_number = ?", (contract_num,))
                        exists = cur.fetchone()
                        if exists:
                            incoming_ts = data.get('last_modified', '')
                            cur.execute("SELECT last_modified FROM clients WHERE id=?", (exists[0],))
                            existing_ts = cur.fetchone()[0] or ""
                            if incoming_ts > existing_ts:
                                clauses = ", ".join([f"{k}=?" for k in data_to_save.keys()])
                                cur.execute(f"UPDATE clients SET {clauses} WHERE id=?", (*data_to_save.values(), exists[0]))
                                data_changed = True
                                stats["clients"] += 1
                                server_log(f"SERVER SYNC: Updated client {contract_num} (del={data.get('is_deleted')})")
                            else:
                                server_log(f"SERVER SYNC: Ignored client {contract_num} (existing modified at {existing_ts} >= incoming {incoming_ts})")
                        else:
                            cols = ", ".join(data_to_save.keys())
                            placeholders = ", ".join(["?" for _ in data_to_save])
                            cur.execute(f"INSERT INTO clients ({cols}) VALUES ({placeholders})", list(data_to_save.values()))
                            data_changed = True
                            stats["clients"] += 1
                            server_log(f"SERVER SYNC: Inserted client {contract_num}")

                elif table == "devices":
                    serial = data.get('serial_number')
                    parent_cn = data.get('parent_contract_number')
                    if serial and parent_cn:
                        cur.execute("SELECT id FROM clients WHERE contract_number = ?", (parent_cn,))
                        client_res = cur.fetchone()
                        if client_res:
                            client_id = client_res[0]
                            data_to_save['client_id'] = client_id
                            cur.execute("SELECT id FROM devices WHERE serial_number = ?", (serial,))
                            exists = cur.fetchone()
                            if exists:
                                incoming_ts = data.get('last_modified', '')
                                cur.execute("SELECT last_modified FROM devices WHERE id=? ", (exists[0],))
                                existing_ts = cur.fetchone()[0] or ""
                                if incoming_ts > existing_ts:
                                    clauses = ", ".join([f"{k}=?" for k in data_to_save.keys()])
                                    cur.execute(f"UPDATE devices SET {clauses} WHERE id=? ", (*data_to_save.values(), exists[0]))
                                    data_changed = True
                                    stats["devices"] += 1
                                    server_log(f"SERVER SYNC: Updated device {serial} (del={data.get('is_deleted')})")
                                else:
                                    server_log(f"SERVER SYNC: Ignored device {serial} (existing modified at {existing_ts} >= incoming {incoming_ts})")
                            else:
                                cols = ", ".join(data_to_save.keys())
                                placeholders = ", ".join(["?" for _ in data_to_save])
                                cur.execute(f"INSERT INTO devices ({cols}) VALUES ({placeholders}) ", list(data_to_save.values()))
                                data_changed = True
                                stats["devices"] += 1
                                server_log(f"SERVER SYNC: Inserted device {serial}")
                        else:
                            server_log(f"SERVER SYNC ERROR: Client {parent_cn} not found for device {serial}")
                            stats["errors"] += 1
                    else:
                        server_log(f"SERVER SYNC SKIP: Missing serial({serial}) or contract({parent_cn}) for device data: {json.dumps(data)}")
                        stats["errors"] += 1

                elif table == "users":
                    username = data.get('username')
                    if username:
                        cur.execute("SELECT id FROM users WHERE username = ?", (username,))
                        exists = cur.fetchone()
                        incoming_ts = data.get('last_modified', '')
                        if exists:
                            cur.execute("SELECT last_modified FROM users WHERE id=?", (exists[0],))
                            existing_ts = cur.fetchone()[0] or ""
                            if incoming_ts > existing_ts:
                                clauses = ", ".join([f"{k}=?" for k in data_to_save.keys()])
                                cur.execute(f"UPDATE users SET {clauses} WHERE id=?", (*data_to_save.values(), exists[0]))
                                data_changed = True
                                stats["users"] += 1
                        else:
                            cols = ", ".join(data_to_save.keys())
                            placeholders = ", ".join(["?" for _ in data_to_save])
                            cur.execute(f"INSERT INTO users ({cols}) VALUES ({placeholders})", list(data_to_save.values()))
                            data_changed = True
                            stats["users"] += 1

                elif table == "products":
                    u = data.get('uuid')
                    if u:
                        cur.execute("SELECT id FROM products WHERE uuid = ?", (u,))
                        exists = cur.fetchone()
                        incoming_ts = data.get('last_modified', '')
                        if exists:
                            cur.execute("SELECT last_modified FROM products WHERE id=?", (exists[0],))
                            existing_ts = cur.fetchone()[0] or ""
                            if incoming_ts >= existing_ts:
                                clauses = ", ".join([f"{k}=?" for k in data_to_save.keys()])
                                cur.execute(f"UPDATE products SET {clauses} WHERE id=?", (*data_to_save.values(), exists[0]))
                                data_changed = True
                                stats["products"] += 1
                        else:
                            cols = ", ".join(data_to_save.keys())
                            placeholders = ", ".join(["?" for _ in data_to_save])
                            cur.execute(f"INSERT INTO products ({cols}) VALUES ({placeholders})", list(data_to_save.values()))
                            data_changed = True
                            stats["products"] += 1

                elif table == "repair_history":
                    serial = data.get('serial_number')
                    if serial:
                        cur.execute("SELECT id FROM devices WHERE serial_number = ?", (serial,))
                        dev_res = cur.fetchone()
                        if dev_res:
                            dev_id = dev_res[0]
                            r_date = data.get('repair_date')
                            prob = data.get('problem_description')
                            cur.execute("SELECT id FROM repair_history WHERE device_id=? AND repair_date=? AND problem_description=?", (dev_id, r_date, prob))
                            if not cur.fetchone():
                                rh_data = {k: v for k, v in data_to_save.items() if k != 'serial_number'}
                                rh_data['device_id'] = dev_id
                                cols = ", ".join(rh_data.keys())
                                placeholders = ", ".join(["?" for _ in rh_data])
                                cur.execute(f"INSERT INTO repair_history ({cols}) VALUES ({placeholders})", list(rh_data.values()))
                                data_changed = True
                                stats["repairs"] += 1

                elif table == "audit_logs":
                    ts, user, act = data.get('timestamp'), data.get('username'), data.get('action')
                    if ts and user and act:
                        cur.execute("SELECT id FROM audit_logs WHERE timestamp=? AND username=? AND action=?", (ts, user, act))
                        if not cur.fetchone():
                            cols, placeholders = ", ".join(data_to_save.keys()), ", ".join(["?" for _ in data_to_save])
                            cur.execute(f"INSERT INTO audit_logs ({cols}) VALUES ({placeholders})", list(data_to_save.values()))
                            data_changed = True
                            stats["audit_logs"] += 1

                elif table == "certificates":
                    num = data.get('number')
                    if num:
                        cur.execute("SELECT id FROM certificates WHERE number = ?", (num,))
                        exists = cur.fetchone()
                        incoming_ts = data.get('last_modified', '')
                        if exists:
                            cur.execute("SELECT last_modified FROM certificates WHERE id=?", (exists[0],))
                            existing_ts = cur.fetchone()[0] or ""
                            if incoming_ts > existing_ts:
                                clauses = ", ".join([f"{k}=?" for k in data_to_save.keys()])
                                cur.execute(f"UPDATE certificates SET {clauses} WHERE id=?", (*data_to_save.values(), exists[0]))
                                data_changed = True
                                stats["certificates"] += 1
                        else:
                            cols, placeholders = ", ".join(data_to_save.keys()), ", ".join(["?" for _ in data_to_save])
                            cur.execute(f"INSERT INTO certificates ({cols}) VALUES ({placeholders})", list(data_to_save.values()))
                            data_changed = True
                            stats["certificates"] += 1

                elif table == "global_settings":
                    key, val = data.get('key'), data.get('value')
                    if key:
                        cur.execute("SELECT last_modified FROM global_settings WHERE key = ?", (key,))
                        exists = cur.fetchone()
                        incoming_ts = data.get('last_modified', '')
                        if exists:
                            if incoming_ts > (exists[0] or ""):
                                cur.execute("UPDATE global_settings SET value = ?, last_modified = ? WHERE key = ?", (val, incoming_ts, key))
                                data_changed = True
                                stats["global_settings"] += 1
                        else:
                            cur.execute("INSERT INTO global_settings (key, value, last_modified) VALUES (?, ?, ?)", (key, val, incoming_ts))
                            data_changed = True
                            stats["global_settings"] += 1

                elif table == "invoices":
                    u = data.get('uuid')
                    if u:
                        cur.execute("SELECT id, last_modified FROM invoices WHERE uuid = ?", (u,))
                        exists = cur.fetchone()
                        incoming_ts = data.get('last_modified', '')
                        if exists:
                            if incoming_ts > (exists[1] or ""):
                                clauses = ", ".join([f"{k}=?" for k in data_to_save.keys()])
                                cur.execute(f"UPDATE invoices SET {clauses} WHERE id=?", (*data_to_save.values(), exists[0]))
                                data_changed = True
                                stats["invoices"] = stats.get("invoices", 0) + 1
                        else:
                            cols, placeholders = ", ".join(data_to_save.keys()), ", ".join(["?" for _ in data_to_save])
                            cur.execute(f"INSERT INTO invoices ({cols}) VALUES ({placeholders})", list(data_to_save.values()))
                            data_changed = True
                            stats["invoices"] = stats.get("invoices", 0) + 1

                elif table == "invoice_items":
                    p_uuid = data.get('parent_invoice_uuid')
                    if p_uuid:
                        cur.execute("SELECT id FROM invoices WHERE uuid = ?", (p_uuid,))
                        inv_res = cur.fetchone()
                        if inv_res:
                            inv_id = inv_res[0]
                            # Simple logic: clear items for this invoice first time we see it in this push
                            if not hasattr(req, '_cleared_inv_ids'): req._cleared_inv_ids = set()
                            if inv_id not in req._cleared_inv_ids:
                                cur.execute("DELETE FROM invoice_items WHERE invoice_id = ?", (inv_id,))
                                req._cleared_inv_ids.add(inv_id)
                            
                            item_data = {k: v for k, v in data_to_save.items() if k != 'parent_invoice_uuid'}
                            item_data['invoice_id'] = inv_id
                            cols, placeholders = ", ".join(item_data.keys()), ", ".join(["?" for _ in item_data])
                            cur.execute(f"INSERT INTO invoice_items ({cols}) VALUES ({placeholders})", list(item_data.values()))
                            data_changed = True

                elif table == "counterparties":
                    u = data.get('uuid')
                    if u:
                        cur.execute("SELECT id, last_modified FROM counterparties WHERE uuid = ?", (u,))
                        exists = cur.fetchone()
                        incoming_ts = data.get('last_modified', '')
                        if exists:
                            if incoming_ts > (exists[1] or ""):
                                clauses = ", ".join([f"{k}=?" for k in data_to_save.keys()])
                                cur.execute(f"UPDATE counterparties SET {clauses} WHERE id=?", (*data_to_save.values(), exists[0]))
                                data_changed = True
                                stats["counterparties"] = stats.get("counterparties", 0) + 1
                        else:
                            cols, placeholders = ", ".join(data_to_save.keys()), ", ".join(["?" for _ in data_to_save])
                            cur.execute(f"INSERT INTO counterparties ({cols}) VALUES ({placeholders})", list(data_to_save.values()))
                            data_changed = True
                            stats["counterparties"] = stats.get("counterparties", 0) + 1

                elif table == "handover_protocols":
                    u = data.get('uuid')
                    if u:
                        cur.execute("SELECT id, last_modified FROM handover_protocols WHERE uuid = ?", (u,))
                        exists = cur.fetchone()
                        
                        cp_uuid = data.get('counterparty_uuid')
                        local_cp_id = None
                        if cp_uuid:
                            cur.execute("SELECT id FROM counterparties WHERE uuid = ?", (cp_uuid,))
                            cp_res = cur.fetchone()
                            if cp_res: local_cp_id = cp_res[0]
                        
                        protocol_data = {k: v for k, v in data_to_save.items() if k != 'counterparty_uuid'}
                        if local_cp_id: protocol_data['counterparty_id'] = local_cp_id
                        
                        incoming_ts = data.get('last_modified', '')
                        if exists:
                            if incoming_ts > (exists[1] or ""):
                                clauses = ", ".join([f"{k}=?" for k in protocol_data.keys()])
                                cur.execute(f"UPDATE handover_protocols SET {clauses} WHERE id=?", (*protocol_data.values(), exists[0]))
                                data_changed = True
                                stats["protocols"] = stats.get("protocols", 0) + 1
                        else:
                            cols, placeholders = ", ".join(protocol_data.keys()), ", ".join(["?" for _ in protocol_data])
                            cur.execute(f"INSERT INTO handover_protocols ({cols}) VALUES ({placeholders})", list(protocol_data.values()))
                            data_changed = True
                            stats["protocols"] = stats.get("protocols", 0) + 1
            except Exception as e:
                print(f"SERVER SYNC ITEM ERROR ({table}): {e}")
                stats["errors"] += 1

        if data_changed:
            con.commit()
            server_log(f"SERVER SYNC: Push processed. Stats: {stats}")
            signals.data_pushed.emit()
        elif any(v > 0 for k, v in stats.items() if k != "errors"):
            server_log(f"SERVER SYNC: Push finished (No changes). Stats: {stats}")
            
    except Exception as e:
        if con: con.rollback()
        server_log(f"SERVER SYNC CRITICAL ERROR: {e}", use_traceback=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if con: con.close()
    return {"message": "Sync successful", "stats": stats, "server_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

class ServerThread(threading.Thread):
    def __init__(self, host="0.0.0.0", port=8000):
        super().__init__()
        self.host, self.port = host, port
        self.should_stop = False
        
    def run(self):
        try:
            print(f"Starting server on {self.host}:{self.port}...")
            config = uvicorn.Config(app, host=self.host, port=self.port, log_level="critical", loop="asyncio", log_config=None)
            self.server = uvicorn.Server(config)
            self.server.run()
        except Exception as e:
            print(f"SERVER ERROR: {e}")
        
    def stop(self):
        if hasattr(self, 'server'):
            self.server.should_exit = True
