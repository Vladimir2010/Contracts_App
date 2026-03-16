import sys
import os
import time
from datetime import datetime

# Safe stdout/stderr for windowed apps (prevents crashes in --noconsole mode)
if sys.stdout is None or sys.stderr is None:
    class StreamRedirector:
        def write(self, text): pass
        def flush(self): pass
        def isatty(self): return False
        def fileno(self): return -1
        @property
        def encoding(self): return 'utf-8'
        
    sys.stdout = StreamRedirector()
    sys.stderr = StreamRedirector()
    sys.stdin = StreamRedirector() # Using same dummy for stdin read (returns nothing)

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTableWidget, QTableWidgetItem,
    QPushButton, QVBoxLayout, QWidget, QHBoxLayout, QLineEdit,
    QCheckBox, QMessageBox, QFileDialog, QStatusBar, QMenu, QToolBar,
    QSplashScreen, QProgressBar, QLabel, QToolButton, QDialog, QComboBox,
    QTabWidget, QFrame, QGroupBox, QScrollArea, QGridLayout, QAbstractItemView
)
from PyQt6.QtCore import Qt, QTimer, QSize, QUrl
from PyQt6.QtGui import QAction, QIcon, QPixmap, QDesktopServices
from PyQt6.QtWidgets import QSystemTrayIcon
try:
    import winreg
except ImportError:
    winreg = None

from database import (
    init_db, get_all_devices, search_devices, delete_device,
    get_client_by_contract, get_devices_by_contract,
    get_all_products, search_products, delete_product, get_db_stats,
    get_all_invoices, get_invoice_details, update_invoice_payment, delete_invoice,
    get_next_invoice_number, add_invoice
)
from export_pdf import generate_invoice_pdf
from contract_generator import generate_service_contract, generate_nap_xml
from updater_client import check_for_updates, download_and_install_update, CURRENT_APP_VERSION, log_message
from dialogs import (
    AddDeviceDialog, EditDeviceDialog, AddToExistingContractDialog,
    ExpiringContractsDialog, SettingsDialog, LoginDialog, RepairProtocolDialog,
    ProductDialog, DuplicatePassportDialog, InvoiceDialog, ProtocolDialog
)
from importer import import_contracts_simple
from bim_loader import load_certificates_safe
from date_utils import format_date_bg
from path_utils import get_resource_path
from database import log_action
try:
    from server_thread import ServerThread
    from sync_manager import SyncManager
    import inspect
    if SyncManager:
        print(f"DEBUG: SyncManager loaded from: {inspect.getfile(SyncManager)}")
        # Check if perform_sync_iteration exists
        if not hasattr(SyncManager, 'perform_sync_iteration'):
            print("WARNING: SyncManager lacks perform_sync_iteration method!")
except ImportError as e:
    print(f"Sync modules not available: {e}")
    ServerThread = None
    SyncManager = None

try:
    from hotkey_manager import HotkeyManager
except ImportError as e:
    print(f"Hotkey manager not available: {e}")
    HotkeyManager = None

def set_autorun(enabled: bool):
    """Set the application to start automatically with Windows"""
    if winreg is None:
        return
        
    app_name = "ContractsApp"
    # Get the path to the executable
    if getattr(sys, 'frozen', False):
        # If running as EXE
        app_path = sys.executable
    else:
        # If running as script
        app_path = os.path.abspath(sys.argv[0])
        
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
        if enabled:
            winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, f'"{app_path}" --silent')
        else:
            try:
                winreg.DeleteValue(key, app_name)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
    except Exception as e:
        print(f"Error setting autorun: {e}")

from PyQt6.QtCore import QThread, pyqtSignal

