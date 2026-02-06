import threading
import uvicorn
import os
from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import sqlite3
from datetime import datetime

# Import database functions safely
# We need to add the parent directory to path to import database if running directly
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

try:
    from database import get_connection, DB_PATH
except ImportError:
    # If standard import fails, try running as script
    pass

app = FastAPI(title="Contracts App Sync Server")

# Models
class SyncPullRequest(BaseModel):
    last_sync_time: str

class SyncPushItem(BaseModel):
    table: str
    data: Dict[str, Any]

class SyncPushRequest(BaseModel):
    client_id: str
    items: List[SyncPushItem]

# --- API Endpoints ---

@app.get("/status")
def status():
    return {"status": "running", "server_time": datetime.now().isoformat()}

@app.post("/sync/pull")
def pull_changes(req: SyncPullRequest):
    """Client asks for changes since last_sync_time"""
    con = get_connection()
    cur = con.cursor()
    
    response = {"clients": [], "devices": []}
    
    try:
        # Get changed clients
        cur.execute(f"SELECT * FROM clients WHERE last_modified > ?", (req.last_sync_time,))
        cols = [description[0] for description in cur.description]
        clients = [dict(zip(cols, row)) for row in cur.fetchall()]
        response["clients"] = clients
        
        # Get changed devices
        cur.execute(f"SELECT * FROM devices WHERE last_modified > ?", (req.last_sync_time,))
        cols = [description[0] for description in cur.description]
        devices = [dict(zip(cols, row)) for row in cur.fetchall()]
        response["devices"] = devices
        
    finally:
        con.close()
        
    return response

from PyQt6.QtCore import QObject, pyqtSignal

class ServerSignals(QObject):
    data_pushed = pyqtSignal()

# Global signals instance
signals = ServerSignals()

@app.post("/sync/push")
def push_changes(req: SyncPushRequest):
    """Client sends local changes to be merged"""
    con = get_connection()
    cur = con.cursor()
    
    try:
        data_changed = False
        for item in req.items:
            table = item.table
            data = item.data
            
            # Remove keys that shouldn't be pushed directly
            data_to_save = {k: v for k, v in data.items() if k not in ['id', 'parent_contract_number']}
            
            if table == "clients":
                contract_num = data.get('contract_number')
                if contract_num:
                    cur.execute("SELECT id FROM clients WHERE contract_number = ?", (contract_num,))
                    exists = cur.fetchone()
                    
                    if exists:
                        # Check timestamp for clients too
                        incoming_ts = data.get('last_modified', '')
                        cur.execute("SELECT last_modified FROM clients WHERE id=?", (exists[0],))
                        existing_ts = cur.fetchone()[0]
                        if not existing_ts: existing_ts = ""
                        
                        if incoming_ts > existing_ts:
                            clauses = ", ".join([f"{k}=?" for k in data_to_save.keys()])
                            values = list(data_to_save.values())
                            cur.execute(f"UPDATE clients SET {clauses} WHERE id=?", (*values, exists[0]))
                            data_changed = True
                        else:
                            pass
                    else:
                        cols = ", ".join(data_to_save.keys())
                        placeholders = ", ".join(["?" for _ in data_to_save])
                        cur.execute(f"INSERT INTO clients ({cols}) VALUES ({placeholders})", list(data_to_save.values()))
                        data_changed = True

            elif table == "devices":
                serial = data.get('serial_number')
                parent_cn = data.get('parent_contract_number')
                
                if serial and parent_cn:
                    # 1. Resolve client_id on server
                    cur.execute("SELECT id FROM clients WHERE contract_number = ?", (parent_cn,))
                    client_res = cur.fetchone()
                    
                    if client_res:
                        client_id = client_res[0]
                        data_to_save['client_id'] = client_id
                        
                        # 2. Check if device exists
                        cur.execute("SELECT id FROM devices WHERE serial_number = ?", (serial,))
                    if exists:
                        # Check timestamp to prevent overwriting newer data with old data
                        # We assume data['last_modified'] exists and is comparable string
                        incoming_ts = data.get('last_modified', '')
                        
                        # Fetch existing timestamp
                        cur.execute("SELECT last_modified FROM devices WHERE id=?", (exists[0],))
                        existing_ts = cur.fetchone()[0]
                        if not existing_ts: existing_ts = ""
                        
                        if incoming_ts > existing_ts:
                            clauses = ", ".join([f"{k}=?" for k in data_to_save.keys()])
                            values = list(data_to_save.values())
                            cur.execute(f"UPDATE devices SET {clauses} WHERE id=?", (*values, exists[0]))
                            data_changed = True
                        else:
                            # Server has newer or equal data, ignore client push for this item
                            pass
                    else:
                        cols = ", ".join(data_to_save.keys())
                        placeholders = ", ".join(["?" for _ in data_to_save])
                        cur.execute(f"INSERT INTO devices ({cols}) VALUES ({placeholders})", list(data_to_save.values()))
                        data_changed = True
                else:
                    pass
                        
        con.commit()
        if data_changed:
            signals.data_pushed.emit()
            
    except Exception as e:
        con.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        con.close()
        
    return {"message": "Sync successful", "server_time": datetime.now().isoformat()}

# --- Server Thread Class ---

class ServerThread(threading.Thread):
    def __init__(self, host="0.0.0.0", port=8000):
        super().__init__()
        self.signals = signals # Expose signals to main window
        self.host = host
        self.port = port
        self.should_stop = False
        
    def run(self):
        try:
            print(f"Starting server on {self.host}:{self.port}...")
            # Setup Server - specific config for non-blocking
            # Setup Server - specific config for non-blocking
            # log_config=None prevents uvicorn from trying to configure logging handlers (which crashes in no-console mode)
            config = uvicorn.Config(app, host=self.host, port=self.port, log_level="critical", loop="asyncio", log_config=None)
            self.server = uvicorn.Server(config)
            self.server.run()
        except Exception as e:
            print(f"SERVER ERROR: {e}")
        
    def stop(self):
        self.should_stop = True
        if hasattr(self, 'server'):
            self.server.should_exit = True
