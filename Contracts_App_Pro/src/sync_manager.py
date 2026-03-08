import requests
import json
import os
import threading
import time
from datetime import datetime
from PyQt6.QtCore import QObject, pyqtSignal
from database import get_connection

# Settings file to store server URL
from path_utils import get_app_root, get_data_root
SETTINGS_PATH = os.path.join(get_data_root(), "data", "sync_settings.json")

class SyncManager(QObject):
    sync_started = pyqtSignal()
    sync_finished = pyqtSignal(bool, str) # success, message
    status_changed = pyqtSignal(str) # "online", "offline", "syncing"

    def __init__(self):
        super().__init__()
        self.mode = "client" # Default
        self.server_url = "http://localhost:8000"
        self.last_sync_time = "2000-01-01 00:00:00"
        self.load_settings()
        self.is_running = False
        self.thread = None
        self.sync_event = threading.Event()

    def load_settings(self):
        """Load settings from disk and update internal state"""
        if os.path.exists(SETTINGS_PATH):
            try:
                with open(SETTINGS_PATH, 'r') as f:
                    data = json.load(f)
                    self.mode = data.get("mode", "client")
                    self.server_url = data.get("server_url", "http://localhost:8000")
                    self.last_sync_time = data.get("last_sync_time", "2000-01-01 00:00:00")
                    # Convert T back to space if found in old settings
                    self.last_sync_time = self.last_sync_time.replace('T', ' ')
                    print(f"SYNC INFO: Settings loaded. Mode: {self.mode}, Server: {self.server_url}")
            except Exception as e:
                print(f"SYNC ERROR: Failed to load settings: {e}")
        else:
            print("SYNC INFO: No settings file found, using defaults.")

    def reload_settings(self):
        """Public method to refresh settings from disk"""
        self.load_settings()

    def save_settings(self, url, mode):
        # Sanitize URL: remove trailing slash and /status if user pasted full browser link
        url = url.strip()
        if url:
            # Add http:// if missing
            if not url.lower().startswith("http"):
                url = f"http://{url}"
            # Remove trailing slash
            if url.endswith("/"):
                url = url[:-1]
            # Remove /status if entered
            if url.endswith("/status"):
                url = url[:-7]
            
        self.server_url = url or "http://localhost:8000"
        self.mode = mode
        os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
        with open(SETTINGS_PATH, 'w') as f:
            json.dump({
                "server_url": self.server_url, 
                "mode": mode,
                "last_sync_time": self.last_sync_time
            }, f)
        print(f"SYNC INFO: Settings saved to {SETTINGS_PATH}. Mode: {mode}, URL: {self.server_url}")

    def sync_now(self):
        """Manually trigger a sync iteration immediately"""
        if self.is_running:
            print("SYNC INFO: Manual sync trigger received, waking up loop...")
            self.sync_event.set()
        else:
            print("SYNC INFO: Manual sync trigger received, starting iteration...")
            self.perform_sync_iteration()

    def perform_sync_iteration(self):
        """Manually trigger a sync iteration (alias for main.py)"""
        if self.mode == "server":
            return
        
        # Run in a separate thread to not block UI
        threading.Thread(target=self._perform_sync_iteration, daemon=True).start()

    def _perform_sync_iteration(self):
        try:
            # Capturing start time to avoid missing records added during sync
            sync_start = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Check connection
            print(f"SYNC DEBUG: Testing connection to {self.server_url}/status")
            requests.get(f"{self.server_url}/status", timeout=5)
            self.status_changed.emit("online")
            
            # Perform Sync
            self.sync_started.emit()
            self.status_changed.emit("syncing")
            
            self.push_changes()
            new_count = self.pull_changes()
            
            self.last_sync_time = sync_start
            # Persist last sync time
            self.save_settings(self.server_url, self.mode)
            
            msg = "Sync successful"
            if new_count > 0:
                msg = f"Успешна синхронизация. Получени са {new_count} нови записа."
                
            self.sync_finished.emit(True, msg)
            self.status_changed.emit("online")
            
        except requests.exceptions.RequestException as e:
            import traceback
            print(f"SYNC CONNECTION ERROR Details:")
            print(f"  Attempted URL: {self.server_url}")
            print(f"  Exception: {str(e)}")
            traceback.print_exc()
            self.status_changed.emit("offline")
            self.sync_finished.emit(False, f"Няма връзка със сървъра ({self.server_url}): {e}")
        except Exception as e:
            import traceback
            print(f"SYNC UNKNOWN ERROR:")
            traceback.print_exc()
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
        self.sync_event.set()

    def _run_loop(self):
        print(f"SYNC INFO: Background sync started (Mode: {self.mode})")
        while self.is_running:
            self._perform_sync_iteration()
            
            # Wait for 60 seconds OR until sync_event is set
            self.sync_event.wait(timeout=60)
            self.sync_event.clear()

    def push_changes(self):
        print(f"SYNC DEBUG: push_changes starting. last_sync_time={self.last_sync_time}")
        con = get_connection()
        cur = con.cursor()
        
        # 1. Get modified clients (including deleted)
        cur.execute("SELECT * FROM clients WHERE last_modified >= ?", (self.last_sync_time,))
        cols = [d[0] for d in cur.description]
        clients = [dict(zip(cols, row)) for row in cur.fetchall()]
        
        # 2. Get modified devices (including deleted) with their parent client's contract number
        cur.execute("""
            SELECT d.*, c.contract_number as parent_contract_number 
            FROM devices d
            JOIN clients c ON d.client_id = c.id
            WHERE d.last_modified >= ?
        """, (self.last_sync_time,))
        cols = [d[0] for d in cur.description]
        devices = [dict(zip(cols, row)) for row in cur.fetchall()]
        
        print(f"SYNC DEBUG: Found {len(clients)} clients and {len(devices)} devices modified in DB since {self.last_sync_time}")
        for c in clients:
            print(f"  - Client to push: {c.get('contract_number')} ({c.get('company_name')})")
        for d in devices:
            sn = d.get('serial_number')
            p_cn = d.get('parent_contract_number')
            if not sn:
                print(f"  - !!! WARNING: Device has EMPTY serial number for contract {p_cn} !!!")
                print(f"    Full data: {json.dumps(d)}")
            else:
                print(f"  - Device to push: {sn} for contract {p_cn}")
        
        # 3. Get modified users
        cur.execute("SELECT * FROM users WHERE last_modified >= ?", (self.last_sync_time,))
        cols = [d[0] for d in cur.description]
        users = [dict(zip(cols, row)) for row in cur.fetchall()]

        # 4. Get modified products
        cur.execute("SELECT * FROM products WHERE last_modified >= ?", (self.last_sync_time,))
        cols = [d[0] for d in cur.description]
        products = [dict(zip(cols, row)) for row in cur.fetchall()]

        # 5. Get modified repair history
        cur.execute("""
            SELECT r.*, d.serial_number 
            FROM repair_history r
            JOIN devices d ON r.device_id = d.id
            WHERE r.last_modified >= ?
        """, (self.last_sync_time,))
        cols = [d[0] for d in cur.description]
        repairs = [dict(zip(cols, row)) for row in cur.fetchall()]

        # 6. Get modified certificates
        cur.execute("SELECT * FROM certificates WHERE last_modified >= ?", (self.last_sync_time,))
        cols = [d[0] for d in cur.description]
        certificates = [dict(zip(cols, row)) for row in cur.fetchall()]

        # 7. Get modified global settings
        cur.execute("SELECT * FROM global_settings WHERE last_modified >= ?", (self.last_sync_time,))
        cols = [d[0] for d in cur.description]
        settings = [dict(zip(cols, row)) for row in cur.fetchall()]

        # 8. Get modified audit logs
        cur.execute("SELECT * FROM audit_logs WHERE timestamp > ?", (self.last_sync_time,))
        cols = [d[0] for d in cur.description]
        audit_logs = [dict(zip(cols, row)) for row in cur.fetchall()]

        # 9. Get modified invoices with items
        cur.execute("SELECT * FROM invoices WHERE last_modified >= ?", (self.last_sync_time,))
        cols = [d[0] for d in cur.description]
        invoices = [dict(zip(cols, row)) for row in cur.fetchall()]
        
        # Attach items to each invoice (we'll push them as a nested structure or separate table)
        # For simplicity and to match the server's existing pattern, let's push invoice_items separately 
        # but with the parent invoice's uuid.
        invoice_items = []
        for inv in invoices:
            cur.execute("SELECT * FROM invoice_items WHERE invoice_id = ?", (inv['id'],))
            i_cols = [d[0] for d in cur.description]
            for item_row in cur.fetchall():
                item_dict = dict(zip(i_cols, item_row))
                item_dict['parent_invoice_uuid'] = inv['uuid']
                invoice_items.append(item_dict)

        # 10. Get modified counterparties
        cur.execute("SELECT * FROM counterparties WHERE last_modified >= ?", (self.last_sync_time,))
        cols = [d[0] for d in cur.description]
        counterparties = [dict(zip(cols, row)) for row in cur.fetchall()]

        # 11. Get modified handover protocols
        cur.execute("""
            SELECT p.*, cp.uuid as counterparty_uuid 
            FROM handover_protocols p
            LEFT JOIN counterparties cp ON p.counterparty_id = cp.id
            WHERE p.last_modified >= ?
        """, (self.last_sync_time,))
        cols = [d[0] for d in cur.description]
        protocols = [dict(zip(cols, row)) for row in cur.fetchall()]
        
        con.close()
        
        if not any([clients, devices, users, products, repairs, certificates, audit_logs, settings, invoices, counterparties, protocols]):
            print("SYNC INFO: No local changes to push.")
            return

        payload = {
            "client_id": "desktop_client",
            "items": []
        }
        
        print(f"SYNC INFO: Pushing changes: {len(clients)} clients, {len(devices)} devices, {len(invoices)} invoices, {len(products)} products...")
        
        for c in clients:
            payload["items"].append({"table": "clients", "data": c})
        for d in devices:
            payload["items"].append({"table": "devices", "data": d})
        for u in users:
            payload["items"].append({"table": "users", "data": u})
        for p in products:
            payload["items"].append({"table": "products", "data": p})
        for r in repairs:
            payload["items"].append({"table": "repair_history", "data": r})
        for c in certificates:
            payload["items"].append({"table": "certificates", "data": c})
        for a in audit_logs:
            payload["items"].append({"table": "audit_logs", "data": a})
        for s in settings:
            payload["items"].append({"table": "global_settings", "data": s})
        for inv in invoices:
            payload["items"].append({"table": "invoices", "data": inv})
        for item in invoice_items:
            payload["items"].append({"table": "invoice_items", "data": item})
        for cp in counterparties:
            payload["items"].append({"table": "counterparties", "data": cp})
        for p in protocols:
            payload["items"].append({"table": "handover_protocols", "data": p})
            
        try:
            full_url = f"{self.server_url}/sync/push"
            print(f"SYNC DEBUG: Pushing to {full_url}")
            resp = requests.post(full_url, json=payload, timeout=5)
            if resp.ok:
                print("SYNC INFO: Push successful.")
            else:
                print(f"SYNC ERROR: Push failed with status {resp.status_code}: {resp.text}")
        except Exception as e:
            print(f"SYNC PUSH EXCEPTION: {e}")
            pass

    def pull_changes(self):
        print(f"SYNC INFO: Pulling changes since {self.last_sync_time}...")
        try:
            full_url = f"{self.server_url}/sync/pull"
            print(f"SYNC DEBUG: Pulling from {full_url}")
            resp = requests.post(
                full_url, 
                json={"last_sync_time": self.last_sync_time},
                timeout=5
            )
            if not resp.ok:
                print(f"SYNC ERROR: Pull failed with status {resp.status_code}")
                return 0
            
            data = resp.json()
            # Log what we got
            msg_parts = []
            for k, v in data.items():
                if v and isinstance(v, list):
                    msg_parts.append(f"{k}: {len(v)}")
            if msg_parts:
                print(f"SYNC INFO: Received new data: {', '.join(msg_parts)}")
            else:
                print("SYNC INFO: No new data from server.")

        except Exception as e:
            print(f"SYNC PULL EXCEPTION: {e}")
            return 0
            
        con = get_connection()
        cur = con.cursor()
        
        new_items_count = 0
        
        # 1. Clients Sync
        for client in data.get("clients", []):
            try:
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
                    existing_ts = cur.fetchone()[0] or ""
                    
                    if incoming_ts > existing_ts:
                        clauses = ", ".join([f"{k}=?" for k in clean_data.keys()])
                        vals = list(clean_data.values()) + [exists[0]]
                        cur.execute(f"UPDATE clients SET {clauses} WHERE id=?", vals)
                else:
                    cols = ", ".join(clean_data.keys())
                    placeholders = ", ".join(["?"] * len(clean_data))
                    cur.execute(f"INSERT INTO clients ({cols}) VALUES ({placeholders})", list(clean_data.values()))
                    new_items_count += 1
            except Exception as e:
                print(f"SYNC ERROR (Client {client.get('contract_number')}): {e}")

        # 2. For devices - match by serial number
        for device in data.get("devices", []):
            try:
                sn = device.get('serial_number')
                if not sn: continue
                
                cur.execute("SELECT id FROM devices WHERE serial_number = ?", (sn,))
                exists = cur.fetchone()
                
                # Resolve client_id locally using parent_contract_number
                p_cn = device.get('parent_contract_number')
                local_client_id = None
                if p_cn:
                    cur.execute("SELECT id FROM clients WHERE contract_number = ?", (p_cn,))
                    client_res = cur.fetchone()
                    if client_res:
                        local_client_id = client_res[0]
                
                # Clean data for DB (remove non-db columns)
                clean_data = {k: v for k, v in device.items() if k not in ['id', 'parent_contract_number']}
                if local_client_id:
                    clean_data['client_id'] = local_client_id
                
                if exists:
                    # Check timestamp - Last Write Wins
                    incoming_ts = device.get('last_modified', '')
                    cur.execute("SELECT last_modified FROM devices WHERE id=?", (exists[0],))
                    existing_ts = cur.fetchone()[0] or ""
                    
                    if incoming_ts > existing_ts:
                        clauses = ", ".join([f"{k}=?" for k in clean_data.keys()])
                        vals = list(clean_data.values()) + [exists[0]]
                        cur.execute(f"UPDATE devices SET {clauses} WHERE id=?", vals)
                else:
                    # Insert new device
                    if local_client_id:
                        cols = ", ".join(clean_data.keys())
                        placeholders = ", ".join(["?"] * len(clean_data))
                        cur.execute(f"INSERT INTO devices ({cols}) VALUES ({placeholders})", list(clean_data.values()))
                        new_items_count += 1
                    else:
                        print(f"SYNC WARNING: skipping new device {sn} because client {p_cn} not found locally.")
            except Exception as e:
                 print(f"SYNC ERROR (Device {device.get('serial_number')}): {e}")
                 
        con.commit()
        
        # 3. Users Sync (Upsert to avoid primary key collisions)
        for u in data.get("users", []):
            un = u.get('username')
            if not un: continue
            
            cur.execute("SELECT id, last_modified FROM users WHERE username = ?", (un,))
            exists = cur.fetchone()
            clean_data = {k: v for k, v in u.items() if k != 'id'}
            
            if exists:
                if (u.get('last_modified') or '') > (exists[1] or ''):
                     clauses = ", ".join([f"{k}=?" for k in clean_data.keys()])
                     vals = list(clean_data.values()) + [exists[0]]
                     cur.execute(f"UPDATE users SET {clauses} WHERE id=?", vals)
            else:
                 cols = ", ".join(clean_data.keys())
                 placeholders = ", ".join(["?"] * len(clean_data))
                 cur.execute(f"INSERT INTO users ({cols}) VALUES ({placeholders})", list(clean_data.values()))

        # 4. Products Sync (Match by uuid)
        for p in data.get("products", []):
            u = p.get('uuid')
            if not u: continue
            
            cur.execute("SELECT id, last_modified FROM products WHERE uuid = ?", (u,))
            exists = cur.fetchone()
            clean_data = {k: v for k, v in p.items() if k != 'id'}
            
            if exists:
                if (p.get('last_modified') or '') >= (exists[1] or ''):
                     clauses = ", ".join([f"{k}=?" for k in clean_data.keys()])
                     vals = list(clean_data.values()) + [exists[0]]
                     cur.execute(f"UPDATE products SET {clauses} WHERE id=?", vals)
            else:
                 cols = ", ".join(clean_data.keys())
                 placeholders = ", ".join(["?"] * len(clean_data))
                 cur.execute(f"INSERT INTO products ({cols}) VALUES ({placeholders})", list(clean_data.values()))
                 
        # 5. Repairs (Match by unique composite: device_id + date + problem)
        # We use the serial_number in the payload to find the local device_id
        for r in data.get("repair_history", []):
            sn = r.get('serial_number')
            if not sn: continue
            
            # Find local device_id
            cur.execute("SELECT id FROM devices WHERE serial_number = ?", (sn,))
            dev_res = cur.fetchone()
            if not dev_res: continue
            
            dev_id = dev_res[0]
            date_r = r.get('repair_date')
            prob = r.get('problem_description')
            
            cur.execute("SELECT id FROM repair_history WHERE device_id=? AND repair_date=? AND problem_description=?", (dev_id, date_r, prob))
            exists = cur.fetchone()
            
            clean_data = {k: v for k, v in r.items() if k not in ['id', 'serial_number']}
            clean_data['device_id'] = dev_id
            
            if not exists:
                 cols = ", ".join(clean_data.keys())
                 placeholders = ", ".join(["?"] * len(clean_data))
                 cur.execute(f"INSERT INTO repair_history ({cols}) VALUES ({placeholders})", list(clean_data.values()))

        # 6. Certificates (Match by number)
        for cert in data.get("certificates", []):
            num = cert.get('number')
            if not num: continue
            
            cur.execute("SELECT id, last_modified FROM certificates WHERE number = ?", (num,))
            exists = cur.fetchone()
            clean_data = {k: v for k, v in cert.items() if k != 'id'}
            
            if exists:
                if (cert.get('last_modified') or '') > (exists[1] or ''):
                     clauses = ", ".join([f"{k}=?" for k in clean_data.keys()])
                     vals = list(clean_data.values()) + [exists[0]]
                     cur.execute(f"UPDATE certificates SET {clauses} WHERE id=?", vals)
            else:
                 cols = ", ".join(clean_data.keys())
                 placeholders = ", ".join(["?"] * len(clean_data))
                 cur.execute(f"INSERT INTO certificates ({cols}) VALUES ({placeholders})", list(clean_data.values()))

        # 7. Audit Logs Sync (Match by timestamp, username, action)
        for a in data.get("audit_logs", []):
            ts = a.get('timestamp')
            user = a.get('username')
            act = a.get('action')
            
            if ts and user and act:
                cur.execute("SELECT id FROM audit_logs WHERE timestamp=? AND username=? AND action=?", (ts, user, act))
                if not cur.fetchone():
                    clean_data = {k: v for k, v in a.items() if k != 'id'}
                    cols = ", ".join(clean_data.keys())
                    placeholders = ", ".join(["?"] * len(clean_data))
                    cur.execute(f"INSERT INTO audit_logs ({cols}) VALUES ({placeholders})", list(clean_data.values()))

        # 8. Counterparties Sync (Match by uuid)
        for cp in data.get("counterparties", []):
            u = cp.get('uuid')
            if not u: continue
            cur.execute("SELECT id, last_modified FROM counterparties WHERE uuid = ?", (u,))
            exists = cur.fetchone()
            clean_data = {k: v for k, v in cp.items() if k != 'id'}
            if exists:
                if (cp.get('last_modified') or '') > (exists[1] or ''):
                    clauses = ", ".join([f"{k}=?" for k in clean_data.keys()])
                    cur.execute(f"UPDATE counterparties SET {clauses} WHERE id=?", list(clean_data.values()) + [exists[0]])
            else:
                cols, placeholders = ", ".join(clean_data.keys()), ", ".join(["?"] * len(clean_data))
                cur.execute(f"INSERT INTO counterparties ({cols}) VALUES ({placeholders})", list(clean_data.values()))

        # 9. Invoices Sync (Match by uuid)
        for inv in data.get("invoices", []):
            u = inv.get('uuid')
            if not u: continue
            cur.execute("SELECT id, last_modified FROM invoices WHERE uuid = ?", (u,))
            exists = cur.fetchone()
            clean_data = {k: v for k, v in inv.items() if k != 'id'}
            if exists:
                if (inv.get('last_modified') or '') > (exists[1] or ''):
                    clauses = ", ".join([f"{k}=?" for k in clean_data.keys()])
                    cur.execute(f"UPDATE invoices SET {clauses} WHERE id=?", list(clean_data.values()) + [exists[0]])
            else:
                cols, placeholders = ", ".join(clean_data.keys()), ", ".join(["?"] * len(clean_data))
                cur.execute(f"INSERT INTO invoices ({cols}) VALUES ({placeholders})", list(clean_data.values()))

        # 10. Invoice Items Sync (Follow parent invoices)
        # We'll just delete and re-insert items for any invoice that was in the payload
        for item in data.get("invoice_items", []):
            p_uuid = item.get('parent_invoice_uuid')
            if not p_uuid: continue
            cur.execute("SELECT id FROM invoices WHERE uuid = ?", (p_uuid,))
            inv_res = cur.fetchone()
            if inv_res:
                inv_id = inv_res[0]
                # To avoid duplicates, we'd need a way to identifying items. 
                # But since invoices are updated as a whole, we can clear items for inv_id once.
                # Let's track which invoices we've cleared items for in this sync session.
                if not hasattr(self, '_cleared_invoices'): self._cleared_invoices = set()
                if inv_id not in self._cleared_invoices:
                    cur.execute("DELETE FROM invoice_items WHERE invoice_id = ?", (inv_id,))
                    self._cleared_invoices.add(inv_id)
                
                clean_data = {k: v for k, v in item.items() if k not in ['id', 'parent_invoice_uuid']}
                clean_data['invoice_id'] = inv_id
                cols = ", ".join(clean_data.keys())
                placeholders = ", ".join(["?"] * len(clean_data))
                cur.execute(f"INSERT INTO invoice_items ({cols}) VALUES ({placeholders})", list(clean_data.values()))

        # 11. Handover Protocols (Match by uuid)
        for p in data.get("handover_protocols", []):
            u = p.get('uuid')
            if not u: continue
            cur.execute("SELECT id, last_modified FROM handover_protocols WHERE uuid = ?", (u,))
            exists = cur.fetchone()
            
            # Resolve counterparty_id locally
            cp_uuid = p.get('counterparty_uuid')
            local_cp_id = None
            if cp_uuid:
                cur.execute("SELECT id FROM counterparties WHERE uuid = ?", (cp_uuid,))
                cp_res = cur.fetchone()
                if cp_res: local_cp_id = cp_res[0]
            
            clean_data = {k: v for k, v in p.items() if k not in ['id', 'counterparty_uuid']}
            if local_cp_id: clean_data['counterparty_id'] = local_cp_id
            
            if exists:
                if (p.get('last_modified') or '') > (exists[1] or ''):
                    clauses = ", ".join([f"{k}=?" for k in clean_data.keys()])
                    cur.execute(f"UPDATE handover_protocols SET {clauses} WHERE id=?", list(clean_data.values()) + [exists[0]])
            else:
                cols, placeholders = ", ".join(clean_data.keys()), ", ".join(["?"] * len(clean_data))
                cur.execute(f"INSERT INTO handover_protocols ({cols}) VALUES ({placeholders})", list(clean_data.values()))

        if hasattr(self, '_cleared_invoices'): del self._cleared_invoices
        con.commit()
        con.close()
        return new_items_count