class AutomationThread(QThread):
    """Background worker for automated tasks like monthly reports"""
    status_signal = pyqtSignal(str)

    def run(self):
        import time
        from datetime import datetime
        from path_utils import get_app_root, get_data_root
        from database import get_expiring_contracts
        from export_word import export_to_word
        from email_manager import send_email_with_attachment
        import json

        print("Automation Thread started...")
        
        while True:
            try:
                # 1. Load settings
                settings_path = os.path.join(get_data_root(), "data", "settings.json")
                if not os.path.exists(settings_path):
                    time.sleep(3600)
                    continue
                
                with open(settings_path, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                
                auto_cfg = settings.get('automation', {})
                if not auto_cfg.get('auto_reports_enabled'):
                    time.sleep(3600)
                    continue
                
                # 2. Check timing
                now = datetime.now()
                target_day = auto_cfg.get('report_day', 10)
                last_sent = auto_cfg.get('last_report_month', "") # Format: "YYYY-MM"
                
                current_month = now.strftime("%Y-%m")
                
                # We send on the target day if not sent this month yet
                if now.day == target_day and last_sent != current_month and 9 <= now.hour <= 23:
                    print(f"Time to send monthly report: {current_month}")
                    
                    # 3. Generate Report (Expiring contracts for next month)
                    exp_month = now.month + 1 if now.month < 12 else 1
                    exp_year = now.year if now.month < 12 else now.year + 1
                    
                    data = get_expiring_contracts(exp_month, exp_year)
                    if data:
                        headers = ["№ Договор", "Фирма/Клиент", "ЕИК", "Град", "Адрес", "Име Обект", "Модел", "Сериен №", "ИН на ФУ", "Валидност БИМ"]
                        report_data = []
                        for row in data:
                            report_data.append((row[1], row[3], row[4], row[7], row[9], row[14], row[17], row[18], row[19], row[22]))

                        report_dir = os.path.join(get_data_root(), "data", "reports")
                        os.makedirs(report_dir, exist_ok=True)
                        report_file = os.path.join(report_dir, f"Expiring_Contracts_{current_month}.docx")
                        
                        title = f"Справка за изтичащи договори - {exp_month:02d}.{exp_year}"
                        if export_to_word(report_data, headers, report_file, title):
                            # 4. Send Email
                            smtp_cfg = {
                                'server': auto_cfg.get('smtp_server'),
                                'port': auto_cfg.get('smtp_port', 587),
                                'user': auto_cfg.get('smtp_user'),
                                'password': auto_cfg.get('smtp_password'),
                                'use_tls': auto_cfg.get('smtp_tls', True)
                            }
                            
                            recipient_str = auto_cfg.get('report_recipient', '')
                            all_recipients = [r.strip() for r in recipient_str.split(',') if r.strip()]
                            
                            if all_recipients:
                                subject = f"Месечна справка: {title}"
                                body = f"Здравейте,\n\nВ приложение ще намерите справка за договорите, чиято валидност изтича през {exp_month:02d}.{exp_year}.\n\nПоздрави,\nContracts App Automation"
                                
                                success = False
                                for recipient in all_recipients:
                                    if send_email_with_attachment(smtp_cfg, recipient, subject, body, report_file):
                                        print(f"Monthly report sent successfully to {recipient}!")
                                        success = True
                                
                                if success:
                                    settings['automation']['last_report_month'] = current_month
                                    with open(settings_path, 'w', encoding='utf-8') as f:
                                        json.dump(settings, f, ensure_ascii=False, indent=2)
                                    self.status_signal.emit("Месечният отчет бе изпратен.")
                                else:
                                    self.status_signal.emit("Грешка при изпращане на имейл отчет.")
                            else:
                                print("No recipients configured for monthly report.")
                        else:
                            print("Failed to generate report.")
                    else:
                        print("No expiring contracts found.")
                        settings['automation']['last_report_month'] = current_month
                        with open(settings_path, 'w', encoding='utf-8') as f:
                            json.dump(settings, f, ensure_ascii=False, indent=2)
                
                # 5. EXPIRING ALERTS (7, 14, 30 days)
                current_date_key = now.strftime("%Y-%m-%d")
                last_alert_date = auto_cfg.get('last_alert_date', "")
                
                if last_alert_date != current_date_key and 8 <= now.hour <= 23:
                    print("Checking for 7/14/30 day expiry alerts...")
                    from database import get_contracts_expiring_in_days
                    
                    alert_intervals = {
                        7: auto_cfg.get('email_7d_ahead', True),
                        14: auto_cfg.get('email_14d_ahead', True),
                        30: auto_cfg.get('email_30d_ahead', True)
                    }
                    
                    # Custom Communication Templates
                    comm_cfg = settings.get('communication', {})
                    email_tpl_subject = comm_cfg.get('email_subject') or "⚠️ ВНИМАНИЕ: Договор(и) изтичащи след {days} дни!"
                    email_tpl_body = comm_cfg.get('email_body') or "Следните договори изтичат точно след {days} дни:\n\n{list}\n\nМоля, свържете се с клиентите за подновяване.\n\nПоздрави,\nContracts App Automation"
                    viber_tpl = comm_cfg.get('viber_template') or "⚠️ Изтичащи след {days} дни:\n{list}"
                    viber_token = comm_cfg.get('viber_token', "")
                    viber_receiver = comm_cfg.get('viber_receiver', "")

                    smtp_cfg = {
                        'server': auto_cfg.get('smtp_server'),
                        'port': auto_cfg.get('smtp_port', 587),
                        'user': auto_cfg.get('smtp_user'),
                        'password': auto_cfg.get('smtp_password'),
                        'use_tls': auto_cfg.get('smtp_tls', True)
                    }
                    recipient = auto_cfg.get('report_recipient')
                    
                    any_alerts_sent = False
                    for days, enabled in alert_intervals.items():
                        if enabled:
                            exp_clients = get_contracts_expiring_in_days(days)
                            if exp_clients:
                                # Prepare list of clients
                                clients_list = ""
                                for c in exp_clients:
                                    clients_list += f"- {c['company_name']} (Договор № {c['contract_number']})\n"
                                
                                # 1. Email Alert
                                subject = email_tpl_subject.replace("{days}", str(days))
                                body = email_tpl_body.replace("{days}", str(days)).replace("{list}", clients_list)
                                
                                recipient_str = auto_cfg.get('report_recipient', '')
                                all_recipients = [r.strip() for r in recipient_str.split(',') if r.strip()]
                                
                                from email_manager import send_email_with_attachment
                                for recipient in all_recipients:
                                    if send_email_with_attachment(smtp_cfg, recipient, subject, body):
                                        print(f"Sent {days} day alert to {recipient}")
                                        any_alerts_sent = True
                                
                                # 2. Viber Alert
                                if viber_token and viber_receiver:
                                    from viber_manager import send_viber_message
                                    v_text = viber_tpl.replace("{days}", str(days)).replace("{list}", clients_list)
                                    send_viber_message(viber_token, viber_receiver, v_text)

                    # Update last alert date
                    settings['automation']['last_alert_date'] = current_date_key
                    with open(settings_path, 'w', encoding='utf-8') as f:
                        json.dump(settings, f, ensure_ascii=False, indent=2)
                        
                    if any_alerts_sent:
                        self.status_signal.emit("Изпратени са автоматични известия за изтичащи договори.")

            except Exception as e:
                print(f"Automation Error: {e}")
            
            time.sleep(3600)


def backup_database():
    """Backup database to backups/ folder (zipped)"""
    try:
        from database import DB_PATH
        import zipfile
        
        if not os.path.exists(DB_PATH):
            return

        backup_dir = os.path.join(os.path.dirname(DB_PATH), "..", "backups")
        os.makedirs(backup_dir, exist_ok=True)
        
        # Limit backups? (Optional, maybe keep last 30)
        
        now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_name = f"contracts_backup_{now_str}.zip"
        zip_path = os.path.join(backup_dir, zip_name)
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.write(DB_PATH, os.path.basename(DB_PATH))
            
        print(f"Database backed up to {zip_path}")
        
        
        # Cleanup old backups (keep last 50)
        backups = sorted([os.path.join(backup_dir, f) for f in os.listdir(backup_dir) if f.endswith('.zip')])
        if len(backups) > 50:
            for old in backups[:-50]:
                try: os.remove(old)
                except: pass
                
    except Exception as e:
        print(f"Backup failed: {e}")


class SplashScreen(QSplashScreen):
    def __init__(self):
        # Create a background pixmap (canvas)
        canvas_width = 700
        canvas_height = 500
        pixmap = QPixmap(canvas_width, canvas_height)
        pixmap.fill(Qt.GlobalColor.white)
        
        super().__init__(pixmap)
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint)
        
        # Load custom branding from settings.json
        from path_utils import get_app_root, get_data_root
        branding_title = "Регистър на\nфискални устройства"
        logo_path = get_resource_path('logo-d-d.jpg')
        
        settings_path = os.path.join(get_data_root(), "data", "settings.json")
        if os.path.exists(settings_path):
            try:
                import json
                with open(settings_path, 'r', encoding='utf-8') as f:
                    local_data = json.load(f)
                    branding = local_data.get('branding', {})
                    if branding.get('app_title'):
                        branding_title = branding.get('app_title').replace(" ", "\n", 1)
                    if branding.get('splash_path') and os.path.exists(branding.get('splash_path')):
                        logo_path = branding.get('splash_path')
            except: pass

        # Title Label
        self.titleLabel = QLabel(branding_title, self)
        self.titleLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.titleLabel.setStyleSheet("font-size: 32px; font-weight: bold; color: #2c3e50; margin-top: 20px;")
        self.titleLabel.setGeometry(0, 30, canvas_width, 100)
        
        # Logo Label
        self.logoLabel = QLabel(self)
        if os.path.exists(logo_path):
            original_pixmap = QPixmap(logo_path)
            # Adjust scaling for potential custom splash images
            scaled_logo = original_pixmap.scaled(600, 300, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.logoLabel.setPixmap(scaled_logo)
            self.logoLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
            # Center the logo
            logo_x = (canvas_width - scaled_logo.width()) // 2
            logo_y = 130 
            self.logoLabel.setGeometry(logo_x, logo_y, scaled_logo.width(), scaled_logo.height())
        
        # Layout for progress bar
        self.progressBar = QProgressBar(self)
        self.progressBar.setGeometry(40, canvas_height - 60, canvas_width - 80, 25)
        self.progressBar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progressBar.setStyleSheet("""
            QProgressBar {
                background-color: #f0f2f5;
                color: #2c3e50;
                border: 1px solid #d1d9e6;
                border-radius: 12px;
                text-align: center;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3498db, stop:1 #2ecc71);
                border-radius: 10px;
            }
        """)
        self.progressBar.setValue(0)

    def setProgress(self, value):
        """Smoothly increment progress bar to target value"""
        current_value = self.progressBar.value()
        if value > current_value:
            # Determine step size and speed based on the gap
            step = 1
            delay = 0.015
            
            for v in range(current_value + step, value + 1, step):
                self.progressBar.setValue(v)
                time.sleep(delay)
                QApplication.processEvents()
        else:
            self.progressBar.setValue(value)
            QApplication.processEvents()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Регистър на фискални устройства")
        self.setMinimumSize(1400, 800)
        self.apply_branding()
        
        # Create central tab widget
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        self.tabs.setStyleSheet("QTabBar::tab { height: 40px; width: 200px; font-weight: bold; }")
        
        # Create toolbar
        self.create_toolbar()
        
        # Tab 1: Devices
        self.device_tab = QWidget()
        self.setup_device_tab()
        self.tabs.addTab(self.device_tab, "🏢 Устройства")
        
        # Tab 2: Products
        self.product_tab = QWidget()
        self.setup_product_tab()
        self.tabs.addTab(self.product_tab, "📦 Продукти")
        
        # Tab 3: Invoices (New)
        self.invoice_tab = QWidget()
        self.setup_invoice_tab()
        self.tabs.addTab(self.invoice_tab, "🧾 Фактури")

        # Tab 4: Statistics
        self.stats_tab = QWidget()
        self.setup_stats_tab()
        self.tabs.addTab(self.stats_tab, "📊 Статистика")
        self.tabs.currentChanged.connect(self.on_tab_changed)
        
        # Shortcuts
        self.search_shortcut = QAction(self)
        self.search_shortcut.setShortcut("Ctrl+F")
        self.search_shortcut.triggered.connect(self.focus_search)
        self.addAction(self.search_shortcut)
        
        # New Device Shortcut
        self.new_device_shortcut = QAction(self)
        self.new_device_shortcut.setShortcut("Ctrl+N")
        self.new_device_shortcut.triggered.connect(self.add_device)
        self.addAction(self.new_device_shortcut)
        
        # Handover Protocol Shortcut
        self.proto_shortcut = QAction(self)
        self.proto_shortcut.setShortcut("Ctrl+P")
        self.proto_shortcut.triggered.connect(self.open_protocol)
        self.addAction(self.proto_shortcut)
        
        # Audit Log Shortcut
        self.audit_shortcut = QAction(self)
        self.audit_shortcut.setShortcut("Ctrl+H") # H for History
        self.audit_shortcut.triggered.connect(self.show_audit_log)
        self.addAction(self.audit_shortcut)
        
        # Sync Shortcut
        self.sync_shortcut = QAction(self)
        self.sync_shortcut.setShortcut("Ctrl+G") # G for Global Sync
        self.sync_shortcut.triggered.connect(self.perform_sync)
        self.addAction(self.sync_shortcut)
        
        # Settings Shortcut
        self.settings_shortcut = QAction(self)
        self.settings_shortcut.setShortcut("Ctrl+S")
        self.settings_shortcut.triggered.connect(self.show_settings)
        self.addAction(self.settings_shortcut)
        
        # Status bar
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("Готов")
        
        # Initial status
        self.refresh_table()
        self.refresh_products()
        
        self.current_user = None
        
        # Sync Integration
        self.server_thread = None
        self.sync_manager = None
        self.init_sync_system()
        
        # Tray Icon
        self.init_tray_icon()
        
        # Automation Thread
        self.automation_thread = AutomationThread()
        self.automation_thread.status_signal.connect(lambda msg: self.statusBar.showMessage(msg, 5000))
        self.automation_thread.start()
        
        # Check for updates automatically (3 seconds after startup to not freeze UI)
        QTimer.singleShot(3000, self.perform_update_check)
        
        # Initialize Global Hotkey
        if HotkeyManager:
            self.hotkey_mgr = HotkeyManager(self)
            self.hotkey_mgr.hotkey_triggered.connect(self.on_hotkey_triggered)
            self.hotkey_mgr.start()

    def perform_update_check(self, manual=False):
        """Checks for updates. If manual=True, shows a message even if no updates found."""
        try:
            if manual:
                self.statusBar.showMessage("Проверка за обновления...", 5000)
            
            log_message(f"Извикване на check_for_updates(manual={manual})...")
            has_update, new_version, url, notes = check_for_updates()
            log_message(f"Резултат: has_update={has_update}")
            
            if has_update:
                log_message("Показване на QMessageBox...")
                try:
                    msg = QMessageBox(self)
                    msg.setIcon(QMessageBox.Icon.Information)
                    msg.setWindowTitle("Налична е нова версия!")
                    msg.setText(f"Открита е нова версия <b>{new_version}</b> на програмата.")
                    
                    details = f"Вашата версия: {CURRENT_APP_VERSION}\nНова версия: {new_version}\n\nКакво ново:\n{notes}"
                    msg.setDetailedText(details)
                    
                    msg.setInformativeText("Искате ли да изтеглите и инсталирате обновлението сега? Програмата ще се рестартира автоматично.")
                    
                    yes_btn = msg.addButton("Да, обнови сега", QMessageBox.ButtonRole.AcceptRole)
                    msg.addButton("По-късно", QMessageBox.ButtonRole.RejectRole)
                    
                    log_message("Преди msg.exec()...")
                    msg.exec()
                    log_message("След msg.exec().")
                    
                    if msg.clickedButton() == yes_btn:
                        log_message("Потребителят избра 'Да'.")
                        # Proceed with download
                        from PyQt6.QtWidgets import QProgressDialog
                        progress = QProgressDialog("Изтегляне на новата версия...", "Отказ", 0, 0, self)
                        progress.setWindowTitle("Обновяване")
                        progress.setWindowModality(Qt.WindowModality.WindowModal)
                        progress.show()
                        
                        # Ensure UI updates before heavy download
                        QApplication.processEvents() 
                        
                        # We pass the token if defined in updater_client
                        from updater_client import GITHUB_ACCESS_TOKEN
                        token = GITHUB_ACCESS_TOKEN if "ТУК_ЩЕ" not in GITHUB_ACCESS_TOKEN else None
                        
                        log_message("Старт на download_and_install_update()...")
                        download_and_install_update(url, token)
                        
                        progress.close()
                        log_message("КРАЙ: Инсталаторът трябва да е стартиран.")
                except Exception as ex:
                    log_message(f"Грешка при показване на прозореца за ъпдейт: {ex}")
            
            elif manual:
                QMessageBox.information(self, "Обновяване", 
                    f"Имате последната версия на програмата (v{CURRENT_APP_VERSION}).")
                    
        except Exception as e:
            log_message(f"Грешка в perform_update_check: {e}")
            import traceback
            log_message(traceback.format_exc())

    def setup_device_tab(self):
        layout = QVBoxLayout()
        self.device_tab.setLayout(layout)
        
        # Create filter panel
        filter_panel = self.create_filter_panel()
        layout.addLayout(filter_panel)
        
        # Create table
        self.table = QTableWidget()
        self.table.setColumnCount(25)
        self.table.setHorizontalHeaderLabels([
            "ID", "№ Договор", "Статус", "Фирма", "ЕИК", "ДДС", "МОЛ", "Град", "ПК", "Адрес", 
            "Тел. 1", "Тел. 2", "Старт Договор", "Край Договор", "Име Обект", "Адрес Обект", "Тел. Обект",
            "Модел", "Сериен №", "ИН на ФУ", "Фис. Памет", "№ Свид. БИМ", "Валидност БИМ", "Евро", "НАП Отчет"
        ])
        
        # Hide ID column
        self.table.setColumnHidden(0, True)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        
        # Set column widths
        widths = [0, 80, 80, 200, 90, 50, 120, 80, 50, 200, 90, 90, 90, 90, 120, 200, 90, 120, 100, 100, 100, 80, 90, 50, 60]
        for i, w in enumerate(widths):
            self.table.setColumnWidth(i, w)
            
        self.table.doubleClicked.connect(self.edit_selected_device)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        
        layout.addWidget(self.table)

    def setup_product_tab(self):
        layout = QVBoxLayout()
        self.product_tab.setLayout(layout)
        
        # SEARCH ROW
        search_layout = QHBoxLayout()
        self.product_search = QLineEdit()
        self.product_search.setPlaceholderText("Търси продукт по име или категория...")
        self.product_search.textChanged.connect(self.refresh_products)
        search_layout.addWidget(self.product_search)
        
        btn_add = QPushButton("➕ Нов Продукт")
        btn_add.clicked.connect(self.add_product_action)
        search_layout.addWidget(btn_add)
        
        btn_export_price = QPushButton("📄 Ценова Листа")
        btn_export_price.clicked.connect(self.export_price_list_options)
        btn_export_price.setStyleSheet("background-color: #007bff; color: white;")
        search_layout.addWidget(btn_export_price)
        
        layout.addLayout(search_layout)
        
        # PRODUCT TABLE
        self.product_table = QTableWidget()
        self.product_table.setColumnCount(7)
        self.product_table.setHorizontalHeaderLabels([
            "ID", "Име", "Категория", "Цена", "Валута", "Цена (EUR)", "Описание"
        ])
        self.product_table.setColumnHidden(0, True)
        self.product_table.setSortingEnabled(True)
        self.product_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.product_table.horizontalHeader().setStretchLastSection(True)
        
        # Double click to edit
        self.product_table.doubleClicked.connect(self.edit_product_action)
        
        # Context menu
        self.product_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.product_table.customContextMenuRequested.connect(self.show_product_context_menu)
        
        layout.addWidget(self.product_table)

    def setup_invoice_tab(self):
        layout = QVBoxLayout()
        self.invoice_tab.setLayout(layout)
        
        # Tools row
        tools_layout = QHBoxLayout()
        
        self.invoice_search = QLineEdit()
        self.invoice_search.setPlaceholderText("Търси по номер на фактура или клиент...")
        # self.invoice_search.textChanged.connect(self.refresh_invoices)
        tools_layout.addWidget(self.invoice_search)
        
        btn_add = QPushButton("🧾 Нова Фактура")
        btn_add.clicked.connect(self.add_invoice_action)
        btn_add.setStyleSheet("background-color: #28a745; color: white; font-weight: bold; min-height: 30px;")
        tools_layout.addWidget(btn_add)
        
        btn_refresh = QPushButton("🔄 Обнови")
        btn_refresh.clicked.connect(self.refresh_invoices)
        tools_layout.addWidget(btn_refresh)
        
        layout.addLayout(tools_layout)
        
        # Invoice table
        self.invoice_table = QTableWidget()
        self.invoice_table.setColumnCount(8)
        self.invoice_table.setHorizontalHeaderLabels([
            "ID", "Номер", "Тип", "Дата", "Клиент", "Сума", "Статус", "Платена"
        ])
        self.invoice_table.setColumnHidden(0, True)
        self.invoice_table.setSortingEnabled(True)
        self.invoice_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.invoice_table.horizontalHeader().setStretchLastSection(True)
        
        # Set column widths
        widths = [0, 120, 100, 100, 300, 120, 120, 80]
        for i, w in enumerate(widths):
            self.invoice_table.setColumnWidth(i, w)
            
        self.invoice_table.doubleClicked.connect(self.view_invoice_action)
        self.invoice_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.invoice_table.customContextMenuRequested.connect(self.show_invoice_context_menu)
        
        layout.addWidget(self.invoice_table)

    def setup_stats_tab(self):
        layout = QVBoxLayout()
        self.stats_tab.setLayout(layout)
        
        # Scroll area for stats
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        container = QWidget()
        container_layout = QVBoxLayout(container)
        
        # 1. SUMMARY CARDS
        cards_layout = QGridLayout()
        
        self.card_active = self.create_stat_card("Активни договори", "0", "#2ecc71")
        self.card_expired = self.create_stat_card("Изтекли договори", "0", "#e74c3c")
        self.card_expiring = self.create_stat_card("Изтичащи (30 дни)", "0", "#f39c12")
        self.card_revenue = self.create_stat_card("Прогнозен месечен приход", "0.00 лв.", "#3498db")
        
        cards_layout.addWidget(self.card_active, 0, 0)
        cards_layout.addWidget(self.card_expired, 0, 1)
        cards_layout.addWidget(self.card_expiring, 1, 0)
        cards_layout.addWidget(self.card_revenue, 1, 1)
        
        container_layout.addLayout(cards_layout)
        
        # 2. DEVICE DISTRIBUTION
        dist_group = QGroupBox("Разпределение по модел")
        dist_layout = QVBoxLayout()
        self.dist_label = QLabel("Зареждане...")
        dist_layout.addWidget(self.dist_label)
        dist_group.setLayout(dist_layout)
        container_layout.addWidget(dist_group)
        
        # Refresh button
        btn_refresh = QPushButton("🔄 Обнови Статистиката")
        btn_refresh.setFixedWidth(200)
        btn_refresh.clicked.connect(self.refresh_stats)
        container_layout.addWidget(btn_refresh, 0, Qt.AlignmentFlag.AlignCenter)
        
        container_layout.addStretch()
        
        scroll.setWidget(container)
        layout.addWidget(scroll)

    def create_stat_card(self, title, value, color):
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: white;
                border-radius: 10px;
                border: 1px solid #dee2e6;
                padding: 20px;
            }}
        """)
        card_layout = QVBoxLayout(card)
        
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("color: #6c757d; font-size: 14px; font-weight: bold;")
        
        lbl_value = QLabel(value)
        lbl_value.setStyleSheet(f"color: {color}; font-size: 24px; font-weight: bold;")
        lbl_value.setObjectName("value_label")
        
        card_layout.addWidget(lbl_title)
        card_layout.addWidget(lbl_value)
        
        return card

    def refresh_invoices(self):
        """Load invoices from DB to table"""
        invoices = get_all_invoices()
        
        self.invoice_table.setSortingEnabled(False)
        self.invoice_table.setRowCount(0)
        
        for inv in invoices:
            row = self.invoice_table.rowCount()
            self.invoice_table.insertRow(row)
            
            # ID (hidden)
            self.invoice_table.setItem(row, 0, QTableWidgetItem(str(inv['id'])))
            
            # Number
            self.invoice_table.setItem(row, 1, QTableWidgetItem(inv['number']))
            
            # Type
            doc_type = "Фактура" if inv['type'] == 'INV' else "Проформа"
            self.invoice_table.setItem(row, 2, QTableWidgetItem(doc_type))
            
            # Date
            self.invoice_table.setItem(row, 3, QTableWidgetItem(format_date_bg(inv['date_issued'])))
            
            # Client
            self.invoice_table.setItem(row, 4, QTableWidgetItem(inv['client_name']))
            
            # Amount
            amount_item = QTableWidgetItem(f"{inv['total_amount']:.2f} {inv['currency']}")
            amount_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.invoice_table.setItem(row, 5, amount_item)
            
            # Status
            status_map = {
                'PENDING': '⏳ Изчакващ',
                'PAID': '✅ Платена',
                'OVERDUE': '⚠️ Просрочена',
                'PARTIAL': '🌗 Частично'
            }
            status_text = status_map.get(inv['payment_status'], inv['payment_status'])
            self.invoice_table.setItem(row, 6, QTableWidgetItem(status_text))
            
            # Paid Checkbox (visual only)
            is_paid = "Да" if inv.get('is_paid') == 1 else "Не"
            self.invoice_table.setItem(row, 7, QTableWidgetItem(is_paid))
            
        self.invoice_table.setSortingEnabled(True)

    def show_invoice_context_menu(self, pos):
        index = self.invoice_table.indexAt(pos)
        if not index.isValid(): return
        
        row = index.row()
        invoice_id = int(self.invoice_table.item(row, 0).text())
        
        menu = QMenu()
        view_act = menu.addAction("👁️ Преглед/Редакция")
        print_act = menu.addAction("🖨️ Издай (Печат)")
        menu.addSeparator()
        pay_act = menu.addAction("💰 Маркирай като платена")
        unpay_act = menu.addAction("🔄 Маркирай като неплатена")
        menu.addSeparator()
        del_act = menu.addAction("🗑️ Изтриване")
        
        action = menu.exec(self.invoice_table.viewport().mapToGlobal(pos))
        
        if action == view_act:
            self.view_invoice_action()
        elif action == print_act:
            self.print_invoice_action(invoice_id)
        elif action == pay_act:
            if update_invoice_payment(invoice_id, 'PAID', True):
                self.refresh_invoices()
        elif action == unpay_act:
            if update_invoice_payment(invoice_id, 'PENDING', False):
                self.refresh_invoices()
        elif action == del_act:
            if QMessageBox.question(self, "Потвърждение", "Сигурни ли сте, че искате да изтриете тази фактура?") == QMessageBox.StandardButton.Yes:
                if delete_invoice(invoice_id):
                    self.refresh_invoices()

    def view_invoice_action(self):
        # Selected row
        selected = self.invoice_table.selectionModel().selectedRows()
        if not selected: return
        
        row = selected[0].row()
        invoice_id = int(self.invoice_table.item(row, 0).text())
        
        # Get full details from DB
        invoice_details = get_invoice_details(invoice_id)
        if invoice_details:
            dialog = InvoiceDialog(self, invoice_data=invoice_details)
            if dialog.exec():
                self.refresh_invoices()

    def print_invoice_action(self, invoice_id):
        """Fetch invoice, generate PDF and open it directly"""
        invoice_details = get_invoice_details(invoice_id)
        if not invoice_details:
            QMessageBox.warning(self, "Грешка", "Не бе открита информация за фактурата.")
            return

        # Prepare data for PDF (Seller info from settings)
        from database import get_setting
        invoice_details['seller'] = {
            'name': get_setting('name', 'Д и Д Фискал Системс ЕООД'),
            'eik': get_setting('eik', '205634567'),
            'vat': get_setting('vat', 'BG205634567'),
            'city': get_setting('city', 'София'),
            'address': get_setting('address', 'гр. София, бул. България №1'),
            'mol': get_setting('mol', 'Александър Петров')
        }
        
        prefix = "Faktura" if invoice_details['type'] == 'INV' else "Proforma"
        default_name = f"{prefix}_{invoice_details['number']}.pdf"
        
        save_path = os.path.join(os.path.expanduser("~"), "Documents", "ContractsApp", "Invoices")
        os.makedirs(save_path, exist_ok=True)
        file_path = os.path.join(save_path, default_name)
        
        if generate_invoice_pdf(invoice_details, file_path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))
            log_action(self.current_user['id'], self.current_user['username'], "PRINT_INVOICE", f"Printed document {invoice_details['number']}")
        else:
            QMessageBox.critical(self, "Грешка", "Грешка при генериране на PDF!")

    def add_invoice_action(self):
        dialog = InvoiceDialog(self)
        if dialog.exec():
            self.refresh_invoices()
            if self.current_user:
                log_action(self.current_user['id'], self.current_user['username'], "CREATE_INVOICE", f"Created document")

    def refresh_stats(self):
        try:
            from database import get_db_stats
            stats = get_db_stats()
            
            # Update cards
            self.card_active.findChild(QLabel, "value_label").setText(str(stats['active_contracts']))
            self.card_expired.findChild(QLabel, "value_label").setText(str(stats['expired_contracts']))
            self.card_expiring.findChild(QLabel, "value_label").setText(str(stats['expiring_soon']))
            self.card_revenue.findChild(QLabel, "value_label").setText(f"{stats['monthly_revenue']:.2f} лв.")

            # Apply visibility from settings
            from path_utils import get_app_root, get_data_root
            settings_path = os.path.join(get_data_root(), "data", "settings.json")
            if os.path.exists(settings_path):
                import json
                try:
                    with open(settings_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        dash = data.get('dashboard', {})
                        self.card_active.setVisible(dash.get('show_active', True))
                        self.card_expired.setVisible(dash.get('show_expiring', True))
                        self.card_expiring.setVisible(dash.get('show_total', True)) 
                        self.card_revenue.setVisible(dash.get('show_recent', True))
                except: pass

            # Update distribution
            dist_text = ""
            for model, count in stats['model_dist'].items():
                percentage = (count / stats['total_devices'] * 100) if stats['total_devices'] > 0 else 0
                dist_text += f"<b>{model}</b>: {count} бр. ({percentage:.1f}%)\n"
            
            if not dist_text:
                dist_text = "Няма данни за устройства."
            self.dist_label.setText(dist_text)

        except Exception as e:
            print(f"Error refreshing stats: {e}")

    def apply_branding(self):
        """Load custom title from settings"""
        from path_utils import get_app_root, get_data_root
        settings_path = os.path.join(get_data_root(), "data", "settings.json")
        if os.path.exists(settings_path):
            try:
                import json
                with open(settings_path, 'r', encoding='utf-8') as f:
                    local_data = json.load(f)
                    branding = local_data.get('branding', {})
                    if branding.get('app_title'):
                        self.setWindowTitle(branding.get('app_title'))
            except: pass

    def on_tab_changed(self, index):
        if index == 0:
            self.refresh_table()
        elif index == 1:
            self.refresh_products()
        elif index == 2:
            self.refresh_invoices()
        elif index == 3:
            self.refresh_stats()

    def refresh_products(self):
        query = self.product_search.text().strip()
        if query:
            products = search_products(query)
        else:
            products = get_all_products()
            
        self.product_table.setSortingEnabled(False)
        self.product_table.setRowCount(0)
        
        for p in products:
            row = self.product_table.rowCount()
            self.product_table.insertRow(row)
            
            # Helper for ID
            item_id = QTableWidgetItem(str(p['id']))
            self.product_table.setItem(row, 0, item_id)
            
            self.product_table.setItem(row, 1, QTableWidgetItem(p['name']))
            self.product_table.setItem(row, 2, QTableWidgetItem(p['category'] or ""))
            
            # Formatting prices
            price = p['price']
            currency = p['currency']
            
            # Calculate EUR price if stored in BGN
            if currency == 'BGN':
                price_bgn = price
                price_eur = price / 1.95583
            else:
                price_eur = price
                price_bgn = price * 1.95583
                
            item_price = QTableWidgetItem(f"{price:.2f}")
            item_price.setData(Qt.ItemDataRole.UserRole, price)
            self.product_table.setItem(row, 3, item_price)
            
            self.product_table.setItem(row, 4, QTableWidgetItem(currency))
            
            item_eur = QTableWidgetItem(f"{price_eur:.2f}")
            self.product_table.setItem(row, 5, item_eur)
            
            self.product_table.setItem(row, 6, QTableWidgetItem(p['description'] or ""))
            
        self.product_table.setSortingEnabled(True)

    def add_product_action(self):
        dialog = ProductDialog(parent=self)
        if dialog.exec():
            self.refresh_products()
            if self.current_user:
                log_action(self.current_user['id'], self.current_user['username'], "ADD_PRODUCT", "Added new product")

    def edit_product_action(self):
        selected = self.product_table.selectionModel().selectedRows()
        if not selected:
            return
        row = selected[0].row()
        product_id = int(self.product_table.item(row, 0).text())
        
        # We need full product data for the dialog
        # For now, we can extract from table or ideally call database
        # Let's extract from table for simplicity as we have most data there
        data = {
            'id': product_id,
            'name': self.product_table.item(row, 1).text(),
            'category': self.product_table.item(row, 2).text(),
            'price': float(self.product_table.item(row, 3).text()),
            'currency': self.product_table.item(row, 4).text(),
            'description': self.product_table.item(row, 6).text()
        }
        
        dialog = ProductDialog(product_data=data, parent=self)
        if dialog.exec():
            self.refresh_products()
            if self.current_user:
                log_action(self.current_user['id'], self.current_user['username'], "EDIT_PRODUCT", f"Updated product: {data['name']}")

    def delete_product_action(self):
        selected = self.product_table.selectionModel().selectedRows()
        if not selected:
            return
            
        if QMessageBox.question(self, "Потвърждение", "Сигурни ли сте, че искате да изтриете този продукт?") == QMessageBox.StandardButton.Yes:
            row = selected[0].row()
            product_id = int(self.product_table.item(row, 0).text())
            if delete_product(product_id):
                self.refresh_products()
                if self.current_user:
                    log_action(self.current_user['id'], self.current_user['username'], "DELETE_PRODUCT", f"Deleted product ID: {product_id}")

    def show_product_context_menu(self, pos):
        index = self.product_table.indexAt(pos)
        if not index.isValid(): return
        
        menu = QMenu()
        edit_act = menu.addAction("✏️ Редактиране")
        del_act = menu.addAction("🗑️ Изтриване")
        
        action = menu.exec(self.product_table.viewport().mapToGlobal(pos))
        if action == edit_act:
            self.edit_product_action()
        elif action == del_act:
            self.delete_product_action()

    def export_price_list_options(self):
        """Show options for price list export"""
        msg = QDialog(self)
        msg.setWindowTitle("Експорт на Ценова Листа")
        layout = QVBoxLayout()
        msg.setLayout(layout)
        
        layout.addWidget(QLabel("Изберете формат на цените:"))
        
        cb_format = QComboBox()
        cb_format.addItems(["BGN + EUR (Двойна цена)", "Само EUR (Евро)"])
        layout.addWidget(cb_format)
        
        btn_export = QPushButton("📄 Генерирай")
        btn_export.clicked.connect(lambda: self.run_price_export(cb_format.currentIndex(), msg))
        layout.addWidget(btn_export)
        
        msg.exec()

    def run_price_export(self, format_idx, dialog):
        dialog.accept()
        from contract_generator import generate_price_list
        import os
        
        products = get_all_products()
        if not products:
            QMessageBox.warning(self, "Внимание", "Няма продукти за експорт!")
            return
            
        output_dir = os.path.join(os.path.expanduser("~"), "Documents", "ContractsApp", "PriceLists")
        
        try:
            path = generate_price_list(products, format_idx, output_dir)
            self.statusBar.showMessage("Ценовата листа е генерирана")
            self.choose_format_and_open(path)
        except Exception as e:
            QMessageBox.critical(self, "Грешка", f"Грешка при генериране на ценова листа: {str(e)}")


    def set_user(self, user):
        self.current_user = user
        if user:
            self.setWindowTitle(f"Регистър на фискални устройства - Потребител: {user.get('full_name', 'Unknown')}")
            self.statusBar.showMessage(f"Добре дошли, {user.get('full_name')}!")
    
    def create_toolbar(self):
        """Create application toolbar with themed dropdown menus"""
        self.toolbar = QToolBar("Главна лента")
        self.toolbar.setMovable(False)
        self.toolbar.setIconSize(QSize(32, 32))
        self.addToolBar(self.toolbar)
        
        # Tools Group: Устройства
        btn_devices = QToolButton()
        btn_devices.setText("Устройства")
        btn_devices.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu_devices = QMenu(self)
        
        action_add = QAction("➕ Ново устройство", self)
        action_add.triggered.connect(self.add_device)
        menu_devices.addAction(action_add)
        
        action_add_existing = QAction("➕ Към съществуващ договор", self)
        action_add_existing.triggered.connect(self.add_to_existing_contract)
        menu_devices.addAction(action_add_existing)
        
        menu_devices.addSeparator()
        
        action_edit = QAction("✏️ Редактиране", self)
        action_edit.triggered.connect(self.edit_selected_device)
        menu_devices.addAction(action_edit)
        
        action_delete = QAction("🗑️ Изтриване", self)
        action_delete.triggered.connect(self.delete_selected_device)
        menu_devices.addAction(action_delete)
        
        btn_devices.setMenu(menu_devices)
        self.toolbar.addWidget(btn_devices)
        
        self.toolbar.addSeparator()
        
        # Tools Group: Документи
        btn_docs = QToolButton()
        btn_docs.setText("Документи")
        btn_docs.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu_docs = QMenu(self)
        
        action_contract = QAction("📜 Издай договор", self)
        action_contract.triggered.connect(self.generate_selected_contract)
        menu_docs.addAction(action_contract)
        
        action_fiscal = QAction("⚙️ Заявка Фиск.", self)
        action_fiscal.triggered.connect(self.open_fiscalization_request)
        menu_docs.addAction(action_fiscal)
        
        menu_docs.addSeparator()
        
        action_cert = QAction("📝 Свидетелство", self)
        action_cert.triggered.connect(self.generate_selected_certificate)
        menu_docs.addAction(action_cert)
        
        action_dereg = QAction("📋 Дерегистрация", self)
        action_dereg.triggered.connect(self.generate_deregistration_action)
        menu_docs.addAction(action_dereg)
        
        action_repair = QAction("🔧 Протокол за ремонт", self)
        action_repair.triggered.connect(self.generate_repair_protocol_action)
        menu_docs.addAction(action_repair)
        
        action_duplicate = QAction("📄 Заявление за дубликат", self)
        action_duplicate.triggered.connect(self.generate_duplicate_action)
        menu_docs.addAction(action_duplicate)
        
        menu_docs.addSeparator()
        
        action_handover = QAction("📋 Приемо-предавателен протокол", self)
        action_handover.triggered.connect(self.open_protocol)
        menu_docs.addAction(action_handover)
        
        btn_docs.setMenu(menu_docs)
        self.toolbar.addWidget(btn_docs)
        
        self.toolbar.addSeparator()
        
        # Tools Group: Справки
        btn_reports = QToolButton()
        btn_reports.setText("Справки")
        btn_reports.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu_reports = QMenu(self)
        
        action_expiring = QAction("📄 Изтичащи договори", self)
        action_expiring.triggered.connect(self.show_expiring_contracts)
        menu_reports.addAction(action_expiring)
        
        menu_reports.addSeparator()
        
        action_nra = QAction("📊 Отчет НАП (Н-18)", self)
        action_nra.triggered.connect(self.show_nra_report)
        menu_reports.addAction(action_nra)
        
        btn_reports.setMenu(menu_reports)
        self.toolbar.addWidget(btn_reports)
        
        self.toolbar.addSeparator()
        
        # Tools Group: Импорт
        btn_import = QToolButton()
        btn_import.setText("Импорт")
        btn_import.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu_import = QMenu(self)
        
        action_import_contracts = QAction("📥 Импорт на договори (xlsx)", self)
        action_import_contracts.triggered.connect(self.import_from_excel)
        menu_import.addAction(action_import_contracts)
        
        action_import_bim = QAction("📥 Свидетелства от БИМ (xlsx)", self)
        action_import_bim.triggered.connect(self.load_certificates)
        menu_import.addAction(action_import_bim)
        
        btn_import.setMenu(menu_import)
        self.toolbar.addWidget(btn_import)
        
        self.toolbar.addSeparator()
        
        # Standalone: Настройки
        action_settings = QAction("🛠️ Настройки", self)
        action_settings.triggered.connect(self.show_settings)
        self.toolbar.addAction(action_settings)
        
        # Standalone: Одит
        action_audit = QAction("📋 Одит", self)
        action_audit.triggered.connect(self.show_audit_log)
        self.toolbar.addAction(action_audit)
        
        self.toolbar.addSeparator()
        
        # Standalone: Обнови
        action_refresh = QAction("🔄 Обнови", self)
        action_refresh.triggered.connect(self.clear_filters)
        self.toolbar.addAction(action_refresh)

        self.toolbar.addSeparator()

        action_about_menu = QAction("ℹ️ За програмата", self)
        action_about_menu.triggered.connect(self.show_about)
        
        action_check_updates = QAction("🔄 Проверка за обновления", self)
        action_check_updates.triggered.connect(lambda: self.perform_update_check(manual=True))
        
        # QToolButton for About with Menu
        about_tool_btn = QToolButton(self)
        about_tool_btn.setText("ℹ️ За програмата")
        about_tool_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        about_tool_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        
        about_menu = QMenu(self)
        about_menu.addAction(action_about_menu)
        about_menu.addAction(action_check_updates)
        about_tool_btn.setMenu(about_menu)
        
        self.toolbar.addWidget(about_tool_btn)
        
        # New: Tab switching actions for clarity
        self.toolbar.addSeparator()
        
        action_tab_devices = QAction("🏢 Устройства", self)
        action_tab_devices.triggered.connect(lambda: self.tabs.setCurrentIndex(0))
        self.toolbar.addAction(action_tab_devices)
        
        action_tab_products = QAction("📦 Продукти", self)
        action_tab_products.triggered.connect(lambda: self.tabs.setCurrentIndex(1))
        self.toolbar.addAction(action_tab_products)

    def show_about(self):
        """Show About dialog"""
        QMessageBox.about(self, "За програмата", 
            f"""<h3>Contracts App Professional</h3>
            <p><b>Версия:</b> {CURRENT_APP_VERSION}</p>
            <p>Професионална система за управление на договори и фискални устройства.</p>
            <p>Този софтуер е предназначен за автоматизиране на процесите по регистрация, 
            дерегистрация и поддръжка на ФУ.</p>
            <p>Copyright © 2026 VladPos Systems</p>
            """
        )
    
    def create_filter_panel(self):
        """Create search/filter panel"""
        layout = QVBoxLayout()
        
        # Row 1: Text filters
        row1 = QHBoxLayout()
        
        self.f_company = QLineEdit()
        self.f_company.setPlaceholderText("Фирма...")
        self.f_company.textChanged.connect(self.apply_filters)
        row1.addWidget(self.f_company)
        
        self.f_eik = QLineEdit()
        self.f_eik.setPlaceholderText("ЕИК...")
        self.f_eik.textChanged.connect(self.apply_filters)
        row1.addWidget(self.f_eik)
        
        self.f_contract = QLineEdit()
        self.f_contract.setPlaceholderText("№ Договор...")
        self.f_contract.textChanged.connect(self.apply_filters)
        row1.addWidget(self.f_contract)
        
        layout.addLayout(row1)
        
        # Row 2: More filters
        row2 = QHBoxLayout()
        
        self.f_phone = QLineEdit()
        self.f_phone.setPlaceholderText("Телефон...")
        self.f_phone.textChanged.connect(self.apply_filters)
        row2.addWidget(self.f_phone)
        
        self.f_address = QLineEdit()
        self.f_address.setPlaceholderText("Адрес...")
        self.f_address.textChanged.connect(self.apply_filters)
        row2.addWidget(self.f_address)
        
        self.f_serial = QLineEdit()
        self.f_serial.setPlaceholderText("Сериен номер...")
        self.f_serial.textChanged.connect(self.apply_filters)
        row2.addWidget(self.f_serial)
        
        self.f_euro = QCheckBox("Само с направено ЕВРО")
        self.f_euro.stateChanged.connect(self.apply_filters)
        row2.addWidget(self.f_euro)
        
        layout.addLayout(row2)
        
        # Row 3: Action buttons
        row3 = QHBoxLayout()
        
        btn_search = QPushButton("🔍 Търси")
        btn_search.clicked.connect(self.apply_filters)
        row3.addWidget(btn_search)
        
        btn_clear = QPushButton("🔄 Изчисти филтри")
        btn_clear.clicked.connect(self.clear_filters)
        row3.addWidget(btn_clear)
        
        row3.addStretch()
        
        layout.addLayout(row3)
        
        return layout
    
    def refresh_table(self):
        """Reload all devices into table. Preserves filters if active."""
        if hasattr(self, 'f_company') and self.has_active_filters():
            self.apply_filters()
            return
            
        self.statusBar.showMessage("Зареждане на данни...")
        data = get_all_devices()
        self.load_table(data)
        self.statusBar.showMessage(f"Заредени {len(data)} записа")

    def has_active_filters(self):
        """Check if any search filters are currently active on the devices tab"""
        try:
            return any([
                self.f_company.text().strip(),
                self.f_eik.text().strip(),
                self.f_contract.text().strip(),
                self.f_phone.text().strip(),
                self.f_address.text().strip(),
                self.f_serial.text().strip(),
                self.f_euro.isChecked()
            ])
        except AttributeError:
            return False
    
    def load_table(self, data, expiring_mode=False):
        """Load data into table"""
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        
        # Adjust columns for expiring mode
        if expiring_mode:
            self.table.setColumnCount(7)
            self.table.setHorizontalHeaderLabels([
                "№ Договор", "Фирма", "Модел", "Сериен №", "Изтичане", "ЕИК", "Телефон"
            ])
        else:
            self.table.setColumnCount(25)
            self.table.setHorizontalHeaderLabels([
                "ID", "№ Договор", "Статус", "Фирма", "ЕИК", "ДДС", "МОЛ", "Град", "ПК", "Адрес", 
                "Тел. 1", "Тел. 2", "Начална дата", "Крайна дата", "Име на обект", "Адрес на обект", "Тел. Обект",
                "Модел", "Сериен №", "FDRID", "Номер на ФП", "№ Свидетелство", "Валидност БИМ", "Евро", "НАП Отчет"
            ])
            self.table.setColumnHidden(0, True)
        
        for row_data in data:
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            for col, value in enumerate(row_data):
                display_value = ""
                
                # Helper to clean ".0" from likely integer fields imported as floats
                def clean_float_str(val):
                    s = str(val) if val is not None else ""
                    if s.endswith(".0"):
                        return s[:-2]
                    return s

                # Euro column (23) and NRA (24)
                if not expiring_mode and (col == 23 or col == 24):
                    display_value = "✓" if value else ""
                
                # Date columns: Contract Start (12), Contract Expiry (13), Cert Expiry (22)
                elif (not expiring_mode and col in [12, 13, 22]) or (expiring_mode and col == 4):
                    display_value = format_date_bg(value)
                
                # Columns that need ".0" cleanup: 
                # PK (8), FDRID (19), FM (20), Cert Num (21)
                elif not expiring_mode and col in [8, 19, 20, 21]:
                    display_value = clean_float_str(value)
                
                else:
                    display_value = str(value) if value is not None else ""
                
                item = QTableWidgetItem(display_value)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable) # Make items non-editable by default
                
                # Make ID column data accessible but hidden
                if not expiring_mode and col == 0:
                    item.setData(Qt.ItemDataRole.UserRole, value)
                
                self.table.setItem(row, col, item)
        
        self.table.setSortingEnabled(True)
    
    def apply_filters(self):
        """Apply search filters"""
        self.statusBar.showMessage("Търсене...")
        
        filters = {
            'company': self.f_company.text().strip(),
            'eik': self.f_eik.text().strip(),
            'contract': self.f_contract.text().strip(),
            'phone': self.f_phone.text().strip(),
            'address': self.f_address.text().strip(),
            'serial': self.f_serial.text().strip(),
            'euro': self.f_euro.isChecked()
        }
        
        data = search_devices(filters)
        self.load_table(data)
        self.statusBar.showMessage(f"Намерени {len(data)} записа")
    
    def clear_filters(self):
        """Clear all filters and reload current tab"""
        idx = self.tabs.currentIndex()
        if idx == 0:
            self.f_company.clear()
            self.f_eik.clear()
            self.f_contract.clear()
            self.f_phone.clear()
            self.f_address.clear()
            self.f_serial.clear()
            self.f_euro.setChecked(False)
            self.refresh_table()
        elif idx == 1:
            self.product_search.clear()
            self.refresh_products()
        elif idx == 2:
            self.invoice_search.clear()
            self.refresh_invoices()
        elif idx == 3:
            self.refresh_stats()
        
        self.statusBar.showMessage("Данните бяха обновени успешно", 3000)
    
    def add_device(self):
        """Open add device dialog"""
        dialog = AddDeviceDialog(self)
        if dialog.exec():
            self.refresh_table()
            if self.current_user:
                # We need to capture the new device ID and contract number for better logging. 
                # Ideally AddDeviceDialog would return them, but for now we log generic.
                # Or we can improve AddDeviceDialog later. 
                log_action(self.current_user['id'], self.current_user['username'], "ADD_DEVICE", "Added new device")
    
    def add_to_existing_contract(self):
        """Open add to existing contract dialog"""
        dialog = AddToExistingContractDialog(self)
        if dialog.exec():
            self.refresh_table()
    
    def edit_selected_device(self):
        """Edit the selected device"""
        row = self.table.currentRow()
        
        if row < 0:
            QMessageBox.warning(self, "Внимание", "Моля, изберете устройство за редактиране!")
            return
        
        # Get device ID from first column (hidden)
        device_id = int(self.table.item(row, 0).text())
        
        dialog = EditDeviceDialog(device_id, self)
        if dialog.exec():
            # Retrieve contract number for logging BEFORE refreshing table
            contract_num = self.table.item(row, 3).text()
            self.refresh_table()
            if self.current_user:
                log_action(self.current_user['id'], self.current_user['username'], "EDIT_DEVICE", f"Edited device ID {device_id}", contract_number=contract_num, device_id=device_id)
            
            # Proactive Sync
            if self.sync_manager and self.sync_manager.mode == "client":
                self.sync_manager.sync_now()
    
    def delete_selected_device(self):
        """Delete the selected device"""
        row = self.table.currentRow()
        
        if row < 0:
            QMessageBox.warning(self, "Внимание", "Моля, изберете устройство за изтриване!")
            return
        
        # Confirm deletion
        reply = QMessageBox.question(
            self,
            "Потвърждение",
            "Сигурни ли сте, че искате да изтриете избраното устройство?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            device_id = int(self.table.item(row, 0).text())
            
            if delete_device(device_id):
                # Retrieve info for logging BEFORE refresh
                contract_num = self.table.item(row, 3).text()
                
                QMessageBox.information(self, "Успех", "Устройството е изтрито!")
                self.refresh_table()
                
                if self.current_user:
                    log_action(self.current_user['id'], self.current_user['username'], "DELETE_DEVICE", f"Deleted device ID {device_id}", contract_number=contract_num, device_id=device_id)
                
                # Proactive Sync
                if self.sync_manager and self.sync_manager.mode == "client":
                    self.sync_manager.sync_now()
            else:
                QMessageBox.critical(self, "Грешка", "Грешка при изтриване!")
    
    def show_context_menu(self, position):
        """Show right-click context menu with copy options"""
        index = self.table.indexAt(position)
        if not index.isValid():
            return
            
        menu = QMenu()
        
        # Original actions
        edit_action = menu.addAction("✏️ Редактиране")
        contract_action = menu.addAction("📜 Издай договор")
        menu.addSeparator()
        cert_action = menu.addAction("📝 Издай свидетелство")
        dereg_action = menu.addAction("📋 Протокол дерегистрация")
        menu.addSeparator()
        menu.addSeparator()
        nap_action = menu.addAction("📡 Направи файл за НАП")
        menu.addSeparator()
        menu.addSeparator()
        repair_action = menu.addAction("🔧 Протокол за ремонт")
        duplicate_action = menu.addAction("📄 Заявление за дубликат")
        menu.addSeparator()
        delete_action = menu.addAction("🗑️ Изтриване")
        
        menu.addSeparator()
        
        # History (Admin only)
        history_action = None
        if self.current_user and self.current_user.get('role') == 'admin':
            history_action = menu.addAction("📁 Електронно досие (История)")
            menu.addSeparator()
            
        # New copy actions
        copy_cell_action = menu.addAction("📋 Копирай клетка")
        copy_row_action = menu.addAction("📄 Копирай ред")
        
        action = menu.exec(self.table.viewport().mapToGlobal(position))
        
        if action == edit_action:
            self.edit_selected_device()
        elif action == contract_action:
            self.generate_selected_contract()
        elif action == cert_action:
            self.generate_selected_certificate()
        elif action == dereg_action:
            self.generate_deregistration_action()
        elif action == nap_action:
            self.generate_nap_file()
        elif action == repair_action:
            self.generate_repair_protocol_action()
        elif action == duplicate_action:
            self.generate_duplicate_action()
        elif action == delete_action:
            self.delete_selected_device()
        elif history_action and action == history_action:
            self.show_device_history(index)
        elif action == copy_cell_action:
            self.copy_cell_to_clipboard(index.row(), index.column())
        elif action == copy_row_action:
            self.copy_row_to_clipboard(index.row())

    def show_device_history(self, index):
        """Show history for the device/contract at the given index"""
        row = index.row()
        device_id = int(self.table.item(row, 0).text())
        contract_num = self.table.item(row, 3).text()
        
        from dialogs import DeviceHistoryDialog
        dialog = DeviceHistoryDialog(device_id=device_id, contract_number=contract_num, parent=self)
        dialog.exec()

    def choose_format_and_open(self, docx_path):
        """Ask user if they want to open DOCX or PDF and handle conversion"""
        if not docx_path or not os.path.exists(docx_path):
            return
            
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Question)
        msg.setWindowTitle("Избор на формат")
        msg.setText("В какъв формат искате да отворите документа?")
        docx_btn = msg.addButton("Word (DOCX)", QMessageBox.ButtonRole.ActionRole)
        pdf_btn = msg.addButton("PDF", QMessageBox.ButtonRole.ActionRole)
        cancel_btn = msg.addButton("Отказ", QMessageBox.ButtonRole.RejectRole)
        
        msg.exec()
        
        if msg.clickedButton() == docx_btn:
            os.startfile(docx_path)
        elif msg.clickedButton() == pdf_btn:
            from contract_generator import docx_to_pdf
            self.statusBar.showMessage("Конвертиране в PDF...")
            pdf_path = docx_to_pdf(docx_path)
            if pdf_path:
                os.startfile(pdf_path)
                self.statusBar.showMessage(f"PDF е готов: {pdf_path}", 3000)
            else:
                QMessageBox.critical(self, "Грешка", "Неуспешно конвертиране в PDF. Опитайте с Word.")
                os.startfile(docx_path)

    def generate_selected_certificate(self):
        """Generate certificate for selected device"""
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Внимание", "Моля, изберете устройство!")
            return
            
        item = self.table.item(row, 0)
        device_id = item.data(Qt.ItemDataRole.UserRole)
        if not device_id:
             # Fallback if ItemDataRole wasn't used
             device_id = int(item.text())
        
        from database import get_device_full
        from contract_generator import generate_registration_certificate
        
        full_data = get_device_full(device_id)
        if not full_data: return
        
        # Map DB fields to what generator expects
        client_data = full_data 
        device = full_data
        device['bim_number'] = full_data.get('certificate_number', '')
        
        try:
            template = "RegCert_DY432051.docx"
            output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Generated")
            if not os.path.exists(output_dir): os.makedirs(output_dir)
            
            out_path = generate_registration_certificate(client_data, device, template, output_dir)
            self.statusBar.showMessage("Свидетелството е генерирано")
            if self.current_user:
                log_action(self.current_user['id'], self.current_user['username'], "GEN_CERT", f"Generated certificate for {client_data.get('firm_name')}", device_id=device_id)
            self.choose_format_and_open(out_path)
        except Exception as e:
            QMessageBox.critical(self, "Грешка", f"Грешка при генериране:\n{e}")

    def generate_nap_file(self):
        """Generate NAP XML for selected device and service technician from settings"""
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Грешка", "Моля, изберете ред от таблицата.")
            return

        # Load Settings
        settings_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "settings.json")
        if not os.path.exists(settings_path):
            QMessageBox.warning(self, "Внимание", "Моля, първо попълнете данните за сервизния техник в Настройки!")
            return
            
        import json
        try:
            with open(settings_path, 'r', encoding='utf-8') as f:
                service_data = json.load(f)
        except:
            QMessageBox.critical(self, "Грешка", "Неуспешно зареждане на настройките.")
            return

        if not service_data.get('tech_egn'):
            QMessageBox.warning(self, "Внимание", "Липсват данни за техник в настройките (ЕГН).")
            return

        # Data from Table (ID is in column 0, hidden)
        device_id = int(self.table.item(row, 0).text())
        
        from database import get_device_full
        full_data = get_device_full(device_id)
        
        from contract_generator import clean_numeric
        client_eik = clean_numeric(full_data.get('eik', ''))
        fdrid = clean_numeric(full_data.get('fdrid', ''))

        from path_utils import get_app_root, get_data_root
        output_dir = os.path.join(get_data_root(), "Generated")
        os.makedirs(output_dir, exist_ok=True)

        try:
            xml_path = generate_nap_xml(service_data, client_eik, fdrid, output_dir)
            
            QMessageBox.information(self, "Успех", f"XML файлът за НАП е генериран:\n{os.path.basename(xml_path)}")
            
            if self.current_user:
                log_action(self.current_user['id'], self.current_user['username'], "GEN_NAP_XML", f"Generated NAP XML for device ID {device_id}", device_id=device_id)

            # Open the folder or file
            os.startfile(output_dir)
        except Exception as e:
            QMessageBox.critical(self, "Грешка", f"Грешка при генериране на XML:\n{e}")

    def open_protocol(self):
        """Open Handover Protocol dialog"""
        dialog = ProtocolDialog(self)
        dialog.exec()

    def generate_deregistration_action(self):
        """Open dialog and generate deregistration protocol"""
        selected_rows = self.table.selectionModel().selectedRows()
        device_id = None
        device_data = None
        
        if selected_rows:
            row = selected_rows[0].row()
            item = self.table.item(row, 0)
            device_id = item.data(Qt.ItemDataRole.UserRole)
            from database import get_device_full
            device_data = get_device_full(device_id)
            if device_data:
                device_data['bim_number'] = device_data.get('certificate_number', '')

        from dialogs import DeregistrationDialog
        dialog = DeregistrationDialog(self, device_data)
        if dialog.exec():
            data = dialog.get_data()
            from contract_generator import generate_deregistration_protocol
            try:
                template = "DeregProtocol_DT123456.docx"
                from path_utils import get_app_root, get_data_root
                output_dir = os.path.join(get_data_root(), "Generated")
                if not os.path.exists(output_dir): os.makedirs(output_dir)
                
                out_path = generate_deregistration_protocol(data, template, output_dir)
                self.statusBar.showMessage("Протоколът за дерегистрация е генериран")
                if self.current_user:
                    log_action(self.current_user['id'], self.current_user['username'], "GEN_DEREG", "Generated deregistration protocol", device_id=device_id)
                self.choose_format_and_open(out_path)
            except Exception as e:
                QMessageBox.critical(self, "Грешка", f"Грешка при генериране:\n{e}")

    def open_fiscalization_request(self):
        """Open the 'Заявка за фискализация.docx' template"""
        from path_utils import get_resource_path
        f_path = get_resource_path("Заявка за фискализация.docx")
        if os.path.exists(f_path):
            os.startfile(f_path)
        else:
            QMessageBox.warning(self, "Грешка", f"Файлът не е намерен:\n{f_path}")

    def show_nra_report(self):
        """Open the NRA Report preview dialog"""
        from dialogs import NraReportDialog
        dialog = NraReportDialog(self)
        dialog.exec()

    def run_nra_report_generation(self):
        """Logic to generate the fiskal.ser file using all flagged devices"""
        # Load Settings (Service Data)
        from path_utils import get_app_root, get_data_root
        settings_path = os.path.join(get_data_root(), "data", "settings.json")
        if not os.path.exists(settings_path):
            QMessageBox.warning(self, "Внимание", "Моля, първо попълнете данните за сервизния техник в Настройки!")
            return
            
        import json
        try:
            with open(settings_path, 'r', encoding='utf-8') as f:
                service_data = json.load(f)
        except:
            QMessageBox.critical(self, "Грешка", "Неуспешно зареждане на настройките.")
            return

        from database import get_devices_for_nra_report
        devices = get_devices_for_nra_report()
        
        if not devices:
            QMessageBox.information(self, "Информация", "Няма устройства, маркирани за включване в отчета.")
            return

        output_dir = os.path.join(get_data_root(), "Generated")
        os.makedirs(output_dir, exist_ok=True)

        from contract_generator import generate_fiskal_ser
        try:
            out_path = generate_fiskal_ser(service_data, devices, output_dir)
            QMessageBox.information(self, "Успех", f"Отчетът fiskal.ser е генериран успешно в:\n{out_path}")
            if self.current_user:
                log_action(self.current_user['id'], self.current_user['username'], "GEN_FISKAL_SER", f"Generated NRA report for {len(devices)} devices")
            os.startfile(output_dir)
        except Exception as e:
            QMessageBox.critical(self, "Грешка", f"Грешка при генериране:\n{e}")

    def copy_cell_to_clipboard(self, row, col):
        """Copy single cell text to clipboard"""
        item = self.table.item(row, col)
        if item:
            QApplication.clipboard().setText(item.text())
            self.statusBar.showMessage("Клетката е копирана", 3000)

    def copy_row_to_clipboard(self, row):
        """Copy entire row text to clipboard (tab-separated)"""
        row_data = []
        for col in range(self.table.columnCount()):
            if self.table.isColumnHidden(col):
                continue
            item = self.table.item(row, col)
            row_data.append(item.text() if item else "")
        
        row_text = "\t".join(row_data)
        QApplication.clipboard().setText(row_text)
        self.statusBar.showMessage("Редът е копиран", 3000)
    
    def show_expiring_contracts(self):
        """Show expiring contracts dialog"""
        dialog = ExpiringContractsDialog(self)
        dialog.exec()
    
    def import_from_excel(self):
        """Import data from Excel file"""
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Избери Excel файл за импорт",
            "",
            "Excel Files (*.xlsx *.xls)"
        )
        
        if filename:
            reply = QMessageBox.question(
                self, "Потвърждение",
                "Сигурни ли сте, че искате да импортирате данни? Съществуващите записи могат да бъдат дублирани.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.statusBar.showMessage("Импортиране...")
                result_msg = import_contracts_simple(filename)
                self.refresh_table()
                if self.current_user:
                    log_action(self.current_user['id'], self.current_user['username'], "IMPORT_DATA", f"Imported data from {os.path.basename(filename)}")
                QMessageBox.information(self, "Резултате от импорта", result_msg)

    def show_settings(self):
        """Show settings dialog"""
        dialog = SettingsDialog(self)
        dialog.exec()
    
    def load_certificates(self):
        """Load certificates from BIM Excel file"""
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Избери BIM Excel файл със сертификати",
            "",
            "Excel Files (*.xlsx *.xls)"
        )
        
        if filename:
            self.statusBar.showMessage("Зареждане на сертификати...")
            result = load_certificates_safe(filename)
            QMessageBox.information(self, "Сертификати", result)
            self.statusBar.showMessage("Готов")

    def show_audit_log(self):
        """Show audit log viewer dialog (admin only)"""
        # Check if current user is admin
        if not self.current_user or self.current_user.get('role') != 'admin':
            QMessageBox.warning(self, "Грешка", "Само администраторът има достъп до одита!")
            return
            
        from dialogs import AuditLogViewerDialog
        dialog = AuditLogViewerDialog(self)
        dialog.exec()


    def generate_repair_protocol_action(self):
        """Open repair protocol dialog for selected device"""
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Внимание", "Моля, изберете устройство!")
            return
            
        device_id = int(self.table.item(row, 0).text())
        
        dialog = RepairProtocolDialog(device_id, self)
        dialog.exec()

    def generate_selected_contract(self):
        """Generate service contract from template for selected device's contract"""
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Грешка", "Моля, изберете ред от таблицата.")
            return

        # Get contract number from column 1
        contract_num = self.table.item(row, 1).text()
        
        if not contract_num:
            QMessageBox.warning(self, "Грешка", "Липсва номер на договор за този ред.")
            return

        try:
            # Gather data
            client_data = get_client_by_contract(contract_num)
            if not client_data:
                QMessageBox.critical(self, "Грешка", f"Не са намерени данни за договор {contract_num}")
                return
            
            devices = get_devices_by_contract(contract_num)
            
            # Directory to save
            save_dir = QFileDialog.getExistingDirectory(self, "Изберете папка за запазване на договора")
            if not save_dir:
                return

            template_path = "1 Профинанс Д и Д ЕООД.docx"
            
            # Use generator
            from contract_generator import generate_service_contract
            output_file = generate_service_contract(client_data, devices, template_path, save_dir)
            
            # Open the file
            if os.path.exists(output_file):
                self.statusBar.showMessage(f"Договорът е генериран: {os.path.basename(output_file)}", 5000)
                self.choose_format_and_open(output_file)
                if self.current_user:
                    log_action(self.current_user['id'], self.current_user['username'], 
                               "GEN_CONTRACT", f"Generated contract {contract_num}", 
                               contract_number=contract_num)
            else:
                QMessageBox.information(self, "Успех", f"Договорът беше генериран успешно:\n{output_file}")
                if self.current_user:
                    log_action(self.current_user['id'], self.current_user['username'], 
                               "GEN_CONTRACT", f"Generated contract {contract_num}", 
                               contract_number=contract_num)

        except Exception as e:
            QMessageBox.critical(self, "Грешка", f"Грешка при генериране на договор: {str(e)}")


    def generate_duplicate_action(self):
        """Generate Duplicate Passport Application"""
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Внимание", "Моля, изберете устройство!")
            return
            
        item = self.table.item(row, 0)
        device_id = item.data(Qt.ItemDataRole.UserRole)
        if not device_id:
             # Fallback
             device_id = int(item.text())
        
        from database import get_device_full
        
        full_data = get_device_full(device_id)
        if not full_data:
            QMessageBox.warning(self, "Грешка", "Не може да се зареди информацията за устройството.")
            return

        # Try to infer manufacturer from model name
        model_str = full_data.get('model', '').upper()
        default_manu = None
        if "DAISY" in model_str: default_manu = "Daisy"
        elif "TREMOL" in model_str: default_manu = "Tremol"
        elif "DATECS" in model_str: default_manu = "Datecs"

        dlg = DuplicatePassportDialog(self, default_manufacturer=default_manu)
        if dlg.exec():
            manufacturer = dlg.manufacturer
            
            # Map manufacturer to template file
            templates = {
                "Daisy": "Dublikat_passport_Daisy.docx",
                "Tremol": "Dublikat_passport_Tremol.docx",
                "Datecs": "Dublikat_passport_Datecs.docx"
            }
            
            t_name = templates.get(manufacturer)
            
            try:
                from contract_generator import generate_duplicate_passport
                
                # Output folder
                output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Generated", "Duplicates")
                if not os.path.exists(output_dir): os.makedirs(output_dir)
                
                # Use full_data as both client and device data
                out_path = generate_duplicate_passport(full_data, full_data, manufacturer, t_name, output_dir)
                
                self.statusBar.showMessage("Заявлението за дубликат е генерирано")
                if self.current_user:
                    log_action(self.current_user['id'], self.current_user['username'], 
                               "GEN_DUPLICATE", f"Generated duplicate passport for {full_data.get('company_name')}", 
                               device_id=device_id)
                self.choose_format_and_open(out_path)
                
            except Exception as e:
                QMessageBox.critical(self, "Грешка", f"Грешка при генериране:\n{str(e)}")

    def init_sync_system(self):
        """Initialize Sync System based on settings"""
        if not SyncManager:
            return

        self.sync_manager = SyncManager()
        
        # Connect signals
        self.sync_manager.status_changed.connect(self.update_sync_status)
        self.sync_manager.sync_finished.connect(self.on_sync_finished)
        
        # Add Sync button to toolbar
        self.add_sync_action()
        
        mode = self.sync_manager.mode
        
        if mode == "server":
            self.start_server_mode()
        else:
            self.start_client_mode()

    def add_sync_action(self):
        """Add manual sync/refresh button to toolbar"""
        if hasattr(self, 'toolbar'):
            # Remove existing sync action if present to prevent duplicates
            if hasattr(self, 'sync_action') and self.sync_action in self.toolbar.actions():
                self.toolbar.removeAction(self.sync_action)
                
            mode = self.sync_manager.mode if self.sync_manager else "client"
            
            if mode == "server":
                self.sync_action = QAction("🔄 Обнови (Сървър)", self)
                self.sync_action.setStatusTip("Освежаване на данните от базата")
                self.sync_action.triggered.connect(self.refresh_table)
            else:
                self.sync_action = QAction("🔄 Синхронизирай", self)
                self.sync_action.setStatusTip("Ръчно синхронизиране на данни")
                self.sync_action.triggered.connect(self.sync_manager.sync_now)
            
            self.toolbar.addAction(self.sync_action)

    def start_server_mode(self):
        """Start embedded API server"""
        if ServerThread and not self.server_thread:
            self.server_thread = ServerThread()
            # Connect signal for automatic UI refresh when client pushes data
            if hasattr(self.server_thread, 'signals'):
                self.server_thread.signals.data_pushed.connect(self.refresh_table)
                self.server_thread.signals.data_pushed.connect(self.refresh_products)
            
            self.server_thread.start()
            
            # Detect actual LAN IP to show user
            import socket
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
                s.close()
            except:
                ip = "127.0.0.1"
                
            self.statusBar.showMessage(f"РЕЖИМ СЪРВЪР: http://{ip}:8000")
            self.update_sync_status("server")

    def start_client_mode(self):
        """Start background sync client"""
        if self.sync_manager:
            self.sync_manager.start_background_sync()
            self.statusBar.showMessage("РЕЖИМ КЛИЕНТ: Свързване...")

    def update_sync_status(self, status):
        """Update status bar with sync state"""
        if status == "online":
            self.statusBar.showMessage("🟢 ВРЪЗКА СЪС СЪРВЪРА: ОК", 5000)
        elif status == "offline":
            self.statusBar.showMessage("🔴 НЯМА ВРЪЗКА СЪС СЪРВЪРА (Офлайн режим)", 5000)
        elif status == "syncing":
            self.statusBar.showMessage("🔄 Синхронизиране...", 5000)
        elif status == "server":
             self.statusBar.showMessage("🟢 СЪРВЪРЪТ РАБОТИ", 5000)

    def on_sync_finished(self, success, message):
        if not success:
            self.statusBar.showMessage(f"⚠️ Грешка при синхронизация: {message}", 10000)
        else:
            self.statusBar.showMessage(message, 5000)
            
            # Phase 11: Show pop-up if new items were received
            if "Получени са" in message:
                QMessageBox.information(self, "Нови данни", message)
            self.refresh_table()
            self.refresh_products()

    def open_settings(self):
        """Open settings dialog"""
        dialog = SettingsDialog(self)
        old_mode = self.sync_manager.mode if self.sync_manager else None
        
        if dialog.exec():
            # Refresh sync manager if it exists
            if hasattr(self, 'sync_manager') and self.sync_manager:
                print("DEBUG: Reloading SyncManager settings...")
                self.sync_manager.reload_settings()
                
                # Check if mode changed (Server <-> Client)
                new_mode = self.sync_manager.mode
                if old_mode != new_mode:
                    print(f"DEBUG: Sync mode changed from {old_mode} to {new_mode}. Re-initializing UI.")
                    if new_mode == "server":
                        self.start_server_mode()
                    else:
                        self.start_client_mode()
                    # Rebuild tray icon to update menu actions
                    self.init_tray_icon()
                
                self.statusBar.showMessage(f"Настройките са за заредени. Адрес: {self.sync_manager.server_url}", 5000)
                # Update sync button label/action on toolbar
                self.add_sync_action()
            else:
                # If sync manager was not initialized (e.g. error at startup), try now
                self.init_sync_system()

    def perform_sync(self):
        """Manually trigger a sync iteration"""
        if self.sync_manager:
            self.statusBar.showMessage("🔄 Синхронизиране...", 5000)
            # We use the background runner if available, or call directly
            self.sync_manager.perform_sync_iteration()
            # If not using signals, we can manually call on_sync_finished
            # But SyncManager usually emits 'sync_finished'

    def focus_search(self):
        """Focus the search box in the current tab"""
        idx = self.tabs.currentIndex()
        if idx == 0: # Devices
            self.f_company.setFocus()
            self.f_company.selectAll()
        elif idx == 1: # Products
            self.product_search.setFocus()
            self.product_search.selectAll()
        elif idx == 2: # Invoices
            self.invoice_search.setFocus()
            self.invoice_search.selectAll()
            
    def init_tray_icon(self):
        """Initialize the system tray icon and menu"""
        if hasattr(self, 'tray_icon') and self.tray_icon:
            self.tray_icon.hide()
            
        self.tray_icon = QSystemTrayIcon(self)
        
        # Use existing logo or standard icon
        icon_path = get_resource_path('vladpos_logo.png')
        if not os.path.exists(icon_path):
             icon_path = get_resource_path('logo-d-d.jpg')
             
        if os.path.exists(icon_path):
            self.tray_icon.setIcon(QIcon(icon_path))
        else:
            self.tray_icon.setIcon(self.style().standardIcon(Qt.StandardPixmap.SP_ComputerIcon))
            
        # Create context menu
        tray_menu = QMenu()
        
        show_action = QAction("📂 Отвори програмата", self)
        show_action.triggered.connect(self.show_normal)
        
        sync_action = QAction("🔄 Синхронизиране със сървъра", self)
        sync_action.triggered.connect(self.perform_sync)
        
        settings_action = QAction("⚙️ Настройки", self)
        settings_action.triggered.connect(self.open_settings)
        
        exit_action = QAction("❌ Затваряне", self)
        exit_action.triggered.connect(self.quit_application)
        
        tray_menu.addAction(show_action)
        tray_menu.addAction(sync_action)
        tray_menu.addAction(settings_action)
        tray_menu.addSeparator()
        tray_menu.addAction(exit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_icon_activated)
        self.tray_icon.show()
        # Store menu reference for possible updates
        self.tray_menu = tray_menu

    def on_hotkey_triggered(self):
        """Toggle window visibility on Alt+D: hide if active, show if background/hidden"""
        if self.isVisible() and self.isActiveWindow() and not self.isMinimized():
            self.hide()
            self.statusBar.showMessage("Програмата продължава да работи на заден план.", 3000)
        else:
            self.show_normal()

    def on_tray_icon_activated(self, reason):
        try:
            # Defensive check for ActivationReason conversion bug in some PyQt versions
            # Trigger is usually 3 (Left-Click), ContextMenu is 1 (Right-Click)
            r_val = int(reason)
            if r_val == QSystemTrayIcon.ActivationReason.Trigger.value:
                if self.isVisible():
                    self.hide()
                else:
                    self.show_normal()
        except (TypeError, ValueError, Exception):
            # Fallback: if conversion fails, we still want to toggle visibility 
            # as it's the expected primary action for a tray icon click
            if self.isVisible():
                self.hide()
            else:
                self.show_normal()

    def show_normal(self):
        """Restore, show and activate the window, bringing it to the absolute front"""
        if self.isMinimized():
            self.showNormal()
        else:
            self.show()
            
        # Ensure it's active and has focus
        self.activateWindow()
        self.raise_() # Bring to front of other windows
        
        # Windows-specific: Force focus if needed
        # (Though activateWindow usually suffices for most Qt apps)
        from PyQt6.QtGui import QWindow
        window = self.windowHandle()
        if window:
            window.requestActivate()

    def quit_application(self):
        """Properly quit the application by stopping all threads"""
        try:
            if hasattr(self, 'server_thread') and self.server_thread:
                self.server_thread.stop()
            if hasattr(self, 'sync_manager') and self.sync_manager:
                self.sync_manager.stop()
        except:
            pass
        QApplication.instance().quit()

    def closeEvent(self, event):
        """Handle window close event - hide to tray instead of exit if tray exists"""
        if hasattr(self, 'tray_icon') and self.tray_icon.isVisible():
            self.hide()
            event.ignore()
            self.statusBar.showMessage("Програмата продължава да работи в системната лента.", 5000)
        else:
            # Fallback for when tray is not initialized/visible
            reply = QMessageBox.question(self, 'Изход', 
                "Сигурни ли сте, че искате да излезете?", QMessageBox.StandardButton.Yes | 
                QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
                
            if reply == QMessageBox.StandardButton.Yes:
                # Stop threads
                try:
                    if hasattr(self, 'server_thread') and self.server_thread:
                        self.server_thread.stop()
                    if hasattr(self, 'sync_manager') and self.sync_manager:
                        self.sync_manager.stop()
                except:
                    pass
                event.accept()
            else:
                event.ignore()

def main():
    # Create application
    app = QApplication(sys.argv)
    
    # Set application-wide icon
    icon_path = get_resource_path('vladpos_logo.png')
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    
    # Show Splash Screen
    splash = SplashScreen()
    splash.show()
    
    # Disable automatic exit when windows close (crucial for login/splash flow)
    # This must be set before any windows are shown and closed (like splash or error boxes)
    app.setQuitOnLastWindowClosed(False)
    
    # Simulate loading process while initializing
    # In a real app, this would happen during data loading
    for i in range(1, 101):
        splash.setProgress(i)
        splash.showMessage(f"Зареждане на компоненти... {i}%", 
                          Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter, 
                          Qt.GlobalColor.white)
        import time
        time.sleep(0.02) # Simulating weight
    
    # Ensure data directory exists
    os.makedirs("data", exist_ok=True)
    
    # Initialize database
    init_db()
    
def handle_exception(exc_type, exc_value, exc_traceback):
    """Global exception handler to prevent app from closing silently"""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    import traceback
    error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    
    # Log to file
    try:
        with open("crash_log.txt", "a", encoding="utf-8") as f:
            f.write(f"\n{'='*50}\n")
            f.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(error_msg)
    except:
        pass

    # Show dialog
    try:
        from PyQt6.QtWidgets import QMessageBox, QApplication
        if QApplication.instance():
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.setWindowTitle("Критична грешка")
            msg.setText("Възникна неочаквана грешка в приложението.")
            msg.setInformativeText("Програмата записа детайли в crash_log.txt. Моля, свържете се с поддръжката.")
            msg.setDetailedText(error_msg)
            msg.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg.exec()
    except:
        pass

sys.excepthook = handle_exception

def main():
    # Set exception hook as early as possible
    sys.excepthook = handle_exception
    
    app = QApplication(sys.argv)
    
    # Set global application icon
    icon_path = get_resource_path('vladpos_logo.ico')
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    
    # Splash screen
    splash = SplashScreen()
    splash.show()
    app.processEvents()
    
    # Progress simulation
    splash.setProgress(15)
    
    # Initialize DB (migrations etc)
    splash.setProgress(30)
    init_db()
    
    splash.setProgress(60)
    
    # Run Backup BEFORE showing UI
    try:
        backup_database()
    except:
        pass
    
    splash.setProgress(100)
    
    # Set application style
    app.setStyle('Fusion')
    
    # Create login dialog
    login = LoginDialog()
    
    # Close splash when login is shown
    splash.finish(login) 
    
    result = login.exec()
    
    if result == QDialog.DialogCode.Accepted:
        # Re-enable automatic exit for the main application window
        app.setQuitOnLastWindowClosed(True)
        
        # Create and show main window
        window = MainWindow()
        window.set_user(login.user)
        window.show()
        
        sys.exit(app.exec())
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
