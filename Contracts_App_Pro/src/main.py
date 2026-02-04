import sys
import os
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTableWidget, QTableWidgetItem,
    QPushButton, QVBoxLayout, QWidget, QHBoxLayout, QLineEdit,
    QCheckBox, QMessageBox, QFileDialog, QStatusBar, QMenu, QToolBar,
    QSplashScreen, QProgressBar, QLabel, QToolButton, QDialog, QComboBox,
    QTabWidget, QFrame, QGroupBox, QScrollArea, QGridLayout, QAbstractItemView
)
from PyQt6.QtCore import Qt, QTimer, QSize, QUrl
from PyQt6.QtGui import QAction, QIcon, QPixmap, QDesktopServices

from database import (
    init_db, get_all_devices, search_devices, delete_device,
    get_client_by_contract, get_devices_by_contract,
    get_all_products, search_products, delete_product, get_db_stats
)
from contract_generator import generate_service_contract, generate_nap_xml
from dialogs import (
    AddDeviceDialog, EditDeviceDialog, AddToExistingContractDialog,
    ExpiringContractsDialog, SettingsDialog, LoginDialog, RepairProtocolDialog,
    ProductDialog, DuplicatePassportDialog
)
from importer import import_contracts_simple
from bim_loader import load_certificates_safe
from date_utils import format_date_bg
from path_utils import get_resource_path
from database import log_action

