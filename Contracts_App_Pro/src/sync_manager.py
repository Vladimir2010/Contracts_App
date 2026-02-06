import requests
import json
import os
import threading
import time
from datetime import datetime
from PyQt6.QtCore import QObject, pyqtSignal
from database import get_connection

# Settings file to store server URL
from path_utils import get_app_root
SETTINGS_PATH = os.path.join(get_app_root(), "data", "sync_settings.json")

class SyncManager(QObject):
    sync_started = pyqtSignal()
    sync_finished = pyqtSignal(bool, str) # success, message
    status_changed = pyqtSignal(str) # "online", "offline", "syncing"

    def __init__(self):
        super().__init__()
        self.mode = "client" # Default
        self.server_url = self.load_server_url()
        self.last_sync_time = "2000-01-01T00:00:00"
        self.is_running = False
        self.thread = None

    def load_server_url(self):
        if os.path.exists(SETTINGS_PATH):
            try:
                with open(SETTINGS_PATH, 'r') as f:
                    data = json.load(f)
                    self.mode = data.get("mode", "client")
                    self.last_sync_time = data.get("last_sync_time", "2000-01-01T00:00:00")
                    return data.get("server_url", "http://localhost:8000")
            except:
                return "http://localhost:8000"
        return "http://localhost:8000"

    def save_settings(self, url, mode):
        # Sanitize URL: remove trailing slash and /status if user pasted full browser link
        url = url.strip()
        if url.endswith("/"):
            url = url[:-1]
        if url.endswith("/status"):
            url = url[:-7]
            
        self.server_url = url
        self.mode = mode
        os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
        with open(SETTINGS_PATH, 'w') as f:
            json.dump({
                "server_url": url, 
                "mode": mode,
                "last_sync_time": self.last_sync_time
            }, f)

    def sync_now(self):
        """Manually trigger a sync iteration"""
        if self.mode == "server":
            return
        
        # Run in a separate thread to not block UI
        threading.Thread(target=self._perform_sync_iteration, daemon=True).start()

    def _perform_sync_iteration(self):
        try:
            # Check connection
            requests.get(f"{self.server_url}/status", timeout=2)
            self.status_changed.emit("online")
            
            # Perform Sync
            self.sync_started.emit()
            self.status_changed.emit("syncing")
            
            self.push_changes()
            self.pull_changes()
            
            self.last_sync_time = datetime.now().isoformat()
            # Persist last sync time
            self.save_settings(self.server_url, self.mode)
            
            self.sync_finished.emit(True, "Sync successful")
            self.status_changed.emit("online")
            
        except requests.exceptions.RequestException:
            self.status_changed.emit("offline")
            self.sync_finished.emit(False, "No connection to server")
        except Exception as e:
            self.sync_finished.emit(False, str(e))
            self.status_changed.emit("online")

    def start_background_sync(self):
        """Start the sync loop in background"""
        if self.mode == "server":
            return # Server doesn't sync with itself in this logic
            
        self.is_running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.is_running = False

    def _run_loop(self):
        while self.is_running:
            self._perform_sync_iteration()
            
            # Sleep for 60 seconds before next sync
            for _ in range(60):
                if not self.is_running: break
                time.sleep(1)

    def push_changes(self):
        con = get_connection()
        cur = con.cursor()
        
        # 1. Get modified clients
        cur.execute("SELECT * FROM clients WHERE last_modified > ?", (self.last_sync_time,))
        cols = [d[0] for d in cur.description]
        clients = [dict(zip(cols, row)) for row in cur.fetchall()]
        
        # 2. Get modified devices with their parent client's contract number
        cur.execute("""
            SELECT d.*, c.contract_number as parent_contract_number 
            FROM devices d
            JOIN clients c ON d.client_id = c.id
            WHERE d.last_modified > ?
        """, (self.last_sync_time,))
        cols = [d[0] for d in cur.description]
        devices = []
        for row in cur.fetchall():
            d_dict = dict(zip(cols, row))
            devices.append(d_dict)
        
        con.close()
        
        if not clients and not devices:
            return

        payload = {
            "client_id": "desktop_client", # Identify who we are?
            "items": []
        }
        
        for c in clients:
            payload["items"].append({"table": "clients", "data": c})
        for d in devices:
            payload["items"].append({"table": "devices", "data": d})
            
        try:
            requests.post(f"{self.server_url}/sync/push", json=payload, timeout=5)
        except Exception:
            pass

    def pull_changes(self):
        resp = requests.post(
            f"{self.server_url}/sync/pull", 
            json={"last_sync_time": self.last_sync_time}
        )
        if not resp.ok: return
        
        data = resp.json()
        con = get_connection()
        cur = con.cursor()
        
        # Apply changes locally
        # CAUTION: Need to handle conflicts or potential ID clashes
        # Ideally we use contract number/serial as logic keys
        
        # For prototype, we just upsert based on business keys or update if ID matches?
        # Since ID sync is hard without UUIDs, we will rely on business logic keys mostly
        
        for client in data.get("clients", []):
            # Upsert by contract_number - strict check
            cn = client.get('contract_number')
            if not cn: continue
            
            cur.execute("SELECT id FROM clients WHERE contract_number = ?", (cn,))
            exists = cur.fetchone()
            
            clean_data = {k: v for k, v in client.items() if k != 'id'}
            
            if exists:
                # Check timestamp
                incoming_ts = client.get('last_modified', '')
                cur.execute("SELECT last_modified FROM clients WHERE id=?", (exists[0],))
                existing_ts = cur.fetchone()[0]
                if not existing_ts: existing_ts = ""
                
                if incoming_ts > existing_ts:
                    clauses = ", ".join([f"{k}=?" for k in clean_data.keys()])
                    vals = list(clean_data.values()) + [exists[0]]
                    cur.execute(f"UPDATE clients SET {clauses} WHERE id=?", vals)
                else:
                    pass
            else:
                cols = ", ".join(clean_data.keys())
                placeholders = ", ".join(["?"] * len(clean_data))
                cur.execute(f"INSERT INTO clients ({cols}) VALUES ({placeholders})", list(clean_data.values()))

        # For devices - match by serial number
        for device in data.get("devices", []):
            sn = device.get('serial_number')
            if not sn: continue
            
            cur.execute("SELECT id FROM devices WHERE serial_number = ?", (sn,))
            exists = cur.fetchone()
            
            clean_data = {k: v for k, v in device.items() if k != 'id'}
            
            if exists:
                # Check timestamp - Last Write Wins
                incoming_ts = device.get('last_modified', '')
                cur.execute("SELECT last_modified FROM devices WHERE id=?", (exists[0],))
                existing_ts = cur.fetchone()[0]
                if not existing_ts: existing_ts = ""
                
                if incoming_ts > existing_ts:
                    clauses = ", ".join([f"{k}=?" for k in clean_data.keys()])
                    vals = list(clean_data.values()) + [exists[0]]
                    cur.execute(f"UPDATE devices SET {clauses} WHERE id=?", vals)
                else:
                    pass
            else:
                # We need to map server client_id to local client_id via contract_number or similar
                # Since we don't have contract_number in device payload directly, we skip insert to avoid orphans
                pass 
                
        con.commit()
        con.close()
