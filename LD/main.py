import sys
import os

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTableWidget, QTableWidgetItem,
    QPushButton, QVBoxLayout, QWidget, QHBoxLayout, QLineEdit,
    QCheckBox, QMessageBox, QFileDialog, QStatusBar, QMenu, QToolBar,
    QSplashScreen, QProgressBar, QLabel, QToolButton, QDialog
)
from PyQt6.QtCore import Qt, QTimer, QSize
from PyQt6.QtGui import QAction, QIcon, QPixmap

from database import (
    init_db, get_all_devices, search_devices, delete_device,
    get_client_by_contract, get_devices_by_contract
)
from contract_generator import generate_service_contract, generate_nap_xml
from dialogs import (
    AddDeviceDialog, EditDeviceDialog, AddToExistingContractDialog,
    ExpiringContractsDialog, SettingsDialog, LoginDialog
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
        self.setMinimumSize(1400, 700)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        
        # Create toolbar
        self.create_toolbar()
        
        # Create filter panel
        filter_panel = self.create_filter_panel()
        main_layout.addLayout(filter_panel)
        
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
        
        # Enable sorting
        self.table.setSortingEnabled(True)
        
        # Set column widths
        self.table.setColumnWidth(1, 80)   # Contract
        self.table.setColumnWidth(2, 80)   # Status
        self.table.setColumnWidth(3, 200)  # Company
        self.table.setColumnWidth(4, 90)   # EIK
        self.table.setColumnWidth(5, 50)   # VAT
        self.table.setColumnWidth(6, 120)  # MOL
        self.table.setColumnWidth(7, 80)   # City
        self.table.setColumnWidth(8, 50)   # Postal
        self.table.setColumnWidth(9, 200)  # Address
        self.table.setColumnWidth(10, 90)  # Phone1
        self.table.setColumnWidth(11, 90)  # Phone2
        self.table.setColumnWidth(12, 90)  # Start
        self.table.setColumnWidth(13, 90)  # Expiry
        self.table.setColumnWidth(14, 120) # Obj Name
        self.table.setColumnWidth(15, 200) # Obj Addr
        self.table.setColumnWidth(16, 90)  # Obj Phone
        self.table.setColumnWidth(17, 120) # Model
        self.table.setColumnWidth(18, 100) # Serial
        self.table.setColumnWidth(19, 100) # FDRID
        self.table.setColumnWidth(20, 100) # FM
        self.table.setColumnWidth(21, 80)  # Cert
        self.table.setColumnWidth(22, 90)  # Cert Exp
        self.table.setColumnWidth(23, 50)  # Euro
        self.table.setColumnWidth(24, 60)  # NRA
        
        # Double-click to edit
        self.table.doubleClicked.connect(self.edit_selected_device)
        
        # Right-click context menu
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        
        main_layout.addWidget(self.table)
        
        # Status bar
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("Готов")
        
        # Load initial data
        self.refresh_table()
        
        self.current_user = None

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
        selected_rows = self.table.selectionModel().selectedRows()
        
        if not selected_rows:
            QMessageBox.warning(self, "Внимание", "Моля, изберете устройство за редактиране!")
            return
        
        # Get device ID from first column (hidden)
        row = selected_rows[0].row()
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
        selected_rows = self.table.selectionModel().selectedRows()
        
        if not selected_rows:
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
            row = selected_rows[0].row()
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
            self.run_nap_xml_generation()
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
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "Внимание", "Моля, изберете устройство!")
            return
            
        row = selected_rows[0].row()
        item = self.table.item(row, 0)
        device_id = item.data(Qt.ItemDataRole.UserRole)
        
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
                count = import_contracts_simple(filename)
                self.refresh_table()
                if self.current_user:
                    log_action(self.current_user['id'], self.current_user['username'], "IMPORT_DATA", f"Imported {count} records")
                QMessageBox.information(self, "Успех", f"Импортирани са {count} записа.")

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
                os.startfile(output_file)
                self.statusBar.showMessage(f"Договорът е генериран: {os.path.basename(output_file)}", 5000)
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
    
    # Set application style
    app.setStyle('Fusion')
    
    # Create login dialog
    login = LoginDialog()
    
    # Close splash before login or after? 
    # Usually better to close splash, show login. 
    # But user wants splash to finish loading first.
    splash.finish(login) # Use login as the widget to switch to
    
    if login.exec() == QDialog.DialogCode.Accepted:
        # Create and show main window
        window = MainWindow()
        window.set_user(login.user)
        window.show()
        sys.exit(app.exec())
    else:
        sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        with open("crash_log.txt", "w") as f:
            f.write(traceback.format_exc())
        
        # Also try to show message box if QApplication exists
        try:
            from PyQt6.QtWidgets import QMessageBox, QApplication
            if QApplication.instance():
                QMessageBox.critical(None, "Fatal Error", f"Fatal error:\n{str(e)}")
        except:
            pass
        sys.exit(1)