class SplashScreen(QSplashScreen):
    def __init__(self):
        # Create a background pixmap (canvas)
        canvas_width = 700
        canvas_height = 500
        pixmap = QPixmap(canvas_width, canvas_height)
        pixmap.fill(Qt.GlobalColor.white)
        
        super().__init__(pixmap)
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint)
        
        # Paths to images safely via utility
        logo_path = get_resource_path('logo-d-d.jpg')
        
        # Title Label
        self.titleLabel = QLabel("Регистър на\nфискални устройства", self)
        self.titleLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.titleLabel.setStyleSheet("font-size: 32px; font-weight: bold; color: #2c3e50; margin-top: 20px;")
        self.titleLabel.setGeometry(0, 30, canvas_width, 100)
        
        # Logo Label
        self.logoLabel = QLabel(self)
        if os.path.exists(logo_path):
            original_pixmap = QPixmap(logo_path)
            scaled_logo = original_pixmap.scaled(350, 250, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.logoLabel.setPixmap(scaled_logo)
            self.logoLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
            # Center the logo in the middle of the remaining space
            logo_x = (canvas_width - scaled_logo.width()) // 2
            logo_y = 150 # Starting after title

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
        
        # Paths to images safely via utility
        logo_path = get_resource_path('logo-d-d.jpg')
        
        # Title Label
        self.titleLabel = QLabel("Регистър на\nфискални устройства", self)
        self.titleLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.titleLabel.setStyleSheet("font-size: 32px; font-weight: bold; color: #2c3e50; margin-top: 20px;")
        self.titleLabel.setGeometry(0, 30, canvas_width, 100)
        
        # Logo Label
        self.logoLabel = QLabel(self)
        if os.path.exists(logo_path):
            original_pixmap = QPixmap(logo_path)
            scaled_logo = original_pixmap.scaled(350, 250, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.logoLabel.setPixmap(scaled_logo)
            self.logoLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
            # Center the logo in the middle of the remaining space
            logo_x = (canvas_width - scaled_logo.width()) // 2
            logo_y = 150 # Starting after title
            self.logoLabel.setGeometry(logo_x, logo_y, scaled_logo.width(), scaled_logo.height())
        
        # Layout for progress bar
        self.progressBar = QProgressBar(self)
        self.progressBar.setGeometry(40, canvas_height - 60, canvas_width - 80, 25)
        self.progressBar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progressBar.setStyleSheet("""
            QProgressBar {
                background-color: #ecf0f1;
                color: #2c3e50;
                border: 1px solid #bdc3c7;
                border-radius: 12px;
                text-align: center;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #3498db;
                border-radius: 10px;
            }
        """)
        self.progressBar.setValue(0)

    def setProgress(self, value):
        self.progressBar.setValue(value)
        # Force UI update
        QApplication.processEvents()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Регистър на фискални устройства")
        self.setMinimumSize(1400, 800)
        
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
        
        # Tab 3: Statistics
        self.stats_tab = QWidget()
        self.setup_stats_tab()
        self.tabs.addTab(self.stats_tab, "📊 Статистика")
        self.tabs.currentChanged.connect(self.on_tab_changed)
        
        # Status bar
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("Готов")
        
        # Initial status
        self.refresh_table()
        self.refresh_products()
        
        self.current_user = None

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

    def refresh_stats(self):
        try:
            stats = get_db_stats()
            
            # Update cards
            self.card_active.findChild(QLabel, "value_label").setText(str(stats['active_contracts']))
            self.card_expired.findChild(QLabel, "value_label").setText(str(stats['expired_contracts']))
            self.card_expiring.findChild(QLabel, "value_label").setText(str(stats['expiring_soon']))
            self.card_revenue.findChild(QLabel, "value_label").setText(f"{stats['monthly_revenue']:.2f} лв.")
            
            # Update distribution
            dist_text = ""
            for model, count in stats['model_dist'].items():
                percentage = (count / stats['total_devices'] * 100) if stats['total_devices'] > 0 else 0
                dist_text += f"<b>{model}</b>: {count} бр. ({percentage:.1f}%)\n"
            
            if not dist_text:
                dist_text = "Няма данни за устройства."
                
            self.dist_label.setText(dist_text)
            
        except Exception as e:
            QMessageBox.critical(self, "Грешка", f"Грешка при зареждане на статистика: {str(e)}")

    def on_tab_changed(self, index):
        if index == 2: # Statistics tab
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

    def delete_product_action(self):
        selected = self.product_table.selectionModel().selectedRows()
        if not selected:
            return
            
        if QMessageBox.question(self, "Потвърждение", "Сигурни ли сте, че искате да изтриете този продукт?") == QMessageBox.StandardButton.Yes:
            row = selected[0].row()
            product_id = int(self.product_table.item(row, 0).text())
            if delete_product(product_id):
                self.refresh_products()

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
        toolbar = QToolBar("Главна лента")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(32, 32))
        self.addToolBar(toolbar)
        
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
        toolbar.addWidget(btn_devices)
        
        toolbar.addSeparator()
        
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
        
        btn_docs.setMenu(menu_docs)
        toolbar.addWidget(btn_docs)
        
        toolbar.addSeparator()
        
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
        toolbar.addWidget(btn_reports)
        
        toolbar.addSeparator()
        
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
        toolbar.addWidget(btn_import)
        
        toolbar.addSeparator()
        
        # Standalone: Настройки
        action_settings = QAction("🛠️ Настройки", self)
        action_settings.triggered.connect(self.show_settings)
        toolbar.addAction(action_settings)
        
        # Standalone: Одит
        action_audit = QAction("📋 Одит", self)
        action_audit.triggered.connect(self.show_audit_log)
        toolbar.addAction(action_audit)
        
        toolbar.addSeparator()
        
        # Standalone: Обнови
        action_refresh = QAction("🔄 Обнови", self)
        action_refresh.triggered.connect(self.clear_filters)
        toolbar.addAction(action_refresh)

        toolbar.addSeparator()

        action_about = QAction("ℹ️ За програмата", self)
        action_about.triggered.connect(self.show_about)
        toolbar.addAction(action_about)
        
        # New: Tab switching actions for clarity
        toolbar.addSeparator()
        
        action_tab_devices = QAction("🏢 Устройства", self)
        action_tab_devices.triggered.connect(lambda: self.tabs.setCurrentIndex(0))
        toolbar.addAction(action_tab_devices)
        
        action_tab_products = QAction("📦 Продукти", self)
        action_tab_products.triggered.connect(lambda: self.tabs.setCurrentIndex(1))
        toolbar.addAction(action_tab_products)

    def show_about(self):
        """Show About dialog"""
        QMessageBox.about(self, "За програмата", 
            """<h3>Contracts App Professional</h3>
            <p><b>Версия:</b> 1.0.5</p>
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
        """Reload all devices into table"""
        self.statusBar.showMessage("Зареждане на данни...")
        data = get_all_devices()
        self.load_table(data)
        self.statusBar.showMessage(f"Заредени {len(data)} записа")
    
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
                item.setFlags(item.flags() ^ Qt.ItemFlag.ItemIsEditable) # Make items non-editable by default
                
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
        """Clear all filters and reload"""
        self.f_company.clear()
        self.f_eik.clear()
        self.f_contract.clear()
        self.f_phone.clear()
        self.f_address.clear()
        self.f_serial.clear()
        self.f_euro.setChecked(False)
        self.refresh_table()
    
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
            self.refresh_table()
            if self.current_user:
                # Retrieve contract number for logging
                contract_num = self.table.item(row, 3).text()
                log_action(self.current_user['id'], self.current_user['username'], "EDIT_DEVICE", f"Edited device ID {device_id}", contract_number=contract_num, device_id=device_id)
    
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
                QMessageBox.information(self, "Успех", "Устройството е изтрито!")
                self.refresh_table()
                if self.current_user:
                    contract_num = self.table.item(row, 3).text()
                    log_action(self.current_user['id'], self.current_user['username'], "DELETE_DEVICE", f"Deleted device ID {device_id}", contract_number=contract_num, device_id=device_id)
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
        
        if not full_data:
            QMessageBox.critical(self, "Грешка", "Неуспешно намиране на данните за устройството.")
            return

        from contract_generator import clean_numeric
        client_eik = clean_numeric(full_data.get('eik', ''))
        fdrid = clean_numeric(full_data.get('fdrid', ''))

        from path_utils import get_app_root
        output_dir = os.path.join(get_app_root(), "Generated")
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
                from path_utils import get_app_root
                output_dir = os.path.join(get_app_root(), "Generated")
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
        from path_utils import get_app_root
        settings_path = os.path.join(get_app_root(), "data", "settings.json")
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

        output_dir = os.path.join(get_app_root(), "Generated")
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
            
        from dialogs import AuditLogDialog
        dialog = AuditLogDialog(self)
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
    splash.setProgress(20)
    
    # Initialize DB (migrations etc)
    init_db()
    splash.setProgress(80)
    
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
