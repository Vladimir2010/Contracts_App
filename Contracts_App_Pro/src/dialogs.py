from PyQt6.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout,
    QComboBox, QMessageBox, QDateEdit, QCheckBox, QLabel, QTabWidget, QWidget,
    QFileDialog, QSpinBox, QDoubleSpinBox, QCompleter, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QTextEdit, QGroupBox, QGridLayout, QListWidget
)
from PyQt6.QtCore import QDate, Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from vat_check import check_vat
from database import (
    get_all_certificates, add_client, add_device, get_client_by_contract,
    get_all_contract_numbers, update_device, get_device_full,
    get_next_contract_number, get_devices_for_nra_report, add_repair_record,
    add_product, update_product, delete_product, get_all_products,
    get_next_invoice_number, add_invoice, get_all_invoices, update_invoice,
    update_client, delete_client, search_clients, get_connection,
    get_all_counterparties, add_counterparty, update_counterparty, add_handover_protocol,
    get_setting
)
from database import get_all_clients # Added separate to avoid messing up multiline
from email_manager import send_email_with_attachment
from export_excel import export_to_excel
from export_word import export_to_word
from export_pdf import export_to_pdf, generate_invoice_pdf
from export_protocol import generate_handover_protocol
from date_utils import format_date_bg, qdate_to_db, db_to_qdate
from datetime import datetime
import os
import json
import re

def get_user_auth(obj):
    """Helper to find current user in parent chain"""
    from PyQt6.QtWidgets import QWidget
    parent = obj.parent()
    while parent:
        if hasattr(parent, 'user') and parent.user:
            return parent.user.get('id'), parent.user.get('username', 'SYSTEM')
        if not isinstance(parent, QWidget): break
        parent = parent.parent()
    return None, "SYSTEM"


class AddDeviceDialog(QDialog):
    """Dialog for adding a new device with complete client information"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Добавяне на ново устройство")
        self.setMinimumWidth(700)
        
        # Create tabs for better organization
        tabs = QTabWidget()
        
        # Tab 1: Client Information
        client_tab = QWidget()
        client_layout = QFormLayout()
        
        self.contract_number = QLineEdit()
        self.contract_number.setText(get_next_contract_number())
        self.status = QComboBox()
        self.status.addItems(["", "активен", "бракувана", "прекратен"])
        self.status.setEditable(True)
        self.status.setCurrentText("активен")
        
        self.contract_start = QDateEdit()
        self.contract_start.setCalendarPopup(True)
        self.contract_start.setDisplayFormat("dd.MM.yyyy 'г.'")
        self.contract_start.setDate(QDate.currentDate())
        
        self.contract_expiry = QDateEdit()
        self.contract_expiry.setCalendarPopup(True)
        self.contract_expiry.setDisplayFormat("dd.MM.yyyy 'г.'")
        self.contract_expiry.setDate(QDate.currentDate().addYears(1))
        
        self.company_name = QLineEdit()
        self.city = QLineEdit()
        self.postal_code = QLineEdit()
        self.address = QLineEdit()
        
        # Load and setup autocomplete
        self.setup_autocomplete()
        
        self.eik = QLineEdit()
        self.vat_registered = QComboBox()
        self.vat_registered.addItems(["", "да", "не"])
        
        self.vat_check_btn = QPushButton("🔍 Провери ЗДДС")
        self.vat_check_btn.clicked.connect(self.check_vat_status)
        
        self.mol = QLineEdit()
        self.phone1 = QLineEdit()
        self.phone2 = QLineEdit()
        
        client_layout.addRow("№ Договор *:", self.contract_number)
        client_layout.addRow("Статус:", self.status)
        client_layout.addRow("Начало на договор:", self.contract_start)
        client_layout.addRow("Изтичане на договор:", self.contract_expiry)
        client_layout.addRow("Име на фирма *:", self.company_name)
        client_layout.addRow("Град:", self.city)
        client_layout.addRow("Пощенски код:", self.postal_code)
        client_layout.addRow("Адрес:", self.address)
        client_layout.addRow("ЕИК:", self.eik)
        client_layout.addRow("ЗДДС регистрация:", self.vat_registered)
        client_layout.addRow("", self.vat_check_btn)
        client_layout.addRow("МОЛ:", self.mol)
        client_layout.addRow("Телефон 1:", self.phone1)
        client_layout.addRow("Телефон 2:", self.phone2)
        
        client_tab.setLayout(client_layout)
        
        # Tab 2: Device Information
        device_tab = QWidget()
        device_layout = QFormLayout()
        
        self.fdrid = QLineEdit()
        self.euro_done = QCheckBox("Направено ЕВРО")
        
        self.object_name = QLineEdit()
        self.object_address = QLineEdit()
        self.object_phone = QLineEdit()
        
        # Brand and Model Logic
        self.brand = QComboBox()
        self.brand.addItems(["Избери марка", "Tremol", "Daisy", "Datecs"])
        self.brand.currentTextChanged.connect(self.on_brand_changed)
        
        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        
        # Models data
        self.models_data = {
            "Tremol": ["M20","M23","S25","S21","A19+","ZM-KL V2","ZS-KL V2"],
            "Daisy": ["Compact S","Compact S 01","Compact S 02","Comapct S 03","Compact M",
                      "Compact M 01","Compact M 02","eXpert 01","eXpertSX","eXperts SX 01",
                      "Micro C 01","Perfect M","Perfect M 01","Perfect S","Perfect S 01","Perfect S 03"],
            "Datecs": ["DP-05L","WP-50","WP-50X","WP-50MX","DP-150","DP-150T KL","DP-150 KL",
                      "DP-150MX","DP-25 KL","DP-25 MX","WP-500X","DP-05B","FP 700","FP 700 X",
                      "FP 700 MX","FP 800","FP2000"]
        }
        
        # Certificate dropdown with auto-date
        cert_layout = QHBoxLayout()
        self.certificate_number = QComboBox()
        self.certificate_number.setEditable(True)
        self.certificate_number.currentTextChanged.connect(self.on_certificate_changed)
        self.load_certificates()
        cert_layout.addWidget(self.certificate_number)
        
        self.certificate_expiry = QDateEdit()
        self.certificate_expiry.setCalendarPopup(True)
        self.certificate_expiry.setDisplayFormat("dd.MM.yyyy 'г.'")
        self.certificate_expiry.setDate(QDate.currentDate())
        
        self.serial_number = QLineEdit()
        self.fiscal_memory = QLineEdit()
        self.maintenance_price = QDoubleSpinBox()
        self.maintenance_price.setRange(0, 10000)
        self.maintenance_price.setSuffix(" лв.")
        self.maintenance_price.setValue(0)
        
        device_layout.addRow("FDRID:", self.fdrid)
        device_layout.addRow("", self.euro_done)
        device_layout.addRow("Име на обект:", self.object_name)
        device_layout.addRow("Адрес на обект:", self.object_address)
        device_layout.addRow("Телефон на обект:", self.object_phone)
        device_layout.addRow("Марка:", self.brand)
        device_layout.addRow("Модел:", self.model_combo)
        device_layout.addRow("№ Свидетелство:", self.certificate_number)
        device_layout.addRow("Изтичане свидетелство:", self.certificate_expiry)
        device_layout.addRow("Сериен номер:", self.serial_number)
        device_layout.addRow("№ Фискална памет:", self.fiscal_memory)
        device_layout.addRow("Дежурна такса:", self.maintenance_price)
        
        # Connect phone formatting
        self.phone1.editingFinished.connect(lambda: self.format_phone(self.phone1))
        self.phone2.editingFinished.connect(lambda: self.format_phone(self.phone2))
        self.object_phone.editingFinished.connect(lambda: self.format_phone(self.object_phone))
        
        device_tab.setLayout(device_layout)
        
        # Tab 3: NRA Report (Decree H-18)
        nra_tab = QWidget()
        nra_layout = QFormLayout()
        
        self.nra_report_enabled = QCheckBox("Включи в месечния отчет към НАП")
        self.nra_report_enabled.setChecked(True)
        
        self.nra_report_month = QLineEdit(datetime.now().strftime('%m.%Y'))
        self.nra_td = QComboBox()
        self.nra_td.addItems(["СОФИЯ", "ПЛОВДИВ", "ВАРНА", "БУРГАС", "ВЕЛИКО ТЪРНОВО"])
        self.nra_td.setEditable(True)
        self.nra_td.setCurrentText("СОФИЯ")
        
        self.bim_model = QLineEdit()
        self.bim_date = QDateEdit()
        self.bim_date.setCalendarPopup(True)
        self.bim_date.setDisplayFormat("dd.MM.yyyy 'г.'")
        self.bim_date.setDate(QDate.currentDate())
        
        nra_layout.addRow("", self.nra_report_enabled)
        nra_layout.addRow("Месец за отчет (мм.гггг):", self.nra_report_month)
        nra_layout.addRow("Териториална дирекция:", self.nra_td)
        nra_layout.addRow(QLabel("<b>Данни от БИМ:</b>"))
        nra_layout.addRow("Модел:", self.bim_model)
        nra_layout.addRow("Дата Свидетелство:", self.bim_date)
        
        nra_tab.setLayout(nra_layout)
        
        # Add tabs
        tabs.addTab(client_tab, "Данни за клиент")
        tabs.addTab(device_tab, "Данни за устройство")
        tabs.addTab(nra_tab, "Отчет НАП (Н-18)")
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_save = QPushButton("💾 Запази")
        btn_save.clicked.connect(self.save_device)
        btn_cancel = QPushButton("❌ Отказ")
        btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_cancel)
        
        # Main layout
        main_layout = QVBoxLayout()
        main_layout.addWidget(tabs)
        main_layout.addLayout(btn_layout)
        
        self.setLayout(main_layout)
    
    def on_brand_changed(self, brand):
        """Update model dropdown and serial prefix based on selected brand"""
        self.model_combo.clear()
        
        # Update models
        if brand in self.models_data:
            self.model_combo.addItems(self.models_data[brand])
            
        # Auto-fill serial number prefix
        prefix_map = {
            "Tremol": "ZK",
            "Datecs": "DT",
            "Daisy": "DY"
        }
        
        if brand in prefix_map:
            self.serial_number.setText(prefix_map[brand])
            self.serial_number.setFocus() # Focus to allow immediate typing
    
    def load_certificates(self):
        """Load certificates from database"""
        self.certificate_number.clear()
        self.certificate_number.addItem("")
        
        certs = get_all_certificates()
        self.cert_dict = {}
        
        for cert_num, expiry in certs:
            self.certificate_number.addItem(cert_num)
            self.cert_dict[cert_num] = expiry
    
    def on_certificate_changed(self, cert_num):
        """Auto-fill certificate expiry date when certificate is selected"""
        if cert_num in self.cert_dict:
            expiry_str = self.cert_dict[cert_num]
            if expiry_str:
                try:
                    date_obj = datetime.strptime(expiry_str, '%Y-%m-%d')
                    self.certificate_expiry.setDate(QDate(date_obj.year, date_obj.month, date_obj.day))
                except:
                    pass
    
    def check_vat_status(self):
        """Check VAT registration status online and fill data"""
        eik = self.eik.text().strip()
        if not eik:
            QMessageBox.warning(self, "Грешка", "Моля, въведете ЕИК първо.")
            return

        # Clear existing company fields before new check
        self.company_name.clear()
        self.address.clear()
        self.mol.clear()
        self.city.clear()
        self.postal_code.clear()
        self.vat_registered.setCurrentText("не")
        
        result = check_vat(eik)
        
        if result is None:
            QMessageBox.warning(
                self,
                "Няма връзка",
                "Няма интернет връзка или услугата е недостъпна.\nМоля, въведете ръчно."
            )
        else:
            # Populate fields if we found ANY info (even if not VAT registered)
            if result.get("name"):
                self.company_name.setText(result.get("name", ""))
                self.address.setText(result.get("address", ""))
                self.mol.setText(result.get("mol", ""))
                self.city.setText(result.get("city", ""))
                self.postal_code.setText(result.get("postal_code", ""))
                
                if result.get("valid"):
                    self.vat_registered.setCurrentText("да")
                    status_text = "ДА"
                else:
                    self.vat_registered.setCurrentText("не")
                    status_text = "НЕ"
                
                QMessageBox.information(
                    self, 
                    "Успех", 
                    f"ЗДДС регистрация: {status_text}\n"
                    f"Фирма: {result.get('name')}\n"
                    f"МОЛ: {result.get('mol')}\n"
                    f"Град: {result.get('city')} {result.get('postal_code')}"
                )
            else:
                self.vat_registered.setCurrentText("не")
                QMessageBox.information(self, "Резултат", "Не бе открита информация за този ЕИК.")

    def setup_autocomplete(self):
        """Setup City and Postal Code autocomplete"""
        try:
            from path_utils import get_resource_path
            flat_file = get_resource_path("LD/bg_places_flat.json")
            if not os.path.exists(flat_file):
                return
                
            with open(flat_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # City Completer
            self.city_completer = QCompleter(data.get("cities", []))
            self.city_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            self.city_completer.setFilterMode(Qt.MatchFlag.MatchContains)
            self.city.setCompleter(self.city_completer)
            
            # Postal Code Completer (shows PC - City)
            self.post_completer = QCompleter(data.get("postal_codes", []))
            self.post_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            self.post_completer.setFilterMode(Qt.MatchFlag.MatchContains)
            self.postal_code.setCompleter(self.post_completer)
            
            # Auto-fill City when Postal Code is selected
            self.post_completer.activated.connect(self.on_post_activated)
            
        except Exception as e:
            print(f"Autocomplete Error: {e}")

    def on_post_activated(self, text):
        """When postal code is chosen from list, split it and fill City"""
        if " - " in text:
            parts = text.split(" - ")
            code = parts[0].strip()
            city = parts[1].strip()
            
            self.postal_code.setText(code)
            self.city.setText(city)

    def format_phone(self, line_edit):
        """Automatically format phone numbers: 0888/728-005 or 02/870-5657"""
        text = line_edit.text().strip()
        # Remove all non-digits to start over
        digits = "".join(filter(str.isdigit, text))
        
        if not digits:
            return

        formatted = digits
        if len(digits) == 10: # Mobile
            # 0888728005 -> 0888/728-005
            formatted = f"{digits[:4]}/{digits[4:7]}-{digits[7:]}"
        elif len(digits) == 9: # Fixed (Sofia or major city)
            # 028705657 -> 02/870-5657
            # Note: Sofia codes can be 1 or 2 digits, but 9 total is common for major cities
            # We'll assume first 2 digits are the code for 9-digit numbers
            formatted = f"{digits[:2]}/{digits[2:5]}-{digits[5:]}"
        elif len(digits) == 8: # Smaller city
             formatted = f"{digits[:3]}/{digits[3:5]}-{digits[5:]}"
            
        line_edit.setText(formatted)
    
    def save_device(self):
        """Validate and save device"""
        # Validation
        if not self.contract_number.text().strip():
            QMessageBox.warning(self, "Грешка", "Номер на договор е задължителен!")
            return
        
        if not self.company_name.text().strip():
            QMessageBox.warning(self, "Грешка", "Име на фирма е задължително!")
            return
        
        try:
            # Prepare client data
            client_data = {
                'contract_number': self.contract_number.text().strip(),
                'status': self.status.currentText(),
                'contract_start': self.contract_start.date().toString('yyyy-MM-dd'),
                'contract_expiry': self.contract_expiry.date().toString('yyyy-MM-dd'),
                'company_name': self.company_name.text().strip(),
                'city': self.city.text().strip(),
                'postal_code': self.postal_code.text().strip(),
                'address': self.address.text().strip(),
                'eik': self.eik.text().strip(),
                'vat_registered': self.vat_registered.currentText(),
                'mol': self.mol.text().strip(),
                'phone1': self.phone1.text().strip(),
                'phone2': self.phone2.text().strip()
            }
            
            # Prepare device data
            # Format numbers (remove .0)
            fdrid = self.fdrid.text().strip()
            if fdrid.endswith('.0'): fdrid = fdrid[:-2]
            
            serial = self.serial_number.text().strip()
            if serial.endswith('.0'): serial = serial[:-2]
            
            fiscal = self.fiscal_memory.text().strip()
            if fiscal.endswith('.0'): fiscal = fiscal[:-2]
            
            # Construct model
            brand = self.brand.currentText()
            model_txt = self.model_combo.currentText().strip()
            
            if brand == "Избери марка" or not brand:
                full_model = model_txt
            else:
                full_model = f"{brand} {model_txt}"
            
            device_data = {
                'fdrid': fdrid,
                'euro_done': self.euro_done.isChecked(),
                'object_name': self.object_name.text().strip(),
                'object_address': self.object_address.text().strip(),
                'object_phone': self.object_phone.text().strip(),
                'model': full_model,
                'certificate_number': self.certificate_number.currentText().strip(),
                'certificate_expiry': self.certificate_expiry.date().toString('yyyy-MM-dd'),
                'serial_number': serial,
                'fiscal_memory': fiscal,
                'nra_report_enabled': self.nra_report_enabled.isChecked(),
                'nra_report_month': self.nra_report_month.text().strip(),
                'nra_td': self.nra_td.currentText().strip(),
                'bim_model': self.bim_model.text().strip(),
                'bim_date': self.bim_date.date().toString('yyyy-MM-dd'),
                'maintenance_price': self.maintenance_price.value()
            }
            
            # Add to database
            client_id = add_client(client_data)
            add_device(client_id, device_data)
            
            QMessageBox.information(self, "Успех", "Устройството е добавено успешно!")
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "Грешка", f"Грешка при запазване: {str(e)}")


class AddToExistingContractDialog(QDialog):
    """Dialog for adding a device to an existing contract"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Добавяне на устройство към съществуващ договор")
        self.setMinimumWidth(600)
        
        layout = QVBoxLayout()
        
        # Contract selection
        contract_layout = QHBoxLayout()
        contract_layout.addWidget(QLabel("Изберете договор:"))
        
        self.contract_combo = QComboBox()
        self.contract_combo.setEditable(True)
        self.load_contracts()
        self.contract_combo.currentTextChanged.connect(self.on_contract_selected)
        contract_layout.addWidget(self.contract_combo)
        
        layout.addLayout(contract_layout)
        
        # Client info display (read-only)
        self.client_info = QLabel("Изберете договор за да видите информацията")
        self.client_info.setStyleSheet("padding: 10px; background-color: #f0f0f0; border-radius: 5px;")
        layout.addWidget(self.client_info)
        
        # Device fields
        form = QFormLayout()
        
        self.fdrid = QLineEdit()
        self.euro_done = QCheckBox("Направено ЕВРО")
        self.object_name = QLineEdit()
        self.object_address = QLineEdit()
        self.object_phone = QLineEdit()
        self.object_phone.editingFinished.connect(lambda: self.format_phone(self.object_phone))
        self.model = QLineEdit()
        
        self.certificate_number = QComboBox()
        self.certificate_number.setEditable(True)
        self.certificate_number.currentTextChanged.connect(self.on_certificate_changed)
        self.load_certificates()
        
        self.certificate_expiry = QDateEdit()
        self.certificate_expiry.setCalendarPopup(True)
        self.certificate_expiry.setDisplayFormat("dd.MM.yyyy 'г.'")
        self.certificate_expiry.setDate(QDate.currentDate())
        
        self.serial_number = QLineEdit()
        self.fiscal_memory = QLineEdit()
        
        self.nra_report_enabled = QCheckBox("Включи в месечния отчет към НАП")
        self.nra_report_enabled.setChecked(True)
        self.nra_report_month = QLineEdit(datetime.now().strftime('%m.%Y'))
        self.nra_td = QComboBox()
        self.nra_td.addItems(["СОФИЯ", "ПЛОВДИВ", "ВАРНА", "БУРГАС", "ВЕЛИКО ТЪРНОВО"])
        self.nra_td.setEditable(True)
        self.nra_td.setCurrentText("СОФИЯ")
        self.bim_model = QLineEdit()
        self.bim_date = QDateEdit()
        self.bim_date.setCalendarPopup(True)
        self.bim_date.setDisplayFormat("dd.MM.yyyy 'г.'")
        self.bim_date.setDate(QDate.currentDate())
        
        form.addRow("FDRID:", self.fdrid)
        form.addRow("", self.euro_done)
        form.addRow("Име на обект:", self.object_name)
        form.addRow("Адрес на обект:", self.object_address)
        form.addRow("Телефон на обект:", self.object_phone)
        form.addRow("Модел:", self.model)
        form.addRow("№ Свидетелство:", self.certificate_number)
        form.addRow("Изтичане свидетелство:", self.certificate_expiry)
        form.addRow("Сериен номер:", self.serial_number)
        form.addRow("№ Фискална памет:", self.fiscal_memory)
        form.addRow(QLabel("<b>Отчет към НАП (Н-18):</b>"))
        form.addRow("", self.nra_report_enabled)
        form.addRow("Месец за отчет:", self.nra_report_month)
        form.addRow("Териториална дирекция:", self.nra_td)
        form.addRow("БИМ Модел:", self.bim_model)
        form.addRow("БИМ Дата:", self.bim_date)
        
        # Connect phone formatting
        # These lines are incorrect as self.phone1 and self.phone2 are not attributes of this class
        # self.phone1.editingFinished.connect(lambda: self.format_phone(self.phone1))
        # self.phone2.editingFinished.connect(lambda: self.format_phone(self.phone2))
        self.object_phone.editingFinished.connect(lambda: self.format_phone(self.object_phone))
        
        layout.addLayout(form)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_save = QPushButton("💾 Запази")
        btn_save.clicked.connect(self.save_device)
        btn_cancel = QPushButton("❌ Отказ")
        btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_cancel)
        
        layout.addLayout(btn_layout)
        self.setLayout(layout)
        
        self.current_client_id = None

    
    def load_contracts(self):
        """Load existing contract numbers"""
        self.contract_combo.clear()
        self.contract_combo.addItem("")
        contracts = get_all_contract_numbers()
        self.contract_combo.addItems(contracts)
    
    def load_certificates(self):
        """Load certificates from database"""
        self.certificate_number.clear()
        self.certificate_number.addItem("")
        
        certs = get_all_certificates()
        self.cert_dict = {}
        
        for cert_num, expiry in certs:
            self.certificate_number.addItem(cert_num)
            self.cert_dict[cert_num] = expiry
    
    def on_certificate_changed(self, cert_num):
        """Auto-fill certificate expiry date"""
        if cert_num in self.cert_dict:
            expiry_str = self.cert_dict[cert_num]
            if expiry_str:
                try:
                    date_obj = datetime.strptime(expiry_str, '%Y-%m-%d')
                    self.certificate_expiry.setDate(QDate(date_obj.year, date_obj.month, date_obj.day))
                except:
                    pass
    
    def on_contract_selected(self, contract_num):
        """Load and display client info when contract is selected"""
        if not contract_num:
            self.client_info.setText("Изберете договор за да видите информацията")
            self.current_client_id = None
            return
        
        client = get_client_by_contract(contract_num)
        if client:
            self.current_client_id = client['id']
            info_text = f"""
            <b>Фирма:</b> {client['company_name']}<br>
            <b>ЕИК:</b> {client['eik']}<br>
            <b>Адрес:</b> {client['address']}<br>
            <b>Телефон:</b> {client['phone1']}
            """
            self.client_info.setText(info_text)
        else:
            self.client_info.setText("Договорът не е намерен")
            self.current_client_id = None
    
    def save_device(self):
        """Save new device to existing contract"""
        if not self.current_client_id:
            QMessageBox.warning(self, "Грешка", "Моля, изберете договор!")
            return
        
        try:
            device_data = {
                'fdrid': self.fdrid.text().strip(),
                'euro_done': self.euro_done.isChecked(),
                'object_name': self.object_name.text().strip(),
                'object_address': self.object_address.text().strip(),
                'object_phone': self.object_phone.text().strip(),
                'model': self.model.text().strip(),
                'certificate_number': self.certificate_number.currentText().strip(),
                'certificate_expiry': self.certificate_expiry.date().toString('yyyy-MM-dd'),
                'serial_number': self.serial_number.text().strip(),
                'fiscal_memory': self.fiscal_memory.text().strip(),
                'nra_report_enabled': self.nra_report_enabled.isChecked(),
                'nra_report_month': self.nra_report_month.text().strip(),
                'nra_td': self.nra_td.currentText().strip(),
                'bim_model': self.bim_model.text().strip(),
                'bim_date': self.bim_date.date().toString('yyyy-MM-dd')
            }
            
            add_device(self.current_client_id, device_data)
            
            QMessageBox.information(self, "Успех", "Устройството е добавено успешно!")
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "Грешка", f"Грешка при запазване: {str(e)}")

    def format_phone(self, line_edit):
        """Automatically format phone numbers"""
        text = line_edit.text().strip()
        digits = "".join(filter(str.isdigit, text))
        if not digits: return
        formatted = digits
        if len(digits) == 10:
            formatted = f"{digits[:4]}/{digits[4:7]}-{digits[7:]}"
        elif len(digits) == 9:
            formatted = f"{digits[:2]}/{digits[2:5]}-{digits[5:]}"
        elif len(digits) == 8:
            formatted = f"{digits[:3]}/{digits[3:5]}-{digits[5:]}"
        line_edit.setText(formatted)


class EditDeviceDialog(QDialog):
    """Dialog for editing an existing device"""
    
    def __init__(self, device_id: int, parent=None):
        super().__init__(parent)
        self.device_id = device_id
        self.setWindowTitle("Редактиране на устройство")
        self.setMinimumWidth(700)
        
        # Load device data
        device_data = get_device_full(device_id)
        if not device_data:
            QMessageBox.critical(self, "Грешка", "Устройството не е намерено!")
            self.reject()
            return
        
        # Create tabs
        tabs = QTabWidget()
        
        # Tab 1: Client Information
        client_tab = QWidget()
        client_layout = QFormLayout()
        
        self.contract_number = QLineEdit(device_data.get('contract_number', ''))
        self.status = QComboBox()
        self.status.addItems(["", "активен", "бракувана", "прекратен"])
        self.status.setEditable(True)
        self.status.setCurrentText(device_data.get('status', ''))
        
        self.contract_start = QDateEdit()
        self.contract_start.setCalendarPopup(True)
        self.contract_start.setDisplayFormat("dd.MM.yyyy 'г.'")
        self.set_date_from_string(self.contract_start, device_data.get('contract_start'))
        
        self.contract_expiry = QDateEdit()
        self.contract_expiry.setCalendarPopup(True)
        self.contract_expiry.setDisplayFormat("dd.MM.yyyy 'г.'")
        self.set_date_from_string(self.contract_expiry, device_data.get('contract_expiry'))
        
        self.company_name = QLineEdit(device_data.get('company_name', ''))
        self.city = QLineEdit(device_data.get('city', ''))
        self.postal_code = QLineEdit(device_data.get('postal_code', ''))
        self.address = QLineEdit(device_data.get('address', ''))
        
        # Setup autocomplete
        self.setup_autocomplete()
        
        self.eik = QLineEdit(device_data.get('eik', ''))
        self.vat_registered = QComboBox()
        self.vat_registered.addItems(["", "да", "не"])
        self.vat_registered.setCurrentText(device_data.get('vat_registered', ''))
        
        self.vat_check_btn = QPushButton("🔍 Провери ЗДДС")
        self.vat_check_btn.clicked.connect(self.check_vat_status)
        
        self.mol = QLineEdit(device_data.get('mol', ''))
        self.phone1 = QLineEdit(device_data.get('phone1', ''))
        self.phone2 = QLineEdit(device_data.get('phone2', ''))
        
        client_layout.addRow("№ Договор *:", self.contract_number)
        client_layout.addRow("Статус:", self.status)
        client_layout.addRow("Начало на договор:", self.contract_start)
        client_layout.addRow("Изтичане на договор:", self.contract_expiry)
        client_layout.addRow("Име на фирма *:", self.company_name)
        client_layout.addRow("Град:", self.city)
        client_layout.addRow("Пощенски код:", self.postal_code)
        client_layout.addRow("Адрес:", self.address)
        client_layout.addRow("ЕИК:", self.eik)
        client_layout.addRow("ЗДДС регистрация:", self.vat_registered)
        client_layout.addRow("", self.vat_check_btn)
        client_layout.addRow("МОЛ:", self.mol)
        client_layout.addRow("Телефон 1:", self.phone1)
        client_layout.addRow("Телефон 2:", self.phone2)
        
        client_tab.setLayout(client_layout)
        
        # Tab 2: Device Information
        device_tab = QWidget()
        device_layout = QFormLayout()
        
        self.fdrid = QLineEdit(device_data.get('fdrid', ''))
        self.euro_done = QCheckBox("Направено ЕВРО")
        self.euro_done.setChecked(device_data.get('euro_done', False))
        
        self.object_name = QLineEdit(device_data.get('object_name', ''))
        self.object_address = QLineEdit(device_data.get('object_address', ''))
        self.object_phone = QLineEdit(device_data.get('object_phone', ''))
        
        self.model = QLineEdit(device_data.get('model', ''))
        
        self.certificate_number = QComboBox()
        self.certificate_number.setEditable(True)
        self.certificate_number.currentTextChanged.connect(self.on_certificate_changed)
        self.load_certificates()
        self.certificate_number.setCurrentText(device_data.get('certificate_number', ''))
        
        self.certificate_expiry = QDateEdit()
        self.certificate_expiry.setCalendarPopup(True)
        self.certificate_expiry.setDisplayFormat("dd.MM.yyyy 'г.'")
        self.set_date_from_string(self.certificate_expiry, device_data.get('certificate_expiry'))
        
        self.serial_number = QLineEdit(device_data.get('serial_number', ''))
        self.fiscal_memory = QLineEdit(device_data.get('fiscal_memory', ''))
        self.maintenance_price = QDoubleSpinBox()
        self.maintenance_price.setRange(0, 10000)
        self.maintenance_price.setSuffix(" лв.")
        self.maintenance_price.setValue(device_data.get('maintenance_price', 0))
        
        device_layout.addRow("FDRID:", self.fdrid)
        device_layout.addRow("", self.euro_done)
        device_layout.addRow("Име на обект:", self.object_name)
        device_layout.addRow("Адрес на обект:", self.object_address)
        device_layout.addRow("Телефон на обект:", self.object_phone)
        device_layout.addRow("Модел:", self.model)
        device_layout.addRow("№ Свидетелство:", self.certificate_number)
        device_layout.addRow("Изтичане свидетелство:", self.certificate_expiry)
        device_layout.addRow("Сериен номер:", self.serial_number)
        device_layout.addRow("№ Фискална памет:", self.fiscal_memory)
        device_layout.addRow("Дежурна такса:", self.maintenance_price)
        
        # Connect phone formatting
        self.phone1.editingFinished.connect(lambda: self.format_phone(self.phone1))
        self.phone2.editingFinished.connect(lambda: self.format_phone(self.phone2))
        self.object_phone.editingFinished.connect(lambda: self.format_phone(self.object_phone))
        
        device_tab.setLayout(device_layout)
        
        # Tab 3: NRA Report (Decree H-18)
        nra_tab = QWidget()
        nra_layout = QFormLayout()
        
        self.nra_report_enabled = QCheckBox("Включи в месечния отчет към НАП")
        self.nra_report_enabled.setChecked(device_data.get('nra_report_enabled', True))
        
        self.nra_report_month = QLineEdit(device_data.get('nra_report_month', datetime.now().strftime('%m.%Y')))
        self.nra_td = QComboBox()
        self.nra_td.addItems(["СОФИЯ", "ПЛОВДИВ", "ВАРНА", "БУРГАС", "ВЕЛИКО ТЪРНОВО"])
        self.nra_td.setEditable(True)
        self.nra_td.setCurrentText(device_data.get('nra_td', 'СОФИЯ'))
        
        self.bim_model = QLineEdit(device_data.get('bim_model', ''))
        self.bim_date = QDateEdit()
        self.bim_date.setCalendarPopup(True)
        self.bim_date.setDisplayFormat("dd.MM.yyyy 'г.'")
        self.set_date_from_string(self.bim_date, device_data.get('bim_date'))
        
        nra_layout.addRow("", self.nra_report_enabled)
        nra_layout.addRow("Месец за отчет (мм.гггг):", self.nra_report_month)
        nra_layout.addRow("Териториална дирекция:", self.nra_td)
        nra_layout.addRow(QLabel("<b>Данни от БИМ:</b>"))
        nra_layout.addRow("Модел:", self.bim_model)
        nra_layout.addRow("Дата Свидетелство:", self.bim_date)
        
        nra_tab.setLayout(nra_layout)
        
        # Add tabs
        tabs.addTab(client_tab, "Данни за клиент")
        tabs.addTab(device_tab, "Данни за устройство")
        tabs.addTab(nra_tab, "Отчет НАП (Н-18)")
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_save = QPushButton("💾 Запази промените")
        btn_save.clicked.connect(self.save_changes)
        btn_cancel = QPushButton("❌ Отказ")
        btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_cancel)
        
        # Main layout
        main_layout = QVBoxLayout()
        main_layout.addWidget(tabs)
        main_layout.addLayout(btn_layout)
        
        self.setLayout(main_layout)
    
    def set_date_from_string(self, date_edit, date_str):
        """Set QDateEdit from string date"""
        if date_str:
            try:
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                date_edit.setDate(QDate(date_obj.year, date_obj.month, date_obj.day))
            except:
                date_edit.setDate(QDate.currentDate())
        else:
            date_edit.setDate(QDate.currentDate())
    
    def load_certificates(self):
        """Load certificates from database"""
        self.certificate_number.clear()
        self.certificate_number.addItem("")
        
        certs = get_all_certificates()
        self.cert_dict = {}
        
        for cert_num, expiry in certs:
            self.certificate_number.addItem(cert_num)
            self.cert_dict[cert_num] = expiry
    
    def on_certificate_changed(self, cert_num):
        """Auto-fill certificate expiry date"""
        if cert_num in self.cert_dict:
            expiry_str = self.cert_dict[cert_num]
            if expiry_str:
                try:
                    date_obj = datetime.strptime(expiry_str, '%Y-%m-%d')
                    self.certificate_expiry.setDate(QDate(date_obj.year, date_obj.month, date_obj.day))
                except:
                    pass
    
    def check_vat_status(self):
        """Check VAT registration status online and fill data"""
        eik = self.eik.text().strip()
        if not eik:
            QMessageBox.warning(self, "Грешка", "Моля, въведете ЕИК първо.")
            return

        # Clear existing company fields before new check
        self.company_name.clear()
        self.address.clear()
        self.mol.clear()
        self.city.clear()
        self.postal_code.clear()
        self.vat_registered.setCurrentText("не")
        
        result = check_vat(eik)
        
        if result is None:
            QMessageBox.warning(
                self,
                "Няма връзка",
                "Няма интернет връзка или услугата е недостъпна.\nМоля, въведете ръчно."
            )
        else:
            # Populate fields if we found ANY info
            if result.get("name"):
                self.company_name.setText(result.get("name", ""))
                self.address.setText(result.get("address", ""))
                self.mol.setText(result.get("mol", ""))
                self.city.setText(result.get("city", ""))
                self.postal_code.setText(result.get("postal_code", ""))
                
                if result.get("valid"):
                    self.vat_registered.setCurrentText("да")
                    status_text = "ДА"
                else:
                    self.vat_registered.setCurrentText("не")
                    status_text = "НЕ"
                
                QMessageBox.information(
                    self, 
                    "Успех", 
                    f"ЗДДС регистрация: {status_text}\n"
                    f"Фирма: {result.get('name')}\n"
                    f"МОЛ: {result.get('mol')}\n"
                    f"Град: {result.get('city')} {result.get('postal_code')}"
                )
            else:
                self.vat_registered.setCurrentText("не")
                QMessageBox.information(self, "Резултат", "Не бе открита информация за този ЕИК.")

    def setup_autocomplete(self):
        """Setup City and Postal Code autocomplete"""
        try:
            from path_utils import get_resource_path
            flat_file = get_resource_path("LD/bg_places_flat.json")
            if not os.path.exists(flat_file): return
            with open(flat_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.city_completer = QCompleter(data.get("cities", []))
            self.city_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            self.city_completer.setFilterMode(Qt.MatchFlag.MatchContains)
            self.city.setCompleter(self.city_completer)
            self.post_completer = QCompleter(data.get("postal_codes", []))
            self.post_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            self.post_completer.setFilterMode(Qt.MatchFlag.MatchContains)
            self.postal_code.setCompleter(self.post_completer)
            self.post_completer.activated.connect(self.on_post_activated)
        except: pass

    def on_post_activated(self, text):
        if " - " in text:
            parts = text.split(" - ")
            self.postal_code.setText(parts[0].strip())
            self.city.setText(parts[1].strip())
            
    def format_phone(self, line_edit):
        """Automatically format phone numbers"""
        text = line_edit.text().strip()
        digits = "".join(filter(str.isdigit, text))
        if not digits: return
        formatted = digits
        if len(digits) == 10:
            formatted = f"{digits[:4]}/{digits[4:7]}-{digits[7:]}"
        elif len(digits) == 9:
            formatted = f"{digits[:2]}/{digits[2:5]}-{digits[5:]}"
        elif len(digits) == 8:
            formatted = f"{digits[:3]}/{digits[3:5]}-{digits[5:]}"
        line_edit.setText(formatted)
    
    def save_changes(self):
        """Validate and save changes"""
        if not self.contract_number.text().strip():
            QMessageBox.warning(self, "Грешка", "Номер на договор е задължителен!")
            return
        
        if not self.company_name.text().strip():
            QMessageBox.warning(self, "Грешка", "Име на фирма е задължително!")
            return
        
        try:
            client_data = {
                'contract_number': self.contract_number.text().strip(),
                'status': self.status.currentText(),
                'contract_start': self.contract_start.date().toString('yyyy-MM-dd'),
                'contract_expiry': self.contract_expiry.date().toString('yyyy-MM-dd'),
                'company_name': self.company_name.text().strip(),
                'city': self.city.text().strip(),
                'postal_code': self.postal_code.text().strip(),
                'address': self.address.text().strip(),
                'eik': self.eik.text().strip(),
                'vat_registered': self.vat_registered.currentText(),
                'mol': self.mol.text().strip(),
                'phone1': self.phone1.text().strip(),
                'phone2': self.phone2.text().strip()
            }
            
            device_data = {
                'fdrid': self.fdrid.text().strip(),
                'euro_done': self.euro_done.isChecked(),
                'object_name': self.object_name.text().strip(),
                'object_address': self.object_address.text().strip(),
                'object_phone': self.object_phone.text().strip(),
                'model': self.model.text().strip(),
                'certificate_number': self.certificate_number.currentText().strip(),
                'certificate_expiry': self.certificate_expiry.date().toString('yyyy-MM-dd'),
                'serial_number': self.serial_number.text().strip(),
                'fiscal_memory': self.fiscal_memory.text().strip(),
                'nra_report_enabled': self.nra_report_enabled.isChecked(),
                'nra_report_month': self.nra_report_month.text().strip(),
                'nra_td': self.nra_td.currentText().strip(),
                'bim_model': self.bim_model.text().strip(),
                'bim_date': self.bim_date.date().toString('yyyy-MM-dd'),
                'maintenance_price': self.maintenance_price.value()
            }
            
            user_id, username = get_user_auth(self)
            if update_device(self.device_id, client_data, device_data, user_id=user_id, username=username):
                QMessageBox.information(self, "Успех", "Промените са запазени успешно!")
                self.accept()
            else:
                QMessageBox.critical(self, "Грешка", "Грешка при запазване на промените!")
                
        except Exception as e:
            QMessageBox.critical(self, "Грешка", f"Грешка при запазване: {str(e)}")


class ExpiringContractsDialog(QDialog):
    """Dialog for viewing and exporting expiring contracts"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Справка за изтичащи договори")
        self.setMinimumSize(500, 200)
        
        layout = QVBoxLayout()
        
        # Period selection
        period_layout = QHBoxLayout()
        
        period_layout.addWidget(QLabel("Месец:"))
        self.month_spin = QSpinBox()
        self.month_spin.setRange(1, 12)
        self.month_spin.setValue(datetime.now().month)
        period_layout.addWidget(self.month_spin)
        
        period_layout.addWidget(QLabel("Година:"))
        self.year_spin = QSpinBox()
        self.year_spin.setRange(2020, 2100)
        self.year_spin.setValue(datetime.now().year)
        period_layout.addWidget(self.year_spin)
        
        btn_show = QPushButton("📊 Покажи")
        btn_show.clicked.connect(self.show_results)
        period_layout.addWidget(btn_show)
        
        period_layout.addStretch()
        layout.addLayout(period_layout)
        
        # Export buttons (initially hidden)
        export_layout = QHBoxLayout()
        
        self.btn_export_excel = QPushButton("📗 Експорт в Excel")
        self.btn_export_excel.clicked.connect(self.export_excel)
        self.btn_export_excel.setVisible(False)
        export_layout.addWidget(self.btn_export_excel)
        
        self.btn_export_word = QPushButton("📘 Експорт в Word")
        self.btn_export_word.clicked.connect(self.export_word)
        self.btn_export_word.setVisible(False)
        export_layout.addWidget(self.btn_export_word)
        
        self.btn_export_pdf = QPushButton("📕 Експорт в PDF")
        self.btn_export_pdf.clicked.connect(self.export_pdf)
        self.btn_export_pdf.setVisible(False)
        export_layout.addWidget(self.btn_export_pdf)
        
        self.btn_send_email = QPushButton("📧 Изпрати по имейл")
        self.btn_send_email.clicked.connect(self.send_email_report)
        self.btn_send_email.setVisible(False)
        export_layout.addWidget(self.btn_send_email)
        
        export_layout.addStretch()
        layout.addLayout(export_layout)
        
        # Status label
        self.status_label = QLabel("")
        layout.addWidget(self.status_label)
        
        # Close button
        btn_close = QPushButton("Затвори")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)
        
        self.setLayout(layout)
        
        self.current_data = []
        self.headers = ["№ Договор", "Фирма", "Модел", "Сериен №", "Изтичане", "ЕИК", "Телефон"]
    
    def show_results(self):
        """Show expiring contracts and enable export buttons"""
        from database import get_expiring_contracts
        
        month = self.month_spin.value()
        year = self.year_spin.value()
        
        self.current_data = get_expiring_contracts(month, year)
        
        if not self.current_data:
            self.status_label.setText(f"❌ Няма изтичащи договори за {month:02d}.{year}")
            self.btn_export_excel.setVisible(False)
            self.btn_export_word.setVisible(False)
            self.btn_export_pdf.setVisible(False)
            self.btn_send_email.setVisible(False)
        else:
            count = len(self.current_data)
            self.status_label.setText(f"✅ Намерени {count} изтичащи договора за {month:02d}.{year}")
            self.btn_export_excel.setVisible(True)
            self.btn_export_word.setVisible(True)
            self.btn_export_pdf.setVisible(True)
            self.btn_send_email.setVisible(True)
            
            # Notify parent to update table
            if self.parent():
                self.parent().load_table(self.current_data, expiring_mode=True)
    
    def export_excel(self):
        """Export to Excel"""
        filename, _ = QFileDialog.getSaveFileName(
            self, "Запази Excel файл", 
            f"expiring_contracts_{self.month_spin.value():02d}_{self.year_spin.value()}.xlsx",
            "Excel Files (*.xlsx)"
        )
        
        if filename:
            if export_to_excel(self.current_data, self.headers, filename):
                QMessageBox.information(self, "Успех", f"Експортирано в:\n{filename}")
                os.startfile(filename)
            else:
                QMessageBox.critical(self, "Грешка", "Грешка при експорт!")
    
    def export_word(self):
        """Export to Word"""
        filename, _ = QFileDialog.getSaveFileName(
            self, "Запази Word файл",
            f"expiring_contracts_{self.month_spin.value():02d}_{self.year_spin.value()}.docx",
            "Word Files (*.docx)"
        )
        
        if filename:
            title = f"Справка за изтичащи договори - {self.month_spin.value():02d}.{self.year_spin.value()}"
            if export_to_word(self.current_data, self.headers, filename, title):
                QMessageBox.information(self, "Успех", f"Експортирано в:\n{filename}")
                os.startfile(filename)
            else:
                QMessageBox.critical(self, "Грешка", "Грешка при експорт!")
    
    def export_pdf(self):
        """Export to PDF"""
        filename, _ = QFileDialog.getSaveFileName(
            self, "Запази PDF файл",
            f"expiring_contracts_{self.month_spin.value():02d}_{self.year_spin.value()}.pdf",
            "PDF Files (*.pdf)"
        )
        
        if filename:
            title = f"Справка за изтичащи договори - {self.month_spin.value():02d}.{self.year_spin.value()}"
            if export_to_pdf(self.current_data, self.headers, filename, title):
                QMessageBox.information(self, "Успех", f"Експортирано в:\n{filename}")
                os.startfile(filename)
            else:
                QMessageBox.critical(self, "Грешка", "Грешка при експорт!")

    def send_email_report(self):
        """Send report via Email"""
        from path_utils import get_app_root
        import json
        
        # 1. Generate Temp PDF
        temp_pdf = os.path.join(get_app_root(), "temp_expiring_report.pdf")
        title = f"Справка за изтичащи договори - {self.month_spin.value():02d}.{self.year_spin.value()}"
        if not export_to_pdf(self.current_data, self.headers, temp_pdf, title):
            QMessageBox.critical(self, "Грешка", "Грешка при генериране на PDF файл за прикачване!")
            return

        # 2. Load SMTP settings
        settings_path = os.path.join(get_app_root(), "data", "settings.json")
        if not os.path.exists(settings_path):
            QMessageBox.warning(self, "Внимание", "Не са намерени настройки за имейл (Automation)!")
            return
            
        try:
            with open(settings_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
                auto_cfg = settings.get('automation', {})
                
                smtp_cfg = {
                    'server': auto_cfg.get('smtp_server'),
                    'port': auto_cfg.get('smtp_port', 587),
                    'user': auto_cfg.get('smtp_user'),
                    'password': auto_cfg.get('smtp_password'),
                    'use_tls': auto_cfg.get('smtp_tls', True)
                }
                recipient = auto_cfg.get('report_recipient')
                
                if not smtp_cfg['server'] or not recipient:
                    QMessageBox.warning(self, "Внимание", "Моля настройте SMTP сървър и получател в Настройки -> Автоматизация!")
                    return

                # 3. Send Email
                subject = f"Ръчна справка: {title}"
                body = f"Здравейте,\n\nВ приложение изпращам ръчно генерирана справка за изтичащи договори през {self.month_spin.value():02d}.{self.year_spin.value()}.\n\nПоздрави,\nContracts App Professional"
                
                if send_email_with_attachment(smtp_cfg, recipient, subject, body, temp_pdf):
                    QMessageBox.information(self, "Успех", f"Справката беше изпратена успешно на {recipient}!")
                else:
                    QMessageBox.critical(self, "Грешка", "Неуспешно изпращане на имейл. Проверете настройките.")
                    
        except Exception as e:
            QMessageBox.critical(self, "Грешка", f"Грешка при зареждане на настройки или изпращане: {e}")
        finally:
            # Cleanup temp file
            if os.path.exists(temp_pdf):
                try: os.remove(temp_pdf)
                except: pass

class DeregistrationDialog(QDialog):
    def __init__(self, parent=None, device_data=None):
        super().__init__(parent)
        self.device_data = device_data
        self.setWindowTitle("Данни за Протокол за Дерегистрация")
        self.setMinimumWidth(600)
        
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        # Client Info (if not in DB)
        self.eik_input = QLineEdit()
        self.company_input = QLineEdit()
        self.address_input = QLineEdit()
        self.mol_input = QLineEdit()
        
        # Device Info
        self.model_input = QLineEdit()
        self.sn_input = QLineEdit()
        self.fm_input = QLineEdit()
        self.bim_input = QLineEdit()
        self.fdrid_input = QLineEdit()
        self.obj_name_input = QLineEdit()
        self.obj_addr_input = QLineEdit()
        
        # Manufacturer
        self.manu_combo = QComboBox()
        self.manu_combo.addItems(["Дейзи", "Датекс", "Тремол"])
        
        # Reasons
        self.reason_combo = QComboBox()
        self.reason_combo.addItems([
            "препълване на фискалната памет",
            "смяна на собственика",
            "прекратена регистрацията на ФУ по инициатива на търговеца",
            "бракуване на ФУ",
            "повреда на фискалната памет, която не позволява разчитането ѝ",
            "грешка в блок на фискалната памет",
            "грешка при въвеждане в експлоатация на ФУ"
        ])
        
        # Dates
        self.date_start = QDateEdit()
        self.date_start.setCalendarPopup(True)
        self.date_start.setDate(QDate.currentDate().addYears(-1))
        
        self.date_stop = QDateEdit()
        self.date_stop.setCalendarPopup(True)
        self.date_stop.setDate(QDate.currentDate())
        
        # Turnovers
        self.turnover_input = QLineEdit("0.00")
        self.storno_total_input = QLineEdit("0.00")
        
        # Currency
        self.curr_layout = QHBoxLayout()
        self.bgn_radio = QCheckBox("Лева (лв.)")
        self.bgn_radio.setChecked(True)
        self.eur_radio = QCheckBox("Евро (€)")
        self.curr_layout.addWidget(self.bgn_radio)
        self.curr_layout.addWidget(self.eur_radio)
        
        def on_bgn(state):
            if state: self.eur_radio.setChecked(False)
        def on_eur(state):
            if state: self.bgn_radio.setChecked(False)
        self.bgn_radio.stateChanged.connect(on_bgn)
        self.eur_radio.stateChanged.connect(on_eur)
        
        # VAT Groups
        self.vat_a = QLineEdit("0.00")
        self.vat_b = QLineEdit("0.00")
        self.vat_v = QLineEdit("0.00")
        self.vat_g = QLineEdit("0.00")
        
        self.storno_a = QLineEdit("0.00")
        self.storno_b = QLineEdit("0.00")
        self.storno_v = QLineEdit("0.00")
        self.storno_g = QLineEdit("0.00")
        
        # Form Assembly
        form.addRow("ЕИК:", self.eik_input)
        form.addRow("Фирма:", self.company_input)
        form.addRow("Адрес:", self.address_input)
        form.addRow("МОЛ:", self.mol_input)
        form.addRow(QLabel("<b>Информация за устройството</b>"))
        form.addRow("Модел:", self.model_input)
        form.addRow("Сериен номер:", self.sn_input)
        form.addRow("Производител:", self.manu_combo)
        form.addRow("ФП номер:", self.fm_input)
        form.addRow("Свидетелство БИМ:", self.bim_input)
        form.addRow("FDRID:", self.fdrid_input)
        form.addRow("Обект - Име:", self.obj_name_input)
        form.addRow("Обект - Адрес:", self.obj_addr_input)
        form.addRow(QLabel("<b>Финансови данни</b>"))
        form.addRow("Причина:", self.reason_combo)
        form.addRow("Валута:", self.curr_layout)
        form.addRow("Начална дата:", self.date_start)
        form.addRow("Крайна дата:", self.date_stop)
        form.addRow("Общ оборот:", self.turnover_input)
        form.addRow("Общо Сторно:", self.storno_total_input)
        
        vat_grid = QHBoxLayout()
        vat_grid.addWidget(QLabel("ДДС А:"))
        vat_grid.addWidget(self.vat_a)
        vat_grid.addWidget(QLabel("ДДС Б:"))
        vat_grid.addWidget(self.vat_b)
        vat_grid.addWidget(QLabel("ДДС В:"))
        vat_grid.addWidget(self.vat_v)
        vat_grid.addWidget(QLabel("ДДС Г:"))
        vat_grid.addWidget(self.vat_g)
        form.addRow("Оборот по групи:", vat_grid)
        
        storno_grid = QHBoxLayout()
        storno_grid.addWidget(QLabel("А:"))
        storno_grid.addWidget(self.storno_a)
        storno_grid.addWidget(QLabel("Б:"))
        storno_grid.addWidget(self.storno_b)
        storno_grid.addWidget(QLabel("В:"))
        storno_grid.addWidget(self.storno_v)
        storno_grid.addWidget(QLabel("Г:"))
        storno_grid.addWidget(self.storno_g)
        form.addRow("Сторно по групи:", storno_grid)
        
        layout.addLayout(form)
        
        # Buttons
        btns = QHBoxLayout()
        gen_btn = QPushButton("Генерирай Протокол")
        gen_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Отказ")
        cancel_btn.clicked.connect(self.reject)
        btns.addWidget(gen_btn)
        btns.addWidget(cancel_btn)
        layout.addLayout(btns)
        
        # Pre-fill if exists
        if device_data:
            # device_data is usually a dict or object from DB
            from database import get_client_by_contract
            client = get_client_by_contract(device_data.get('contract_number', ''))
            if client:
                self.eik_input.setText(str(client.get('eik', '')))
                self.company_input.setText(str(client.get('company_name', '')))
                self.address_input.setText(str(client.get('address', '')))
                self.mol_input.setText(str(client.get('mol', '')))
            
            self.model_input.setText(str(device_data.get('model', '')))
            self.sn_input.setText(str(device_data.get('serial_number', '')))
            self.fm_input.setText(str(device_data.get('fiscal_memory', '')))
            self.bim_input.setText(str(device_data.get('bim_number', '')))
            self.fdrid_input.setText(str(device_data.get('fdrid', '')))
            self.obj_name_input.setText(str(device_data.get('object_name', '')))
            self.obj_addr_input.setText(str(device_data.get('object_address', '')))
            self.cert_expiry = device_data.get('certificate_expiry', None)
            
            # Pre-select manufacturer
            sn = str(device_data.get('serial_number', ''))
            if sn.startswith('DY') or sn.startswith('SY'):
                self.manu_combo.setCurrentText("Дейзи")
            elif sn.startswith('DT'):
                self.manu_combo.setCurrentText("Датекс")
            elif sn.startswith('ZK') or sn.startswith('TR') or sn.startswith('TE'):
                self.manu_combo.setCurrentText("Тремол")

    def get_data(self):
        return {
            "eik": self.eik_input.text(),
            "company_name": self.company_input.text(),
            "address": self.address_input.text(),
            "mol": self.mol_input.text(),
            "model": self.model_input.text(),
            "serial_number": self.sn_input.text(),
            "fiscal_memory": self.fm_input.text(),
            "bim_number": self.bim_input.text(),
            "fdrid": self.fdrid_input.text(),
            "manufacturer": self.manu_combo.currentText(),
            "certificate_expiry": getattr(self, 'cert_expiry', None),
            "object_name": self.obj_name_input.text(),
            "object_address": self.obj_addr_input.text(),
            "reason": self.reason_combo.currentText(),
            "currency": "BGN" if self.bgn_radio.isChecked() else "EUR",
            "date_start_fmt": self.date_start.date().toString('dd.MM.yyyy г.'),
            "date_stop_fmt": self.date_stop.date().toString('dd.MM.yyyy г.'),
            "turnover": self.turnover_input.text(),
            "storno_total": self.storno_total_input.text(),
            "vat_a": self.vat_a.text(),
            "vat_b": self.vat_b.text(),
            "vat_v": self.vat_v.text(),
            "vat_g": self.vat_g.text(),
            "storno_a": self.storno_a.text(),
            "storno_b": self.storno_b.text(),
            "storno_v": self.storno_v.text(),
            "storno_g": self.storno_g.text()
        }


class LoginDialog(QDialog):
    """Login dialog with attempt counting"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Вход в системата")
        self.attempts = 0
        self.max_attempts = 10
        self.user = None
        
        self.init_ui()
        
    def init_ui(self):
        # Allow resizing and set a generous default size
        self.setMinimumSize(500, 350)
        self.setSizeGripEnabled(True)
        
        self.setStyleSheet("""
            QDialog {
                background-color: #f5f5f5;
            }
            QLabel {
                font-family: 'Segoe UI', sans-serif;
                color: #333;
            }
            QLineEdit {
                padding: 12px;
                border: 1px solid #ccc;
                border-radius: 6px;
                font-size: 16px;
                background-color: white;
                min-height: 25px; 
            }
            QLineEdit:focus {
                border: 2px solid #3498db;
            }
            QPushButton {
                padding: 12px 24px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 15px;
                min-width: 100px;
                min-height: 25px;
            }
            QPushButton#btnLogin {
                background-color: #3498db;
                color: white;
                border: none;
            }
            QPushButton#btnLogin:hover {
                background-color: #2980b9;
            }
            QPushButton#btnExit {
                background-color: #e74c3c;
                color: white;
                border: none;
            }
            QPushButton#btnExit:hover {
                background-color: #c0392b;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(50, 50, 50, 50)
        layout.setSpacing(25)
        
        # Logo or Title with Icon
        header_layout = QVBoxLayout()
        
        title = QLabel("Вход в системата")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 28px; font-weight: bold; color: #2c3e50; margin-bottom: 5px;")
        header_layout.addWidget(title)
        
        subtitle = QLabel("Регистър на фискални устройства")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("font-size: 16px; color: #7f8c8d;")
        header_layout.addWidget(subtitle)
        
        layout.addLayout(header_layout)
        
        # Form Container
        form_container = QWidget()
        form_container.setStyleSheet("background-color: white; border-radius: 10px; border: 1px solid #ddd;")
        
        # Use simpler layout inside container
        form_layout = QVBoxLayout(form_container)
        form_layout.setContentsMargins(30, 30, 30, 30)
        form_layout.setSpacing(20)
        
        self.username = QLineEdit()
        self.username.setPlaceholderText("Потребителско име")
        
        self.password = QLineEdit()
        self.password.setPlaceholderText("Парола")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.returnPressed.connect(self.attempt_login)
        
        form_layout.addWidget(self.username)
        form_layout.addWidget(self.password)
        
        layout.addWidget(form_container)
        
        self.lbl_error = QLabel("")
        self.lbl_error.setStyleSheet("color: #e74c3c; font-size: 12px; font-weight: bold;")
        self.lbl_error.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_error)
        
        buttons = QHBoxLayout()
        buttons.setSpacing(15)
        
        btn_login = QPushButton("ВХОД")
        btn_login.setObjectName("btnLogin")
        btn_login.clicked.connect(self.attempt_login)
        btn_login.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_login.setDefault(True)
        btn_login.setAutoDefault(True)
        
        btn_exit = QPushButton("ИЗХОД")
        btn_exit.setObjectName("btnExit")
        btn_exit.clicked.connect(self.reject)
        btn_exit.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_exit.setAutoDefault(False)
        
        buttons.addWidget(btn_exit) # Exit left
        buttons.addWidget(btn_login) # Login right
        layout.addLayout(buttons)
        
        self.setLayout(layout)

    def attempt_login(self):
        username = self.username.text().strip()
        password = self.password.text().strip()
        
        if not username or not password:
            self.lbl_error.setText("Моля, попълнете всички полета.")
            self.username.setFocus() if not username else self.password.setFocus()
            return

        from database import get_user_by_username, log_action
        from auth import verify_password
        
        user_data = get_user_by_username(username)
        
        success = False
        if user_data:
            if verify_password(user_data['password_hash'], password):
                success = True
                self.user = user_data
        
        if success:
            log_action(self.user['id'], self.user['username'], "LOGIN", "Успешно влизане")
            QMessageBox.information(self, "Успешно влизане!", f"Добре дошли, {self.user.get('full_name', self.user.get('username'))}!")
            self.accept()
        else:
            self.attempts += 1
            remaining = self.max_attempts - self.attempts
            
            # Show warning message
            QMessageBox.warning(self, "Грешка при вход", f"Грешно потребителско име или парола!\nОстават {remaining} опита.")
            
            # Clear both fields and reset focus as requested
            self.username.clear()
            self.password.clear()
            self.lbl_error.setText(f"Грешно име или парола! Остават {remaining} опита.")
            self.username.setFocus()
            
            if remaining <= 0:
                QMessageBox.critical(self, "Грешка", "Превишен брой опити за вход! Програмата ще се затвори.")
                self.reject()

class EditUserDialog(QDialog):
    def __init__(self, user_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Редактиране на потребител")
        self.user_data = user_data
        self.setup_ui()
        
    def setup_ui(self):
        layout = QFormLayout(self)
        
        self.u_username = QLineEdit(self.user_data['username'])
        self.u_username.setReadOnly(True) # Cannot change username
        
        self.u_name = QLineEdit(self.user_data['full_name'])
        
        self.u_pass = QLineEdit()
        self.u_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.u_pass.setPlaceholderText("Оставете празно ако не променяте")
        
        self.u_role = QComboBox()
        self.u_role.addItems(["Потребител", "Администратор"])
        current_role = self.user_data.get('role', 'user')
        idx = 1 if current_role == 'admin' else 0
        self.u_role.setCurrentIndex(idx)
        
        # Prevent demoting vladpos
        if self.user_data['username'] == 'vladpos':
            self.u_role.setEnabled(False)
            
        layout.addRow("Потребителско име:", self.u_username)
        layout.addRow("Име и Фамилия:", self.u_name)
        layout.addRow("Нова парола:", self.u_pass)
        layout.addRow("Роля:", self.u_role)
        
        btns = QHBoxLayout()
        btn_save = QPushButton("Запази")
        btn_save.clicked.connect(self.save)
        btn_cancel = QPushButton("Отказ")
        btn_cancel.clicked.connect(self.reject)
        
        btns.addWidget(btn_save)
        btns.addWidget(btn_cancel)
        layout.addRow("", btns)
        
    def save(self):
        full_name = self.u_name.text().strip()
        password = self.u_pass.text().strip()
        role_text = self.u_role.currentText()
        role = "admin" if role_text == "Администратор" else "user"
        
        if not full_name:
            QMessageBox.warning(self, "Грешка", "Името е задължително!")
            return
            
        from database import update_user
        from auth import hash_password
        
        pwd_hash = hash_password(password) if password else None
        
        if update_user(self.user_data['id'], full_name, role, pwd_hash):
            QMessageBox.information(self, "Успех", "Потребителят е обновен!")
            self.accept()
        else:
            QMessageBox.critical(self, "Грешка", "Грешка при обновяване!")


class SettingsDialog(QDialog):
    """Settings dialog including Service Firm data and User Management"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки")
        self.resize(600, 500)
        
        # Get user from parent
        self.user = getattr(parent, 'current_user', None) if parent else None
        
        self.init_ui()
        self.load_settings()
        self.load_users()
        
    def init_ui(self):
        layout = QVBoxLayout()
        
        self.tabs = QTabWidget()
        
        # Tab 1: Service Firm Settings
        self.tab_service = QWidget()
        self.init_service_tab()
        self.tabs.addTab(self.tab_service, "Сервизна фирма")
        
        # Tab 2: Technician Settings
        self.tab_tech = QWidget()
        self.init_tech_tab()
        self.tabs.addTab(self.tab_tech, "Сервизен техник")
        
        # Tab 3: Configuration (Paths etc)
        self.tab_config = QWidget()
        self.init_config_tab()
        self.tabs.addTab(self.tab_config, "Конфигурация")

        # Tab 4: Users (New)
        if self.user and self.user.get('role') == 'admin':
            self.tab_users = QWidget()
            self.init_users_tab()
            self.tabs.addTab(self.tab_users, "Потребители")
            
            # Tab 5: Database Administration
            self.tab_db = QWidget()
            self.init_db_admin_tab()
            self.tabs.addTab(self.tab_db, "База Данни")

        # Tab 6: Network (New)
        self.tab_network = QWidget()
        self.init_network_tab()
        self.tabs.addTab(self.tab_network, "Мрежа")

        # Tab 7: Automation & Email (New)
        self.tab_auto = QWidget()
        self.init_automation_tab()
        self.tabs.addTab(self.tab_auto, "⚙️ Автоматизация")
        
        # Tab 8: Cloud Backup (New)
        self.tab_cloud = QWidget()
        self.init_cloud_backup_tab()
        self.tabs.addTab(self.tab_cloud, "☁️ Архив")

        # Phase 14 Tabs
        self.tab_branding = QWidget()
        self.init_branding_tab()
        self.tabs.addTab(self.tab_branding, "🎨 Брандиране")

        self.tab_templates = QWidget()
        self.init_templates_tab()
        self.tabs.addTab(self.tab_templates, "📝 Шаблони")

        self.tab_comm = QWidget()
        self.init_comm_tab()
        self.tabs.addTab(self.tab_comm, "💬 Комуникация")

        self.tab_dashboard = QWidget()
        self.init_dashboard_tab()
        self.tabs.addTab(self.tab_dashboard, "📊 Дашборд")
        
        layout.addWidget(self.tabs)
        
        # Buttons
        buttons = QHBoxLayout()
        btn_save = QPushButton("Запази настройките")
        btn_save.clicked.connect(self.save_settings)
        btn_close = QPushButton("Затвори")
        btn_close.clicked.connect(self.reject)
        
        buttons.addStretch()
        buttons.addWidget(btn_save)
        buttons.addWidget(btn_close)
        
        layout.addLayout(buttons)
        self.setLayout(layout)
        
    def init_service_tab(self):
        layout = QFormLayout()
        
        self.s_name = QLineEdit()
        self.s_eik = QLineEdit()
        self.s_vat = QLineEdit()
        self.s_city = QLineEdit()
        self.s_post = QLineEdit()
        self.s_addr = QLineEdit()
        self.s_mol = QLineEdit()
        self.s_phone1 = QLineEdit()
        self.s_phone2 = QLineEdit()
        
        # Check Service EIK Button (also checks VAT via VIES)
        check_btn = QPushButton("Провери ЕИК и ДДС")
        check_btn.clicked.connect(self.check_service_eik)
        
        self.s_vat_reg = QCheckBox("ДДС Регистриран")
        
        layout.addRow("ЕИК:", self.s_eik)
        layout.addRow("", check_btn)
        layout.addRow("Име на фирма:", self.s_name)
        layout.addRow("ЗДДС рег. номер:", self.s_vat)
        layout.addRow("", self.s_vat_reg)
        
        layout.addRow("Град:", self.s_city)
        layout.addRow("Пощ. код:", self.s_post)
        layout.addRow("Адрес:", self.s_addr)
        layout.addRow("МОЛ:", self.s_mol)
        layout.addRow("Телефон 1:", self.s_phone1)
        layout.addRow("Телефон 2:", self.s_phone2)
        
        self.tab_service.setLayout(layout)

    def check_service_eik(self):
        eik = self.s_eik.text().strip()
        if not eik:
            QMessageBox.warning(self, "Грешка", "Моля, въведете ЕИК!")
            return
            
        from vat_check import check_vat
        
        try:
            data = check_vat(eik)
            if data:
                self.s_name.setText(data.get('name', ''))
                self.s_addr.setText(data.get('address', ''))
                self.s_mol.setText(data.get('mol', ''))
                self.s_city.setText(data.get('city', ''))
                self.s_post.setText(data.get('postal_code', ''))
                
                if data.get('valid'):
                    # Construct VAT number (BG + EIK)
                    self.s_vat.setText(f"BG{eik}")
                    self.s_vat_reg.setChecked(True)
                    QMessageBox.information(self, "Успех", "Данните са заредени успешно!\nФирмата е регистрирана по ДДС.")
                else:
                    self.s_vat_reg.setChecked(False)
                    QMessageBox.information(self, "Успех", "Данните са заредени успешно!\nФирмата НЕ е регистрирана по ДДС.")
            else:
                QMessageBox.warning(self, "Грешка", "Не са намерени данни за този ЕИК.")
        except Exception as e:
            QMessageBox.critical(self, "Грешка", f"Грешка при проверка:\n{str(e)}")

    def init_tech_tab(self):
        layout = QFormLayout()
        
        # Restoring original variable names where possible for clarity/compatibility
        self.s_tech_f = QLineEdit() # Name
        self.s_tech_m = QLineEdit() # Middle
        self.s_tech_l = QLineEdit() # Last
        self.s_tech_egn = QLineEdit()
        
        layout.addRow("Име:", self.s_tech_f)
        layout.addRow("Презиме:", self.s_tech_m)
        layout.addRow("Фамилия:", self.s_tech_l)
        layout.addRow("ЕГН на техника:", self.s_tech_egn)
        
        label_info = QLabel("Данните са необходими за генериране на XML към НАП.")
        label_info.setStyleSheet("color: gray; font-style: italic;")
        layout.addRow(label_info)
        
        self.tab_tech.setLayout(layout)


        
    def init_config_tab(self):
        layout = QFormLayout()
        
        self.c_db_path = QLineEdit()
        self.c_db_path.setReadOnly(True)
        from database import DB_PATH
        self.c_db_path.setText(DB_PATH)
        
        layout.addRow("Път до база данни:", self.c_db_path)
        
        self.c_autorun = QCheckBox("Стартиране с Windows (Autorun)")
        layout.addRow("", self.c_autorun)
        
        self.tab_config.setLayout(layout)

    def init_branding_tab(self):
        layout = QFormLayout()
        
        self.br_app_title = QLineEdit()
        self.br_app_title.setPlaceholderText("Система за Договори")
        
        self.br_splash_path = QLineEdit()
        self.br_splash_path.setReadOnly(True)
        btn_browse = QPushButton("Избери снимка")
        btn_browse.clicked.connect(self.browse_splash_image)
        
        self.br_clear_splash = QPushButton("Изчисти (По подразбиране)")
        self.br_clear_splash.clicked.connect(lambda: self.br_splash_path.clear())
        
        h_layout = QHBoxLayout()
        h_layout.addWidget(self.br_splash_path)
        h_layout.addWidget(btn_browse)
        
        layout.addRow("Заглавие на Програмата:", self.br_app_title)
        layout.addRow("Начална снимка (Splash):", h_layout)
        layout.addRow("", self.br_clear_splash)
        
        info = QLabel("Снимката трябва да е в формат JPG или PNG. Препоръчителен размер: 700x500.")
        info.setStyleSheet("color: gray; font-style: italic;")
        layout.addRow(info)
        
        self.tab_branding.setLayout(layout)

    def browse_splash_image(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Изберете снимка", "", "Images (*.png *.jpg *.jpeg)")
        if file_path:
            self.br_splash_path.setText(file_path)

    def init_templates_tab(self):
        layout = QVBoxLayout()
        
        label = QLabel("Списък на шаблоните в системата (DOCX файлове):")
        layout.addWidget(label)
        
        self.templates_list = QListWidget()
        self.refresh_templates_list()
        layout.addWidget(self.templates_list)
        
        btn_layout = QHBoxLayout()
        btn_edit = QPushButton("✏️ Редактирай в Word")
        btn_edit.clicked.connect(self.edit_selected_template)
        btn_refresh = QPushButton("🔄 Обнови списъка")
        btn_refresh.clicked.connect(self.refresh_templates_list)
        
        btn_layout.addWidget(btn_edit)
        btn_layout.addWidget(btn_refresh)
        layout.addLayout(btn_layout)
        
        self.tab_templates.setLayout(layout)

    def refresh_templates_list(self):
        self.templates_list.clear()
        from path_utils import get_app_root
        resources_dir = os.path.join(get_app_root(), "resources")
        if os.path.exists(resources_dir):
            files = [f for f in os.listdir(resources_dir) if f.endswith(".docx")]
            self.templates_list.addItems(files)

    def edit_selected_template(self):
        item = self.templates_list.currentItem()
        if not item:
            QMessageBox.warning(self, "Внимание", "Моля, изберете шаблон!")
            return
            
        from path_utils import get_app_root
        file_path = os.path.join(get_app_root(), "resources", item.text())
        if os.path.exists(file_path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))
        else:
            QMessageBox.critical(self, "Грешка", "Файлът не е намерен!")

    def init_comm_tab(self):
        layout = QVBoxLayout()
        
        # Email settings
        email_grp = QGroupBox("Шаблон за Имейл")
        e_form = QFormLayout()
        self.comm_email_subject = QLineEdit()
        self.comm_email_body = QTextEdit()
        e_form.addRow("Тема:", self.comm_email_subject)
        e_form.addRow("Текст:", self.comm_email_body)
        email_grp.setLayout(e_form)
        layout.addWidget(email_grp)
        
        # Viber settings
        viber_grp = QGroupBox("Viber Известяване (Beta)")
        v_form = QFormLayout()
        self.comm_viber_token = QLineEdit()
        self.comm_viber_token.setEchoMode(QLineEdit.EchoMode.Password)
        self.comm_viber_receiver = QLineEdit()
        self.comm_viber_receiver.setPlaceholderText("Receiver ID (User ID)")
        self.comm_viber_template = QTextEdit()
        
        v_form.addRow("Viber Bot Token:", self.comm_viber_token)
        v_form.addRow("Получател ID:", self.comm_viber_receiver)
        
        btn_test_viber = QPushButton("⚡ Тествай Viber връзката")
        btn_test_viber.clicked.connect(self.test_viber_connection)
        v_form.addRow("", btn_test_viber)
        
        v_form.addRow("Шаблон съобщение:", self.comm_viber_template)
        
        viber_grp.setLayout(v_form)
        layout.addWidget(viber_grp)
        
        placeholders = QLabel("Достъпни променливи: {client}, {contract_num}, {expiry_date}, {model}")
        placeholders.setStyleSheet("color: blue; font-weight: bold;")
        layout.addWidget(placeholders)
        
        self.tab_comm.setLayout(layout)

    def test_viber_connection(self):
        token = self.comm_viber_token.text().strip()
        receiver = self.comm_viber_receiver.text().strip()
        
        if not token:
            QMessageBox.warning(self, "Внимание", "Моля, въведете Viber Bot Token!")
            return
            
        from viber_manager import validate_viber_token, send_viber_message
        
        # 1. Validate Token
        if validate_viber_token(token):
            if receiver:
                # 2. Try to send a test message if receiver is present
                ok, msg = send_viber_message(token, receiver, "🔔 Тестово съобщение от Contracts App! Вашата Viber интеграция работи успешно.")
                if ok:
                    QMessageBox.information(self, "Viber Тест", "Връзката е успешна и е изпратено тестово съобщение!")
                else:
                    QMessageBox.warning(self, "Viber Тест", f"Токенът е валиден, но съобщението не беше изпратено:\n{msg}")
            else:
                QMessageBox.information(self, "Viber Тест", "Viber Bot Token-ът е валиден!")
        else:
            QMessageBox.critical(self, "Viber Тест", "Невалиден Viber Bot Token или липса на връзка с API сървъра.")

    def init_dashboard_tab(self):
        layout = QVBoxLayout()
        grp = QGroupBox("Видимост на статистиките")
        vbox = QVBoxLayout()
        
        self.dash_show_total = QCheckBox("Общо устройства")
        self.dash_show_expiring = QCheckBox("Изтичащи договори")
        self.dash_show_active = QCheckBox("Активни клиенти")
        self.dash_show_recent = QCheckBox("Последно добавени")
        
        vbox.addWidget(self.dash_show_total)
        vbox.addWidget(self.dash_show_expiring)
        vbox.addWidget(self.dash_show_active)
        vbox.addWidget(self.dash_show_recent)
        
        grp.setLayout(vbox)
        layout.addWidget(grp)
        layout.addStretch()
        self.tab_dashboard.setLayout(layout)

    def init_cloud_backup_tab(self):
        layout = QFormLayout()
        
        self.cb_gdrive = QCheckBox("Активирай Google Drive архив")
        self.cb_dropbox = QCheckBox("Активирай Dropbox архив")
        self.cb_dropbox_token = QLineEdit()
        self.cb_dropbox_token.setEchoMode(QLineEdit.EchoMode.Password)
        self.cb_dropbox_token.setPlaceholderText("Въведете Dropbox Access Token тук...")
        
        self.cb_folder_id = QLineEdit()
        self.cb_folder_id.setPlaceholderText("ID на папка в Google Drive...")
        
        self.cb_interval = QComboBox()
        self.cb_interval.addItems(["При затваряне", "Всеки ден", "Всяка седмица"])
        
        layout.addRow("Google Drive:", self.cb_gdrive)
        layout.addRow("Google Folder ID:", self.cb_folder_id)
        layout.addRow("Dropbox:", self.cb_dropbox)
        layout.addRow("Dropbox Token:", self.cb_dropbox_token)
        layout.addRow("Интервал:", self.cb_interval)
        
        btn_manual_backup = QPushButton("☁️ Извърши архив сега")
        btn_manual_backup.clicked.connect(self.trigger_manual_backup)
        layout.addRow("", btn_manual_backup)
        
        self.tab_cloud.setLayout(layout)

    def trigger_manual_backup(self):
        from backup_manager import run_cloud_backup
        run_cloud_backup()
        QMessageBox.information(self, "Облачен архив", "Архивирането беше стартирано успешно!")

    def init_users_tab(self):
        layout = QVBoxLayout()
        
        # List of users
        self.table_users = QTableWidget()
        self.table_users.setColumnCount(4)
        self.table_users.setHorizontalHeaderLabels(["ID", "Потребителско име", "Име", "Роля"])
        self.table_users.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table_users.setSortingEnabled(True)
        self.table_users.horizontalHeader().setStretchLastSection(True)
        
        layout.addWidget(QLabel("Списък потребители:"))
        layout.addWidget(self.table_users)
        
        # Add User Form
        grp_add = QWidget()
        lay_add = QFormLayout()
        
        self.u_username = QLineEdit()
        self.u_name = QLineEdit()
        self.u_pass = QLineEdit()
        self.u_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.u_role = QComboBox()
        self.u_role.addItems(["Потребител", "Администратор"])
        
        btn_add_user = QPushButton("Добави потребител")
        btn_add_user.clicked.connect(self.add_new_user)
        
        lay_add.addRow("Потребителско име:", self.u_username)
        lay_add.addRow("Име и Фамилия:", self.u_name)
        lay_add.addRow("Парола:", self.u_pass)
        lay_add.addRow("Роля:", self.u_role)
        lay_add.addRow("", btn_add_user)
        
        grp_add.setLayout(lay_add)
        layout.addWidget(grp_add)
        
        # Edit button
        btn_edit_user = QPushButton("Редактирай избран потребител")
        btn_edit_user.clicked.connect(self.edit_selected_user)
        layout.addWidget(btn_edit_user)
        
        # Delete button
        btn_del_user = QPushButton("Изтрий избран потребител")
        btn_del_user.setStyleSheet("background-color: #ffcccc;")
        btn_del_user.clicked.connect(self.delete_selected_user)
        layout.addWidget(btn_del_user)
        
        # Permissions check
        is_super_admin = (self.user and self.user.get('username') == 'vladpos')
        if not is_super_admin:
            grp_add.setVisible(False)
            btn_edit_user.setVisible(False)
            btn_del_user.setVisible(False)
            layout.addWidget(QLabel("Управлението на потребители е ограничено само за главния администратор."))
        
        self.tab_users.setLayout(layout)

    def load_users(self):
        if not hasattr(self, 'table_users'): return
        
        from database import get_all_users
        users = get_all_users()
        
        self.table_users.setRowCount(0)
        for u in users:
            row = self.table_users.rowCount()
            self.table_users.insertRow(row)
            self.table_users.setItem(row, 0, QTableWidgetItem(str(u['id'])))
            self.table_users.setItem(row, 1, QTableWidgetItem(u['username']))
            self.table_users.setItem(row, 2, QTableWidgetItem(u['full_name']))
            
            role_display = "Администратор" if u.get('role') == 'admin' else "Потребител"
            self.table_users.setItem(row, 3, QTableWidgetItem(role_display))

    def add_new_user(self):
        username = self.u_username.text().strip()
        name = self.u_name.text().strip()
        password = self.u_pass.text().strip()
        
        if not username or not name or not password:
            QMessageBox.warning(self, "Грешка", "Всички полета са задължителни!")
            return
            
        from auth import hash_password
        from database import add_user
        
        pwd_hash = hash_password(password)
        role = "admin" if self.u_role.currentText() == "Администратор" else "user"
        
        if add_user(username, pwd_hash, name, role):
            QMessageBox.information(self, "Успех", "Потребителят е добавен!")
            self.u_username.clear()
            self.u_name.clear()
            self.u_pass.clear()
            self.load_users()
        else:
            QMessageBox.critical(self, "Грешка", "Грешка при добавяне (може би потребителското име вече съществува?)")

    def edit_selected_user(self):
        selected = self.table_users.selectionModel().selectedRows()
        if not selected:
            QMessageBox.warning(self, "Внимание", "Моля, изберете потребител!")
            return
            
        row = selected[0].row()
        username = self.table_users.item(row, 1).text()
        
        from database import get_user_by_username
        user_data = get_user_by_username(username)
        
        if not user_data: 
            return
        
        dialog = EditUserDialog(user_data, self)
        if dialog.exec():
            self.load_users()

    def delete_selected_user(self):
        selected = self.table_users.selectionModel().selectedRows()
        if not selected:
            return
            
        row = selected[0].row()
        uid = int(self.table_users.item(row, 0).text())
        username = self.table_users.item(row, 1).text()
        
        if username == 'vladpos':
            QMessageBox.warning(self, "Забранено", "Не можете да изтриете главния администратор!")
            return
            
        reply = QMessageBox.question(self, "Потвърждение", f"Изтриване на потребител {username}?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            from database import delete_user
            delete_user(uid)
            self.load_users()


    def load_settings(self):
        from database import get_setting
        
        # Load Synchronized Settings from Database
        self.s_name.setText(get_setting('name', ''))
        self.s_eik.setText(get_setting('eik', ''))
        self.s_vat.setText(get_setting('vat', ''))
        self.s_city.setText(get_setting('city', ''))
        self.s_post.setText(get_setting('post', ''))
        self.s_addr.setText(get_setting('address', ''))
        self.s_mol.setText(get_setting('mol', ''))
        self.s_phone1.setText(get_setting('phone1', ''))
        self.s_phone2.setText(get_setting('phone2', ''))
        self.s_vat_reg.setChecked(get_setting('vat_registered', 'False') == 'True')
        
        self.s_tech_f.setText(get_setting('tech_f', ''))
        self.s_tech_m.setText(get_setting('tech_m', ''))
        self.s_tech_l.setText(get_setting('tech_l', ''))
        self.s_tech_egn.setText(get_setting('tech_egn', ''))

        # Load Local Settings from JSON
        from path_utils import get_app_root
        settings_path = os.path.join(get_app_root(), "data", "settings.json")
        if os.path.exists(settings_path):
            import json
            try:
                with open(settings_path, 'r', encoding='utf-8') as f:
                    local_data = json.load(f)
                    self.server_ip.setText(local_data.get('server_url', ''))
                    self.c_autorun.setChecked(local_data.get('autorun', False))
                    
                    # Automation settings
                    auto_data = local_data.get('automation', {})
                    self.smtp_server.setText(auto_data.get('smtp_server', ''))
                    self.smtp_port.setValue(auto_data.get('smtp_port', 587))
                    self.smtp_user.setText(auto_data.get('smtp_user', ''))
                    self.smtp_password.setText(auto_data.get('smtp_password', ''))
                    self.smtp_tls.setChecked(auto_data.get('smtp_tls', True))
                    self.report_recipient.setText(auto_data.get('report_recipient', ''))
                    self.report_day.setValue(auto_data.get('report_day', 10))
                    self.auto_reports_enabled.setChecked(auto_data.get('auto_reports_enabled', False))
                    
                    self.email_7d = auto_data.get('email_7d_ahead', True)
                    self.email_14d = auto_data.get('email_14d_ahead', True)
                    self.email_30d = auto_data.get('email_30d_ahead', True)
                    
                    cloud_data = local_data.get('backup', {})
                    self.cb_interval.setCurrentText(cloud_data.get('interval', 'При затваряне'))
                    self.cb_folder_id.setText(cloud_data.get('google_folder_id', ''))

                    # Branding Settings
                    branding = local_data.get('branding', {})
                    self.br_app_title.setText(branding.get('app_title', ''))
                    self.br_splash_path.setText(branding.get('splash_path', ''))

                    # Communication Settings
                    comm = local_data.get('communication', {})
                    self.comm_email_subject.setText(comm.get('email_subject', ''))
                    self.comm_email_body.setPlainText(comm.get('email_body', ''))
                    self.comm_viber_token.setText(comm.get('viber_token', ''))
                    self.comm_viber_receiver.setText(comm.get('viber_receiver', ''))
                    self.comm_viber_template.setPlainText(comm.get('viber_template', ''))

                    # Dashboard Settings
                    dash = local_data.get('dashboard', {'show_total': True, 'show_expiring': True, 'show_active': True, 'show_recent': True})
                    self.dash_show_total.setChecked(dash.get('show_total', True))
                    self.dash_show_expiring.setChecked(dash.get('show_expiring', True))
                    self.dash_show_active.setChecked(dash.get('show_active', True))
                    self.dash_show_recent.setChecked(dash.get('show_recent', True))

            except Exception as e:
                print(f"Error loading local settings: {e}")

    def save_settings(self):
        from database import set_setting
        
        try:
            # 1. Save Synchronized Settings to Database
            set_setting('name', self.s_name.text().strip())
            set_setting('eik', self.s_eik.text().strip())
            set_setting('vat', self.s_vat.text().strip())
            set_setting('city', self.s_city.text().strip())
            set_setting('post', self.s_post.text().strip())
            set_setting('address', self.s_addr.text().strip())
            set_setting('mol', self.s_mol.text().strip())
            set_setting('phone1', self.s_phone1.text().strip())
            set_setting('phone2', self.s_phone2.text().strip())
            set_setting('vat_registered', str(self.s_vat_reg.isChecked()))
            
            set_setting('tech_f', self.s_tech_f.text().strip())
            set_setting('tech_m', self.s_tech_m.text().strip())
            set_setting('tech_l', self.s_tech_l.text().strip())
            set_setting('tech_egn', self.s_tech_egn.text().strip())

            # 2. Save Local Settings to JSON
            from path_utils import get_app_root
            data_dir = os.path.join(get_app_root(), "data")
            os.makedirs(data_dir, exist_ok=True)
            
            # Read existing to preserve keys we don't manage here (like last_sync_time)
            local_data = {}
            settings_path = os.path.join(data_dir, "settings.json")
            if os.path.exists(settings_path):
                import json
                try:
                    with open(settings_path, 'r', encoding='utf-8') as f:
                        local_data = json.load(f)
                except: pass
            
            mode = "server" if self.radio_server.isChecked() else "client"
            url = self.server_ip.text().strip()
            autorun = self.c_autorun.isChecked()
            
            local_data['server_url'] = url
            local_data['mode'] = mode
            local_data['autorun'] = autorun # Ensure autorun is saved
            
            # Save Cloud Backup Settings
            cloud_data = local_data.get('backup', {})
            cloud_data['google_drive_enabled'] = self.cb_gdrive.isChecked()
            cloud_data['dropbox_enabled'] = self.cb_dropbox.isChecked()
            cloud_data['dropbox_token'] = self.cb_dropbox_token.text().strip()
            cloud_data['google_folder_id'] = self.cb_folder_id.text().strip()
            cloud_data['interval'] = self.cb_interval.currentText()
            local_data['backup'] = cloud_data

            # Save Communication Settings
            comm_data = local_data.get('communication', {})
            comm_data['email_subject'] = self.comm_email_subject.text().strip()
            comm_data['email_body'] = self.comm_email_body.toPlainText().strip()
            comm_data['viber_token'] = self.comm_viber_token.text().strip()
            comm_data['viber_receiver'] = self.comm_viber_receiver.text().strip()
            comm_data['viber_template'] = self.comm_viber_template.toPlainText().strip()
            local_data['communication'] = comm_data

            # Save Branding Settings
            branding_data = local_data.get('branding', {})
            branding_data['app_title'] = self.br_app_title.text().strip()
            branding_data['splash_path'] = self.br_splash_path.text().strip()
            local_data['branding'] = branding_data

            # Save Dashboard Settings
            dash_data = local_data.get('dashboard', {})
            dash_data['show_total'] = self.dash_show_total.isChecked()
            dash_data['show_expiring'] = self.dash_show_expiring.isChecked()
            dash_data['show_active'] = self.dash_show_active.isChecked()
            dash_data['show_recent'] = self.dash_show_recent.isChecked()
            local_data['dashboard'] = dash_data

            # Save Automation & Email Settings
            auto_data = {
                'smtp_server': self.smtp_server.text().strip(),
                'smtp_port': self.smtp_port.value(),
                'smtp_user': self.smtp_user.text().strip(),
                'smtp_password': self.smtp_password.text().strip(),
                'smtp_tls': self.smtp_tls.isChecked(),
                'report_recipient': self.report_recipient.text().strip(),
                'report_day': self.report_day.value(),
                'auto_reports_enabled': self.auto_reports_enabled.isChecked(),
                'email_7d_ahead': getattr(self, 'email_7d', True),
                'email_14d_ahead': getattr(self, 'email_14d', True),
                'email_30d_ahead': getattr(self, 'email_30d', True)
            }
            local_data['automation'] = auto_data
            
            # If autorun changed, update registry
            if local_data.get('autorun') != autorun:
                from main import set_autorun
                set_autorun(autorun)
                local_data['autorun'] = autorun

            import json
            with open(settings_path, 'w', encoding='utf-8') as f:
                json.dump(local_data, f, ensure_ascii=False, indent=2)
            
            # Trigger sync manager update
            from sync_manager import SyncManager
            temp = SyncManager() 
            temp.save_settings(url, mode)
            
            QMessageBox.information(self, "Успех", "Настройките са запазени!\nЗа да влязат в сила новите мрежови настройки, моля рестартирайте приложението.")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Грешка", f"Грешка при запис:\n{e}")

    def send_test_email(self):
        """Send a test email to verify SMTP configuration"""
        smtp_cfg = {
            'server': self.smtp_server.text().strip(),
            'port': self.smtp_port.value(),
            'user': self.smtp_user.text().strip(),
            'password': self.smtp_password.text().strip(),
            'use_tls': self.smtp_tls.isChecked()
        }
        recipient = self.report_recipient.text().strip()
        
        if not smtp_cfg['server'] or not smtp_cfg['user'] or not recipient:
            QMessageBox.warning(self, "Внимание", "Моля попълнете SMTP сървър, потребител и получател!")
            return
            
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import Qt
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        
        try:
            subject = "Тестово съобщение: Contracts App"
            body = "Здравейте,\n\nТова е служебно съобщение за проверка на SMTP настройките в приложението за договори.\nКонфигурацията работи успешно!"
            
            if send_email_with_attachment(smtp_cfg, recipient, subject, body):
                QMessageBox.information(self, "Успех", "Тестовият имейл бе изпратен успешно!")
            else:
                QMessageBox.critical(self, "Грешка", "Неуспешно изпращане. Проверете сървъра, порта и паролата (App Password).")
        except Exception as e:
            QMessageBox.critical(self, "Грешка", f"Възникна системна грешка: {e}")
        finally:
            QApplication.restoreOverrideCursor()

    def init_db_admin_tab(self):
        """Database Administration tab for restore and reset"""
        main_layout = QVBoxLayout()
        
        # Restore Section
        restore_group = QWidget()
        restore_layout = QVBoxLayout()
        restore_group.setLayout(restore_layout)
        
        label_restore = QLabel("<b>Възстановяване от Backup</b>")
        restore_layout.addWidget(label_restore)
        
        row_file = QHBoxLayout()
        self.restore_path_label = QLineEdit()
        self.restore_path_label.setPlaceholderText("Изберете .zip файл...")
        self.restore_path_label.setReadOnly(True)
        btn_browse = QPushButton("📁 Избери файл")
        btn_browse.clicked.connect(self.browse_backup)
        row_file.addWidget(self.restore_path_label)
        row_file.addWidget(btn_browse)
        restore_layout.addLayout(row_file)
        
        btn_restore = QPushButton("✅ Възстанови базата")
        btn_restore.setStyleSheet("background-color: #28a745; color: white; font-weight: bold; padding: 5px;")
        btn_restore.clicked.connect(self.run_restore)
        restore_layout.addWidget(btn_restore)
        
        main_layout.addWidget(restore_group)
        main_layout.addSpacing(20)
        
        # Reset Section (Super Admin only)
        if self.user and self.user.get('username') == 'vladpos':
            reset_group = QWidget()
            reset_group.setObjectName("dangerZone")
            reset_group.setStyleSheet("QWidget#dangerZone { background-color: #fff5f5; border: 2px solid #ff4d4d; border-radius: 5px; padding: 10px; }")
            reset_layout = QVBoxLayout()
            reset_group.setLayout(reset_layout)
            
            label_reset = QLabel("<b>⚠️ КРИТИЧНО: Изчистване на базата</b>")
            label_reset.setStyleSheet("color: #d73a49; font-size: 14px;")
            reset_layout.addWidget(label_reset)
            
            txt_reset = QLabel("Това ще изтрие всички договори, устройства и клиенти! Супер администраторът 'vladpos' ще бъде съхранен автоматично.")
            txt_reset.setWordWrap(True)
            reset_layout.addWidget(txt_reset)
            
            self.confirm_reset_check = QCheckBox("Разбирам последствията и искам да изтрия базата")
            reset_layout.addWidget(self.confirm_reset_check)
            
            btn_reset = QPushButton("🗑️ ИЗТРИЙ ЦЯЛАТА БАЗА ДАННИ")
            btn_reset.setStyleSheet("background-color: #dc3545; color: white; font-weight: bold; padding: 8px;")
            btn_reset.clicked.connect(self.run_reset)
            reset_layout.addWidget(btn_reset)
            
            main_layout.addWidget(reset_group)
        
        main_layout.addStretch()
        self.tab_db.setLayout(main_layout)

    def browse_backup(self):
        """Browse for a backup ZIP file"""
        from path_utils import get_app_root
        backups_dir = os.path.join(get_app_root(), "backups")
        if not os.path.exists(backups_dir):
            backups_dir = os.getcwd()
            
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Изберете бекъп файл", backups_dir, "Backup files (*.zip)"
        )
        if file_path:
            self.restore_path_label.setText(file_path)

    def run_restore(self):
        """Restore DB from backup"""
        path = self.restore_path_label.text()
        if not path:
            QMessageBox.warning(self, "Грешка", "Моля, изберете файл първо!")
            return
            
        confirm = QMessageBox.question(
            self, "Потвърждение",
            "ВНИМАНИЕ: Сегашните данни ще бъдат заменени с тези от архива!\nСигурни ли сте?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if confirm == QMessageBox.StandardButton.Yes:
            from database import restore_database_from_backup
            success, message = restore_database_from_backup(path)
            
            if success:
                QMessageBox.information(self, "Успех", message + "\nПриложението ще се рестартира сега.")
                # Force restart
                import os
                import sys
                os.execl(sys.executable, sys.executable, *sys.argv)
            else:
                QMessageBox.critical(self, "Грешка", message)

    def run_reset(self):
        """Clear the database"""
        if not self.confirm_reset_check.isChecked():
            QMessageBox.warning(self, "Внимание", "Моля, потвърдете че разбирате последствията чрез отметката!")
            return
            
        confirm = QMessageBox.critical(
            self, "ПОСЛЕДНО ПОТВЪРЖДЕНИЕ",
            "АБСОЛЮТНО СИГУРНИ ЛИ СТЕ?\nВсички данни ще бъдат изтрити невъзвратимо!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if confirm == QMessageBox.StandardButton.Yes:
            from database import reset_database
            success, message = reset_database()
            
            if success:
                QMessageBox.information(self, "Успех", message + "\nПриложението ще се рестартира.")
                # Force restart
                import os
                import sys
                os.execl(sys.executable, sys.executable, *sys.argv)
            else:
                QMessageBox.critical(self, "Грешка", message)

    def init_network_tab(self):
        """Initialize Network/Sync settings tab"""
        layout = QVBoxLayout()
        
        # Load existing sync settings
        self.sync_mode_group = QGroupBox("Режим на работа")
        vbox = QVBoxLayout()
        
        from sync_manager import SyncManager
        # We need to instantiate temporarily to load settings
        temp_manager = SyncManager()
        current_server = temp_manager.server_url
        current_mode = temp_manager.mode
        
        self.radio_client = QCheckBox("Клиентски режим (Работна станция)")
        self.radio_client.setChecked(current_mode == "client")
        self.radio_client.toggled.connect(self.on_mode_toggled)
        
        self.radio_server = QCheckBox("Сървърен режим (Главен компютър)")
        self.radio_server.setChecked(current_mode == "server")
        self.radio_server.toggled.connect(self.on_mode_toggled)
        
        vbox.addWidget(self.radio_client)
        vbox.addWidget(self.radio_server)
        self.sync_mode_group.setLayout(vbox)
        
        # Server Config
        self.server_config_group = QGroupBox("Настройки за връзка")
        form = QFormLayout()
        
        self.server_ip = QLineEdit()
        self.server_ip.setText(current_server)
        self.server_ip.setPlaceholderText("http://192.168.1.100:8000")
        
        btn_test = QPushButton("Тест на връзката")
        btn_test.clicked.connect(self.test_connection)
        
        self.my_ip_label = QLabel("Вашият IP адрес: ...")
        self.get_local_ip()
        
        form.addRow("Адрес на сървъра:", self.server_ip)
        form.addRow("", btn_test)
        form.addRow("", self.my_ip_label)
        
        self.server_config_group.setLayout(form)
        
        # Initial state
        self.server_config_group.setEnabled(current_mode == "client")
        self.my_ip_label.setVisible(current_mode == "server")
        
        layout.addWidget(self.sync_mode_group)
        layout.addWidget(self.server_config_group)
        layout.addStretch()
        self.tab_network.setLayout(layout)

    def init_automation_tab(self):
        """Initialize Automation & Email settings tab"""
        layout = QVBoxLayout()
        
        # Email SMTP Group
        email_group = QGroupBox("SMTP Конфигурация (за изпращане на справки)")
        email_form = QFormLayout()
        
        self.smtp_server = QLineEdit()
        self.smtp_server.setPlaceholderText("напр. smtp.gmail.com")
        
        self.smtp_port = QSpinBox()
        self.smtp_port.setRange(1, 65535)
        self.smtp_port.setValue(587)
        
        self.smtp_user = QLineEdit()
        self.smtp_user.setPlaceholderText("vladpos@gmail.com")
        
        self.smtp_password = QLineEdit()
        self.smtp_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.smtp_password.setPlaceholderText("App Password")
        
        self.smtp_tls = QCheckBox("Използвай TLS (STARTTLS)")
        self.smtp_tls.setChecked(True)
        
        email_form.addRow("SMTP Сървър:", self.smtp_server)
        email_form.addRow("Порт:", self.smtp_port)
        email_form.addRow("Потребител (Email):", self.smtp_user)
        email_form.addRow("Парола / App Pass:", self.smtp_password)
        email_form.addRow("", self.smtp_tls)
        
        email_group.setLayout(email_form)
        layout.addWidget(email_group)
        
        # Reporting Group
        report_group = QGroupBox("Месечни Справки")
        report_form = QFormLayout()
        
        self.report_recipient = QLineEdit()
        self.report_recipient.setPlaceholderText("имейл на сервиза...")
        
        self.report_day = QSpinBox()
        self.report_day.setRange(1, 28)
        self.report_day.setValue(10)
        self.report_day.setSuffix(" -то число")
        
        self.auto_reports_enabled = QCheckBox("Активирай автоматично изпращане")
        
        btn_test_email = QPushButton("📧 Тестово изпращане")
        btn_test_email.clicked.connect(self.send_test_email)
        
        report_form.addRow("Получател на справката:", self.report_recipient)
        report_form.addRow("Ден за изпращане:", self.report_day)
        report_form.addRow("", self.auto_reports_enabled)
        report_form.addRow("", btn_test_email)
        
        report_group.setLayout(report_form)
        layout.addWidget(report_group)
        
        layout.addStretch()
        self.tab_auto.setLayout(layout)

    def on_mode_toggled(self):
        if self.sender() == self.radio_client and self.radio_client.isChecked():
            self.radio_server.setChecked(False)
            self.server_config_group.setEnabled(True)
            self.my_ip_label.setVisible(False)
        elif self.sender() == self.radio_server and self.radio_server.isChecked():
            self.radio_client.setChecked(False)
            self.server_config_group.setEnabled(False)
            self.my_ip_label.setVisible(True)
            self.get_local_ip()

    def get_local_ip(self):
        try:
            import socket
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            self.my_ip_label.setText(f"Вашият IP адрес за другите: http://{local_ip}:8000")
        except:
            self.my_ip_label.setText("Не може да се определи IP адрес")

    def test_connection(self):
        url = self.server_ip.text().strip()
        # Sanitize URL: remove trailing slash and /status
        if url.endswith("/"):
            url = url[:-1]
        if url.endswith("/status"):
            url = url[:-7]
            
        if not url: return
        
        try:
            import requests
            resp = requests.get(f"{url}/status", timeout=2)
            if resp.status_code == 200:
                QMessageBox.information(self, "Успех", "Връзката е успешна!\nСървърът е на линия.")
            else:
                QMessageBox.warning(self, "Грешка", f"Сървърът върна код: {resp.status_code}")
        except Exception as e:
            QMessageBox.critical(self, "Грешка", f"Не може да се свърже със сървъра.\nПроверете IP адреса и дали сървърът е стартиран.\n\nДетайли: {str(e)}")


class NraReportDialog(QDialog):
    """Dialog for previewing and generating the NRA (H-18) fiscal.ser report"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Месечен отчет към НАП (Наредба Н-18)")
        self.setMinimumSize(900, 600)
        
        layout = QVBoxLayout()
        
        # Info label
        info = QLabel("Списък на устройствата, маркирани за включване в месечния отчет (fiskal.ser)")
        info.setStyleSheet("font-weight: bold; color: #2c3e50;")
        layout.addWidget(info)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Договор", "Фирма", "Модел", "Сериен номер", "Месец", "Дирекция"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)
        
        # Buttons
        btn_layout = QHBoxLayout()
        self.btn_refresh = QPushButton("🔄 Обнови")
        self.btn_refresh.clicked.connect(self.load_data)
        self.btn_generate = QPushButton("📄 Генерирай fiskal.ser")
        self.btn_generate.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 5px;")
        self.btn_generate.clicked.connect(self.generate_report)
        self.btn_close = QPushButton("Затвори")
        self.btn_close.clicked.connect(self.accept)
        
        btn_layout.addWidget(self.btn_refresh)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_generate)
        btn_layout.addWidget(self.btn_close)
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
        self.load_data()

    def load_data(self):
        devices = get_devices_for_nra_report()
        self.table.setRowCount(len(devices))
        
        for i, d in enumerate(devices):
            self.table.setItem(i, 0, QTableWidgetItem(str(d.get('contract_number', ''))))
            self.table.setItem(i, 1, QTableWidgetItem(d.get('company_name', '')))
            self.table.setItem(i, 2, QTableWidgetItem(d.get('model', '')))
            self.table.setItem(i, 3, QTableWidgetItem(d.get('serial_number', '')))
            self.table.setItem(i, 4, QTableWidgetItem(d.get('nra_report_month', '')))
            self.table.setItem(i, 5, QTableWidgetItem(d.get('nra_td', '')))

    def generate_report(self):
        # We'll use the logic from main.py or move it here
        parent = self.parent()
        if hasattr(parent, 'run_nra_report_generation'):
            parent.run_nra_report_generation()
        else:
            QMessageBox.warning(self, "Внимание", "Функцията за генериране не е достъпна в този контекст.")
# Audit Log Viewer Dialog

class AuditLogDialog(QDialog):
    """Dialog to view audit logs of user actions"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Одит на действията")
        self.resize(900, 600)
        
        self.init_ui()
        self.load_logs()
        
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Filter section
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Филтър по потребител:"))
        
        self.filter_user = QLineEdit()
        self.filter_user.setPlaceholderText("Потребителско име...")
        self.filter_user.textChanged.connect(self.load_logs)
        filter_layout.addWidget(self.filter_user)
        
        filter_layout.addWidget(QLabel("Действие:"))
        self.filter_action = QLineEdit()
        self.filter_action.setPlaceholderText("Тип действие...")
        self.filter_action.textChanged.connect(self.load_logs)
        filter_layout.addWidget(self.filter_action)
        
        btn_refresh = QPushButton("Обнови")
        btn_refresh.clicked.connect(self.load_logs)
        filter_layout.addWidget(btn_refresh)
        
        layout.addLayout(filter_layout)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Дата/Час", "Потребител", "Действие", "Детайли"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 150)
        self.table.setColumnWidth(1, 120)
        self.table.setColumnWidth(2, 150)
        
        layout.addWidget(self.table)
        
        # Close button
        btn_close = QPushButton("Затвори")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)
        
        self.setLayout(layout)
    
    def load_logs(self):
        """Load audit logs from database with optional filtering"""
        from database import DB_PATH
        import sqlite3
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        query = "SELECT id, timestamp, username, action, details FROM audit_logs WHERE 1=1"
        params = []
        
        # Apply filters
        user_filter = self.filter_user.text().strip()
        if user_filter:
            query += " AND username LIKE ?"
            params.append(f"%{user_filter}%")
        
        action_filter = self.filter_action.text().strip()
        if action_filter:
            query += " AND action LIKE ?"
            params.append(f"%{action_filter}%")
        
        query += " ORDER BY id DESC LIMIT 1000"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        self.table.setRowCount(0)
        for row in rows:
            row_pos = self.table.rowCount()
            self.table.insertRow(row_pos)
            
            # Skip ID column (index 0), show only timestamp, username, action, details
            self.table.setItem(row_pos, 0, QTableWidgetItem(row[1]))  # timestamp
            self.table.setItem(row_pos, 1, QTableWidgetItem(row[2]))  # username
            self.table.setItem(row_pos, 2, QTableWidgetItem(row[3]))  # action
            self.table.setItem(row_pos, 3, QTableWidgetItem(row[4] or ""))  # details


class DeviceHistoryDialog(QDialog):
    """Dialog to view history/dossier for a specific device or contract (admin only)"""
    def __init__(self, device_id=None, contract_number=None, parent=None):
        super().__init__(parent)
        self.device_id = device_id
        self.contract_number = contract_number
        
        if device_id:
            self.setWindowTitle(f"История на устройство ID: {device_id}")
        elif contract_number:
            self.setWindowTitle(f"История на договор: {contract_number}")
        else:
            self.setWindowTitle("История")
            
        self.resize(900, 600)
        
        self.init_ui()
        self.load_history()
        
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Info label
        info_label = QLabel("Електронно досие - всички действия и промени:")
        info_label.setStyleSheet("font-weight: bold; font-size: 14px; margin-bottom: 10px;")
        layout.addWidget(info_label)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Дата/Час", "Потребител", "Действие", "Детайли"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 150)
        self.table.setColumnWidth(1, 120)
        self.table.setColumnWidth(2, 150)
        
        # Enable word wrap for details column
        self.table.setWordWrap(True)
        self.table.verticalHeader().setDefaultSectionSize(40)
        
        layout.addWidget(self.table)
        
        # Close button
        btn_close = QPushButton("Затвори")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)
        
        self.setLayout(layout)
    
    def load_history(self):
        """Load history from database"""
        if self.device_id:
            from database import get_device_history
            history = get_device_history(self.device_id)
        elif self.contract_number:
            from database import get_contract_history
            history = get_contract_history(self.contract_number)
        else:
            history = []
        
        self.table.setRowCount(0)
        for entry in history:
            row_pos = self.table.rowCount()
            self.table.insertRow(row_pos)
            
            self.table.setItem(row_pos, 0, QTableWidgetItem(entry["timestamp"]))
            self.table.setItem(row_pos, 1, QTableWidgetItem(entry["username"]))
            self.table.setItem(row_pos, 2, QTableWidgetItem(entry["action"]))
            self.table.setItem(row_pos, 3, QTableWidgetItem(entry["details"] or ""))
        
        if not history:
            # Show message if no history
            row_pos = self.table.rowCount()
            self.table.insertRow(row_pos)
            item = QTableWidgetItem("Няма записана история за това устройство/договор")
            item.setForeground(Qt.GlobalColor.gray)
            self.table.setItem(row_pos, 0, item)
            self.table.setSpan(row_pos, 0, 1, 4)


class RepairProtocolDialog(QDialog):
    """Dialog for entering repair details and generating a protocol"""
    
    def __init__(self, device_id: int, parent=None):
        super().__init__(parent)
        self.device_id = device_id
        self.setWindowTitle("Протокол за ремонт")
        self.setMinimumWidth(500)
        
        # Load device data to show context
        self.device_data = get_device_full(device_id)
        if not self.device_data:
            QMessageBox.critical(self, "Грешка", "Устройството не е намерено!")
            self.reject()
            return
            
        layout = QVBoxLayout()
        
        info_label = QLabel(f"<b>Устройство:</b> {self.device_data['model']} (S/N: {self.device_data['serial_number']})<br>"
                            f"<b>Клиент:</b> {self.device_data['company_name']}")
        info_label.setStyleSheet("padding: 10px; background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 4px;")
        layout.addWidget(info_label)
        
        form = QFormLayout()
        
        self.repair_date = QDateEdit()
        self.repair_date.setCalendarPopup(True)
        self.repair_date.setDisplayFormat("dd.MM.yyyy 'г.'")
        self.repair_date.setDate(QDate.currentDate())
        
        self.problem_description = QTextEdit()
        self.problem_description.setPlaceholderText("Въведете описание на проблема...")
        self.problem_description.setMinimumHeight(150)
        
        form.addRow("Дата на ремонт:", self.repair_date)
        form.addRow("Описание на проблема:", self.problem_description)
        
        layout.addLayout(form)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.btn_generate = QPushButton("📄 Генерирай Протокол")
        self.btn_generate.setStyleSheet("background-color: #28a745; color: white; font-weight: bold; padding: 8px;")
        self.btn_generate.clicked.connect(self.generate_protocol)
        
        self.btn_cancel = QPushButton("Отказ")
        self.btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_generate)
        btn_layout.addWidget(self.btn_cancel)
        
        layout.addLayout(btn_layout)
        self.setLayout(layout)
        
    def generate_protocol(self):
        problem = self.problem_description.toPlainText().strip()
        if not problem:
            QMessageBox.warning(self, "Грешка", "Моля, въведете описание на проблема.")
            return
            
        try:
            from contract_generator import generate_repair_protocol
            import os
            
            # Save to database first to get protocol number (id)
            repair_date_str = self.repair_date.date().toString('yyyy-MM-dd')
            protocol_id = add_repair_record(
                self.device_id,
                problem,
                repair_date_str
            )
            
            # Prepare data for generator
            client_data = {
                'company_name': self.device_data['company_name'],
                'address': self.device_data['address'],
                'mol': self.device_data['mol'],
                'phone1': self.device_data['phone1']
            }
            
            device_data = {
                'model': self.device_data['model'],
                'serial_number': self.device_data['serial_number'],
                'object_address': self.device_data['object_address']
            }
            
            repair_info = {
                'protocol_id': protocol_id,
                'repair_date': repair_date_str,
                'problem_description': problem
            }
            
            # Output directory
            output_dir = os.path.join(os.path.expanduser("~"), "Documents", "ContractsApp", "Protocols")
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
                
            template_path = "RepairProtocol_Template.docx"
            
            output_path = generate_repair_protocol(
                client_data,
                device_data,
                repair_info,
                template_path,
                output_dir
            )
            
            # Offer format and open
            if hasattr(self.parent(), 'choose_format_and_open'):
                self.parent().choose_format_and_open(output_path)
            else:
                QDesktopServices.openUrl(QUrl.fromLocalFile(output_path))
            
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "Грешка", f"Грешка при генериране на протокол: {str(e)}")


class ProductDialog(QDialog):
    """Dialog for adding or editing a product"""
    def __init__(self, product_data=None, parent=None):
        super().__init__(parent)
        self.product_data = product_data
        self.is_edit = product_data is not None
        self.setWindowTitle("Редактиране на продукт" if self.is_edit else "Добавяне на нов продукт")
        self.setMinimumWidth(450)
        
        layout = QVBoxLayout()
        form = QFormLayout()
        
        self.name = QLineEdit()
        if self.is_edit: self.name.setText(self.product_data['name'])
        
        self.category = QComboBox()
        self.category.setEditable(True)
        # We could load existing categories here
        self.category.addItems(["Хардуер", "Софтуер", "Сервизни услуги", "Консумативи"])
        if self.is_edit: self.category.setCurrentText(self.product_data['category'])
        
        self.price = QLineEdit()
        if self.is_edit: self.price.setText(str(self.product_data['price']))
        
        self.currency = QComboBox()
        self.currency.addItems(["BGN", "EUR"])
        if self.is_edit: self.currency.setCurrentText(self.product_data['currency'])
        
        self.description = QTextEdit()
        self.description.setMaximumHeight(100)
        if self.is_edit: self.description.setPlainText(self.product_data['description'] or "")
        
        form.addRow("Име на продукт:*", self.name)
        form.addRow("Категория:", self.category)
        form.addRow("Цена:*", self.price)
        form.addRow("Валута:", self.currency)
        form.addRow("Описание:", self.description)
        
        layout.addLayout(form)
        
        # Help label for BGN/EUR conversion
        self.calc_label = QLabel("Курс: 1 EUR = 1.95583 BGN")
        self.calc_label.setStyleSheet("color: gray; font-style: italic;")
        layout.addWidget(self.calc_label)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_save = QPushButton("💾 Запази")
        btn_save.clicked.connect(self.save)
        btn_save.setStyleSheet("background-color: #28a745; color: white; font-weight: bold; padding: 6px;")
        
        btn_cancel = QPushButton("Отказ")
        btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_cancel)
        
        layout.addLayout(btn_layout)
        self.setLayout(layout)
        
    def save(self):
        name = self.name.text().strip()
        price_str = self.price.text().strip().replace(',', '.')
        
        if not name:
            QMessageBox.warning(self, "Грешка", "Името е задължително!")
            return
            
        try:
            price = float(price_str)
        except ValueError:
            QMessageBox.warning(self, "Грешка", "Невалидна цена!")
            return
            
        data = {
            'name': name,
            'category': self.category.currentText(),
            'price': price,
            'currency': self.currency.currentText(),
            'description': self.description.toPlainText().strip()
        }
        
        try:
            user_id, username = get_user_auth(self)
            if self.is_edit:
                if update_product(self.product_data['id'], data, user_id=user_id, username=username):
                    self.accept()
                else:
                    QMessageBox.warning(self, "Грешка", "Не бе извършена промяна.")
            else:
                if add_product(data):
                    self.accept()
                else:
                    QMessageBox.warning(self, "Грешка", "Грешка при запис.")
        except Exception as e:
            QMessageBox.critical(self, "Грешка", f"Грешка при базата данни: {str(e)}")


class DuplicatePassportDialog(QDialog):
    def __init__(self, parent=None, default_manufacturer=None):
        super().__init__(parent)
        self.setWindowTitle("Заявление за дубликат")
        self.setFixedSize(400, 200)
        self.manufacturer = None
        self.default_manufacturer = default_manufacturer
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        
        form = QFormLayout()
        self.combo_manu = QComboBox()
        self.combo_manu.addItems(["Daisy", "Tremol", "Datecs"])
        
        if self.default_manufacturer:
            index = self.combo_manu.findText(self.default_manufacturer)
            if index >= 0:
                self.combo_manu.setCurrentIndex(index)
        
        form.addRow("Производител:", self.combo_manu)
        
        layout.addLayout(form)
        
        info = QLabel("Ще бъде генерирано заявление за дубликат на паспорт\nспоред избрания производител.")
        info.setStyleSheet("color: gray; font-style: italic;")
        info.setWordWrap(True)
        layout.addWidget(info)
        
        layout.addStretch()
        
        btns = QHBoxLayout()
        btn_gen = QPushButton("Генерирай")
        btn_gen.clicked.connect(self.accept_data)
        btn_cancel = QPushButton("Отказ")
        btn_cancel.clicked.connect(self.reject)
        
        btns.addWidget(btn_gen)
        btns.addWidget(btn_cancel)
        
        layout.addLayout(btns)
        self.setLayout(layout)

    def accept_data(self):
        self.manufacturer = self.combo_manu.currentText()
        self.accept()


class ClientEditorDialog(QDialog):
    """Dialog for adding or editing a client/counterparty"""
    def __init__(self, client_data=None, parent=None):
        super().__init__(parent)
        self.client_data = client_data
        self.is_edit = client_data is not None
        self.setWindowTitle("Редактиране на клиент" if self.is_edit else "Добавяне на нов клиент")
        self.setMinimumWidth(500)
        
        self.init_ui()
        if self.is_edit:
            self.load_data()

    def init_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        self.contract_number = QLineEdit()
        self.status = QComboBox()
        self.status.addItems(["активен", "прекратен", "бракувана"])
        self.status.setEditable(True)
        
        self.company_name = QLineEdit()
        self.company_name.setPlaceholderText("Име на фирмата...")
        
        self.city = QLineEdit()
        self.postal_code = QLineEdit()
        self.address = QLineEdit()
        self.eik = QLineEdit()
        
        self.vat_registered = QCheckBox("Регистриран по ЗДДС")
        
        self.mol = QLineEdit()
        self.phone1 = QLineEdit()
        self.phone2 = QLineEdit()
        
        self.contract_start = QDateEdit()
        self.contract_start.setCalendarPopup(True)
        self.contract_expiry = QDateEdit()
        self.contract_expiry.setCalendarPopup(True)
        
        form.addRow("Фирма/Клиент *:", self.company_name)
        
        # EIK + Check Button
        eik_layout = QHBoxLayout()
        eik_layout.addWidget(self.eik)
        self.btn_check_vat = QPushButton("🔍")
        self.btn_check_vat.setFixedWidth(40)
        self.btn_check_vat.setToolTip("Провери по ЕИК в НАП/Търговски регистър")
        self.btn_check_vat.clicked.connect(self.check_vat_status)
        eik_layout.addWidget(self.btn_check_vat)
        
        form.addRow("ЕИК *:", eik_layout)
        form.addRow("", self.vat_registered)
        form.addRow("МОЛ:", self.mol)
        form.addRow("Град:", self.city)
        form.addRow("Адрес:", self.address)
        form.addRow("Пощ. код:", self.postal_code)
        form.addRow("Тел. 1:", self.phone1)
        form.addRow("Тел. 2:", self.phone2)
        form.addRow("№ Договор:", self.contract_number)
        form.addRow("Статус:", self.status)
        form.addRow("Договор от:", self.contract_start)
        form.addRow("Изтича на:", self.contract_expiry)
        
        layout.addLayout(form)
        
        btns = QHBoxLayout()
        btn_save = QPushButton("💾 Запази")
        btn_save.clicked.connect(self.save_client)
        btn_save.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 5px;")
        
        btn_cancel = QPushButton("Отказ")
        btn_cancel.clicked.connect(self.reject)
        
        btns.addStretch()
        btns.addWidget(btn_save)
        btns.addWidget(btn_cancel)
        layout.addLayout(btns)

    def load_data(self):
        d = self.client_data
        self.company_name.setText(d.get('company_name', ''))
        self.eik.setText(d.get('eik', ''))
        self.vat_registered.setChecked(bool(d.get('vat_registered')))
        self.mol.setText(d.get('mol', ''))
        self.city.setText(d.get('city', ''))
        self.address.setText(d.get('address', ''))
        self.postal_code.setText(d.get('postal_code', ''))
        self.phone1.setText(d.get('phone1', ''))
        self.phone2.setText(d.get('phone2', ''))
        self.contract_number.setText(d.get('contract_number', ''))
        self.status.setCurrentText(d.get('status', 'активен'))
        
        from date_utils import db_to_qdate
        self.contract_start.setDate(db_to_qdate(d.get('contract_start')))
        self.contract_expiry.setDate(db_to_qdate(d.get('contract_expiry')))

    def check_vat_status(self):
        """Check VAT registration status online and fill data"""
        eik = self.eik.text().strip()
        if not eik:
            QMessageBox.warning(self, "Грешка", "Моля, въведете ЕИК първо.")
            return

        result = check_vat(eik)
        
        if result is None:
            QMessageBox.warning(self, "Няма връзка", "Няма информация или връзка с регистъра.")
        else:
            if result.get("name"):
                self.company_name.setText(result.get("name", ""))
                self.city.setText(result.get("city", ""))
                self.address.setText(result.get("address", ""))
                self.postal_code.setText(result.get("postal_code", ""))
                self.mol.setText(result.get("mol", ""))
                
                if result.get("valid"):
                    self.vat_registered.setChecked(True)
                    status_text = "ДА"
                else:
                    self.vat_registered.setChecked(False)
                    status_text = "НЕ"
                
                QMessageBox.information(self, "Успех", f"Открита фирма:\n{result.get('name')}\nЗДДС: {status_text}")
            else:
                QMessageBox.information(self, "Резултат", "Не бе открита информация за този ЕИК.")

    def save_client(self):
        data = {
            'company_name': self.company_name.text().strip(),
            'eik': self.eik.text().strip(),
            'vat_registered': self.vat_registered.isChecked(),
            'mol': self.mol.text().strip(),
            'city': self.city.text().strip(),
            'address': self.address.text().strip(),
            'postal_code': self.postal_code.text().strip(),
            'phone1': self.phone1.text().strip(),
            'phone2': self.phone2.text().strip(),
            'contract_number': self.contract_number.text().strip(),
            'status': self.status.currentText(),
            'contract_start': self.contract_start.date().toString("yyyy-MM-dd"),
            'contract_expiry': self.contract_expiry.date().toString("yyyy-MM-dd")
        }
        
        if not data['company_name'] or not data['eik']:
            QMessageBox.warning(self, "Грешка", "Попълнете Име на фирма и ЕИК!")
            return
            
        try:
            user_id, username = get_user_auth(self)
            if self.is_edit:
                if update_client(self.client_data['id'], data, user_id=user_id, username=username):
                    self.accept()
                else:
                    QMessageBox.critical(self, "Грешка", "Неуспешно обновяване в базата.")
            else:
                new_id = add_client(data)
                if new_id > 0:
                    self.accept()
                else:
                    QMessageBox.critical(self, "Грешка", "Неуспешно добавяне в базата.")
        except Exception as e:
            QMessageBox.critical(self, "Грешка", f"Системна грешка: {e}")


class ClientManagerDialog(QDialog):
    """Dialog for managing counterparts (add/edit/delete/search/select)"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Управление на контрагенти")
        self.setMinimumSize(1000, 600)
        self.selected_client = None
        
        self.init_ui()
        self.load_data()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Search area
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Търсене по име на фирма, ЕИК или номер на договор...")
        self.search_input.textChanged.connect(self.load_data)
        search_layout.addWidget(QLabel("🔍 Търсене:"))
        search_layout.addWidget(self.search_input)
        
        btn_add = QPushButton("➕ Добави нов")
        btn_add.clicked.connect(self.add_client_action)
        btn_add.setStyleSheet("background-color: #27ae60; color: white;")
        search_layout.addWidget(btn_add)
        
        layout.addLayout(search_layout)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "ID", "Фирма/Клиент", "ЕИК", "Град", "Тел.", "Договор №"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.doubleClicked.connect(self.select_client)
        layout.addWidget(self.table)
        
        # Action buttons
        btns_layout = QHBoxLayout()
        
        btn_edit = QPushButton("✏️ Редактирай")
        btn_edit.clicked.connect(self.edit_client_action)
        
        btn_delete = QPushButton("🗑️ Изтрий")
        btn_delete.clicked.connect(self.delete_client_action)
        btn_delete.setStyleSheet("color: red;")
        
        btn_select = QPushButton("✅ Избери")
        btn_select.clicked.connect(self.select_client)
        btn_select.setStyleSheet("background-color: #2980b9; color: white; font-weight: bold; min-width: 100px;")
        
        btn_close = QPushButton("Затвори")
        btn_close.clicked.connect(self.reject)
        
        btns_layout.addWidget(btn_edit)
        btns_layout.addWidget(btn_delete)
        btns_layout.addStretch()
        btns_layout.addWidget(btn_select)
        btns_layout.addWidget(btn_close)
        
        layout.addLayout(btns_layout)

    def load_data(self):
        query = self.search_input.text().strip()
        if query:
            clients = search_clients(query)
        else:
            clients = get_all_clients()
            
        self.table.setRowCount(0)
        self.clients_list = clients # Keep reference
        
        for row_idx, c in enumerate(clients):
            self.table.insertRow(row_idx)
            self.table.setItem(row_idx, 0, QTableWidgetItem(str(c['id'])))
            self.table.setItem(row_idx, 1, QTableWidgetItem(c.get('company_name', '')))
            self.table.setItem(row_idx, 2, QTableWidgetItem(c.get('eik', '')))
            self.table.setItem(row_idx, 3, QTableWidgetItem(c.get('city', '')))
            self.table.setItem(row_idx, 4, QTableWidgetItem(c.get('phone1', '')))
            self.table.setItem(row_idx, 5, QTableWidgetItem(c.get('contract_number', '')))

    def add_client_action(self):
        dlg = ClientEditorDialog(parent=self)
        if dlg.exec():
            self.load_data()

    def edit_client_action(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Внимание", "Изберете клиент за редакция!")
            return
            
        client_data = self.clients_list[row]
        dlg = ClientEditorDialog(client_data=client_data, parent=self)
        if dlg.exec():
            self.load_data()

    def delete_client_action(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Внимание", "Изберете клиент за изтриване!")
            return
            
        client_name = self.table.item(row, 1).text()
        cid = int(self.table.item(row, 0).text())
        
        confirm = QMessageBox.question(self, "Потвърждение", 
                                     f"Сигурни ли сте, че искате да изтриете клиента '{client_name}'?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if confirm == QMessageBox.StandardButton.Yes:
            if delete_client(cid):
                self.load_data()
            else:
                QMessageBox.critical(self, "Грешка", "Неуспешно изтриване.")

    def select_client(self):
        row = self.table.currentRow()
        if row >= 0:
            self.selected_client = self.clients_list[row]
            self.accept()
        else:
            QMessageBox.warning(self, "Внимание", "Моля изберете клиент!")


class InvoiceDialog(QDialog):
    """Professional dialog for issuing invoices and proformas"""
    def __init__(self, parent=None, invoice_data=None):
        super().__init__(parent)
        self.setWindowTitle("Издаване на документ (Фактура / Проформа)")
        self.setMinimumSize(950, 750)
        self.invoice_data = invoice_data
        self.items = []
        
        self.setup_ui()
        if invoice_data:
            self.load_invoice_data()
        else:
            self.inv_number.setText(get_next_invoice_number())

    FIXED_EXCHANGE_RATE = 1.95583

    def load_invoice_data(self):
        inv = self.invoice_data
        if not inv: return
        
        # Header
        index = self.inv_type.findText("Фактура" if inv['type'] == 'INV' else "Проформа")
        self.inv_type.setCurrentIndex(index)
        self.inv_number.setText(inv['number'])
        self.date_issued.setDate(db_to_qdate(inv['date_issued']))
        self.date_due.setDate(db_to_qdate(inv['date_due']))
        
        # Client
        self.client_name.setText(inv['client_name'])
        self.client_eik.setText(inv['client_eik'])
        self.client_vat.setText(inv['client_vat'] or "")
        self.client_address.setText(inv['client_address'])
        self.client_mol.setText(inv['client_mol'] or "")
        
        # Items
        self.table.setRowCount(0)
        for item in inv.get('items', []):
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.setup_row_widgets(row, item['description'], item['quantity'], item['unit_price'])
            
        # Stats
        self.vat_rate.setValue(int(inv['vat_rate']))
        self.pay_method.setCurrentText(inv['payment_method'])
        self.pay_status.setCurrentText(inv['payment_status'])
        self.notes.setPlainText(inv['notes'] or "")
        
        self.calculate_totals()
            
    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        
        # 1. Header Information (Number, Dates, Type)
        header_group = QGroupBox("Информация за документа")
        header_layout = QGridLayout()
        
        self.inv_type = QComboBox()
        self.inv_type.addItems(["Фактура", "Проформа"])
        self.inv_type.currentIndexChanged.connect(self.update_invoice_number)
        
        self.inv_number = QLineEdit()
        self.inv_number.setPlaceholderText("Автоматично...")
        
        self.date_issued = QDateEdit()
        self.date_issued.setCalendarPopup(True)
        self.date_issued.setDate(QDate.currentDate())
        self.date_issued.setDisplayFormat("dd.MM.yyyy")
        
        self.date_due = QDateEdit()
        self.date_due.setCalendarPopup(True)
        self.date_due.setDate(QDate.currentDate().addDays(14))
        self.date_due.setDisplayFormat("dd.MM.yyyy")
        
        header_layout.addWidget(QLabel("Тип:"), 0, 0)
        header_layout.addWidget(self.inv_type, 0, 1)
        header_layout.addWidget(QLabel("Номер:"), 0, 2)
        header_layout.addWidget(self.inv_number, 0, 3)
        header_layout.addWidget(QLabel("Дата на издаване:"), 1, 0)
        header_layout.addWidget(self.date_issued, 1, 1)
        header_layout.addWidget(QLabel("Падеж:"), 1, 2)
        header_layout.addWidget(self.date_due, 1, 3)
        
        header_group.setLayout(header_layout)
        main_layout.addWidget(header_group)
        
        # 2. Client Selection & Data
        client_group = QGroupBox("Данни за Получателя (Контрагент)")
        client_layout = QGridLayout()
        
        self.client_selector = QComboBox()
        self.client_selector.setEditable(True)
        self.client_selector.setPlaceholderText("Избор на клиент (търси по име или ЕИК)...")
        # Add event filter for double click
        if self.client_selector.lineEdit():
            self.client_selector.lineEdit().installEventFilter(self)
            
        self.load_clients()
        self.client_selector.currentIndexChanged.connect(self.on_client_selected)
        
        btn_search_client = QPushButton("🔍")
        btn_search_client.setToolTip("Отвори мениджър на контрагенти")
        btn_search_client.setFixedWidth(40)
        btn_search_client.clicked.connect(self.open_client_manager)
        
        self.client_name = QLineEdit()
        self.client_eik = QLineEdit()
        self.client_vat = QLineEdit()
        self.client_address = QLineEdit()
        self.client_mol = QLineEdit()
        
        client_layout.addWidget(QLabel("Избор от базата:"), 0, 0)
        
        sel_layout = QHBoxLayout()
        sel_layout.addWidget(self.client_selector)
        sel_layout.addWidget(btn_search_client)
        client_layout.addLayout(sel_layout, 0, 1, 1, 3)
        client_layout.addWidget(QLabel("Фирма Получател:"), 1, 0)
        client_layout.addWidget(self.client_name, 1, 1)
        client_layout.addWidget(QLabel("ЕИК:"), 1, 2)
        
        eik_layout = QHBoxLayout()
        eik_layout.addWidget(self.client_eik)
        self.btn_check_vat = QPushButton("🔍")
        self.btn_check_vat.setFixedWidth(40)
        self.btn_check_vat.setToolTip("Провери по ЕИК в НАП/Търговски регистър")
        self.btn_check_vat.clicked.connect(self.check_vat_status)
        eik_layout.addWidget(self.btn_check_vat)
        
        client_layout.addLayout(eik_layout, 1, 3)
        client_layout.addWidget(QLabel("№ по ЗДДС:"), 2, 0)
        client_layout.addWidget(self.client_vat, 2, 1)
        client_layout.addWidget(QLabel("Адрес:"), 2, 2)
        client_layout.addWidget(self.client_address, 2, 3)
        client_layout.addWidget(QLabel("МОЛ:"), 3, 0)
        client_layout.addWidget(self.client_mol, 3, 1)
        
        client_group.setLayout(client_layout)
        main_layout.addWidget(client_group)
        
        # 3. Items Table
        items_group = QGroupBox("Артикули / Услуги / Ремонти")
        items_layout = QVBoxLayout()
        
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Описание на стоката/услугата", "Кол.", "Ед. Цена", "Стойност", ""])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(1, 70)
        self.table.setColumnWidth(2, 100)
        self.table.setColumnWidth(3, 120)
        self.table.setColumnWidth(4, 30)
        
        items_layout.addWidget(self.table)
        
        # Item buttons
        btns_layout = QHBoxLayout()
        self.btn_add_manual = QPushButton("➕ Ръчно добавяне")
        self.btn_add_manual.clicked.connect(self.add_manual_item)
        self.btn_import_product = QPushButton("📦 Избор от Продукти")
        self.btn_import_product.clicked.connect(self.import_product)
        
        btns_layout.addWidget(self.btn_add_manual)
        btns_layout.addWidget(self.btn_import_product)
        btns_layout.addStretch()
        items_layout.addLayout(btns_layout)
        
        items_group.setLayout(items_layout)
        main_layout.addWidget(items_group)
        
        # 4. Footer (Totals, Payment, Methods)
        footer_layout = QHBoxLayout()
        
        # Payment details
        pay_group = QGroupBox("Плащане и бележки")
        pay_layout = QFormLayout()
        self.pay_method = QComboBox()
        self.pay_method.addItems(["Банков път", "В брой", "С карта", "Наложен платеж"])
        self.pay_status = QComboBox()
        self.pay_status.addItems(["PENDING", "PAID", "PARTIAL", "OVERDUE"])
        self.notes = QTextEdit()
        self.notes.setPlaceholderText("Допълнителна информация...")
        self.notes.setMaximumHeight(80)
        
        pay_layout.addRow("Начин на плащане:", self.pay_method)
        pay_layout.addRow("Статус на плащане:", self.pay_status)
        pay_layout.addRow("Забележка:", self.notes)
        pay_group.setLayout(pay_layout)
        footer_layout.addWidget(pay_group, 1)
        
        # Totals
        totals_group = QGroupBox("Суми")
        totals_layout = QFormLayout()
        
        self.lbl_subtotal = QLabel("0.00 €")
        self.lbl_subtotal.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.lbl_vat = QLabel("0.00 €")
        self.lbl_vat.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.lbl_total = QLabel("0.00 €")
        self.lbl_total.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.lbl_total.setStyleSheet("font-size: 20px; font-weight: bold; color: #d35400;")
        
        self.lbl_bgn_total = QLabel("Равностойност: 0.00 лв.")
        self.lbl_bgn_total.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.lbl_bgn_total.setStyleSheet("font-style: italic; color: #7f8c8d;")
        
        self.vat_rate = QSpinBox()
        self.vat_rate.setRange(0, 100)
        self.vat_rate.setValue(20)
        self.vat_rate.setSuffix(" %")
        self.vat_rate.valueChanged.connect(self.calculate_totals)
        
        totals_layout.addRow("<b>Данъчна основа:</b>", self.lbl_subtotal)
        totals_layout.addRow("ДДС ставка:", self.vat_rate)
        totals_layout.addRow("ДДС сума:", self.lbl_vat)
        totals_layout.addRow("<font size='5' color='#2c3e50'><b>ТОТАЛ:</b></font>", self.lbl_total)
        totals_layout.addRow("", self.lbl_bgn_total)
        
        totals_group.setLayout(totals_layout)
        footer_layout.addWidget(totals_group, 1)
        
        main_layout.addLayout(footer_layout)
        
        # 5. Dialog Buttons
        btns = QHBoxLayout()
        self.btn_save = QPushButton("💾 ЗАПИС НА ДОКУМЕНТА")
        self.btn_save.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 12px; font-size: 14px;")
        self.btn_save.clicked.connect(self.save_invoice)
        
        self.btn_cancel = QPushButton("Отказ")
        self.btn_cancel.setMinimumHeight(40)
        self.btn_cancel.clicked.connect(self.reject)
        
        btns.addStretch()
        btns.addWidget(self.btn_cancel)
        btns.addWidget(self.btn_save)
        main_layout.addLayout(btns)

    # --- Methods ---
    def open_client_manager(self):
        """Open the professional client management dialog"""
        dlg = ClientManagerDialog(parent=self)
        if dlg.exec():
            if dlg.selected_client:
                c = dlg.selected_client
                self.client_name.setText(c.get('company_name', ''))
                self.client_eik.setText(c.get('eik', ''))
                self.client_vat.setText(c.get('vat_registered') if isinstance(c.get('vat_registered'), str) else ("BG"+c['eik'] if c.get('vat_registered') else ""))
                self.client_address.setText(c.get('address', ''))
                self.client_mol.setText(c.get('mol', ''))
                
                # Try to select in combo as well
                idx = self.client_selector.findText(c['company_name'])
                if idx >= 0:
                    self.client_selector.setCurrentIndex(idx)
        # Reload clients in case some were added/deleted
        self.load_clients()

    def eventFilter(self, obj, event):
        """Handle double click on client selector line edit"""
        from PyQt6.QtCore import QEvent
        if obj == self.client_selector.lineEdit() and event.type() == QEvent.Type.MouseButtonDblClick:
            self.open_client_manager()
            return True
        return super().eventFilter(obj, event)

    def load_clients(self):
        try:
            self.clients = get_all_clients()
            self.client_selector.clear()
            self.client_selector.addItem("", None)
            for c in self.clients:
                display = f"{c['company_name']} ({c['eik']})"
                self.client_selector.addItem(display, c)
        except:
            pass
            
    def check_vat_status(self):
        """Check VAT registration status online and fill data"""
        eik = self.client_eik.text().strip()
        if not eik:
            QMessageBox.warning(self, "Грешка", "Моля, въведете ЕИК първо.")
            return

        result = check_vat(eik)
        
        if result is None:
            QMessageBox.warning(self, "Няма връзка", "Няма информация или връзка с регистъра.")
        else:
            if result.get("name"):
                self.client_name.setText(result.get("name", ""))
                
                # Combine City + Address if needed, or just address
                # InvoiceDialog has only header fields for Address, City usually separate or combined.
                # In this dialog: self.client_address
                addr_full = f"{result.get('city', '')}, {result.get('address', '')}".strip(', ')
                self.client_address.setText(addr_full)
                
                self.client_mol.setText(result.get("mol", ""))
                
                if result.get("valid"):
                    self.client_vat.setText(str(result.get('vat_number', 'BG'+eik)))
                    status_text = "ДА"
                else:
                    self.client_vat.setText("")
                    status_text = "НЕ"
                
                QMessageBox.information(self, "Успех", f"Открита фирма:\n{result.get('name')}\nЗДДС: {status_text}")
            else:
                QMessageBox.information(self, "Резултат", "Не бе открита информация за този ЕИК.")

    def on_client_selected(self):
        data = self.client_selector.currentData()
        if data:
            self.client_name.setText(data.get('company_name', ''))
            self.client_eik.setText(data.get('eik', ''))
            self.client_vat.setText(data.get('vat_registered', ''))
            self.client_address.setText(f"{data.get('city', '')}, {data.get('address', '')}")
            self.client_mol.setText(data.get('mol', ''))
            
    def update_invoice_number(self):
        t = 'INV' if self.inv_type.currentIndex() == 0 else 'PRO'
        self.inv_number.setText(get_next_invoice_number(t))
        
    def add_manual_item(self):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.setup_row_widgets(row)
        
    def setup_row_widgets(self, row, desc="", qty=1, price=0):
        # Description
        edit_desc = QLineEdit(desc)
        self.table.setCellWidget(row, 0, edit_desc)
        
        # Qty
        spin_qty = QDoubleSpinBox()
        spin_qty.setRange(0.001, 999999)
        spin_qty.setValue(qty)
        spin_qty.setDecimals(3)
        spin_qty.valueChanged.connect(self.calculate_totals)
        self.table.setCellWidget(row, 1, spin_qty)
        
        # Price
        spin_price = QDoubleSpinBox()
        spin_price.setRange(0, 999999)
        spin_price.setValue(price)
        spin_price.setDecimals(2)
        spin_price.valueChanged.connect(self.calculate_totals)
        self.table.setCellWidget(row, 2, spin_price)
        
        # Total (Label)
        lbl_total = QLabel(f"{qty * price:.2f}")
        lbl_total.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lbl_total.setStyleSheet("font-weight: bold; color: #34495e;")
        self.table.setCellWidget(row, 3, lbl_total)
        
        # Delete button
        btn_del = QPushButton("❌")
        btn_del.setFlat(True)
        btn_del.setCursor(Qt.CursorShape.PointingHandCursor)
        # We need to capture the current row strictly
        btn_del.clicked.connect(self.make_delete_callback(row))
        self.table.setCellWidget(row, 4, btn_del)
        
        self.calculate_totals()

    def make_delete_callback(self, row_idx):
        def callback():
            # Find the actual current row of this button as table might have shifted
            for r in range(self.table.rowCount()):
                if self.table.cellWidget(r, 4) == self.sender():
                    self.table.removeRow(r)
                    break
            self.calculate_totals()
        return callback
        
    def import_product(self):
        products = get_all_products()
        if not products:
            QMessageBox.warning(self, "Внимание", "Няма намерени продукти в номенклатурата.")
            return
            
        from PyQt6.QtWidgets import QInputDialog
        items_list = [f"{p['name']} ({p['price']:.2f} {p['currency']})" for p in products]
        item, ok = QInputDialog.getItem(self, "Избор на продукт", "Продукт:", items_list, 0, False)
        
        if ok and item:
            idx = items_list.index(item)
            p = products[idx]
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.setup_row_widgets(row, p['name'], 1, p['price'])

    def calculate_totals(self):
        subtotal = 0
        for r in range(self.table.rowCount()):
            qty_widget = self.table.cellWidget(r, 1)
            price_widget = self.table.cellWidget(r, 2)
            if not qty_widget or not price_widget:
                continue
                
            qty = qty_widget.value()
            price = price_widget.value()
            row_total = qty * price
            subtotal += row_total
            self.table.cellWidget(r, 3).setText(f"{row_total:.2f}")
            
        vat_rate = self.vat_rate.value()
        vat_amount = subtotal * (vat_rate / 100)
        total = subtotal + vat_amount
        total_bgn = total * self.FIXED_EXCHANGE_RATE
        
        self.lbl_subtotal.setText(f"{subtotal:.2f} €")
        self.lbl_vat.setText(f"{vat_amount:.2f} €")
        self.lbl_total.setText(f"{total:.2f} €")
        self.lbl_bgn_total.setText(f"Равностойност: {total_bgn:.2f} лв.")
        
    def save_invoice(self):
        if not self.client_name.text() or not self.inv_number.text():
            QMessageBox.warning(self, "Грешка", "Моля попълнете номер на документ и име на клиент!")
            self.inv_number.setFocus()
            return
            
        if self.table.rowCount() == 0:
            QMessageBox.warning(self, "Грешка", "Добавете поне един артикул!")
            return
            
        # Collect items
        items_to_save = []
        for r in range(self.table.rowCount()):
            desc_widget = self.table.cellWidget(r, 0)
            if not desc_widget or not desc_widget.text():
                QMessageBox.warning(self, "Грешка", f"Артикул на ред {r+1} няма описание!")
                return
            items_to_save.append({
                'description': desc_widget.text(),
                'quantity': self.table.cellWidget(r, 1).value(),
                'unit_price': self.table.cellWidget(r, 2).value()
            })
            
        # Collect header data
        client_data = self.client_selector.currentData()
        data = {
            'number': self.inv_number.text(),
            'type': 'INV' if self.inv_type.currentIndex() == 0 else 'PRO',
            'client_id': client_data['id'] if client_data else None,
            'client_name': self.client_name.text(),
            'client_eik': self.client_eik.text(),
            'client_vat': self.client_vat.text(),
            'client_address': self.client_address.text(),
            'client_mol': self.client_mol.text(),
            'date_issued': self.date_issued.date().toString("yyyy-MM-dd"),
            'date_due': self.date_due.date().toString("yyyy-MM-dd"),
            'vat_rate': self.vat_rate.value(),
            'currency': 'EUR',
            'payment_status': self.pay_status.currentText(),
            'payment_method': self.pay_method.currentText(),
            'notes': self.notes.toPlainText(),
            'total_base': sum(i['quantity'] * i['unit_price'] for i in items_to_save),
            'total_vat': sum(i['quantity'] * i['unit_price'] for i in items_to_save) * (self.vat_rate.value() / 100),
            'total_amount': sum(i['quantity'] * i['unit_price'] for i in items_to_save) * (1 + self.vat_rate.value() / 100)
        }
        
        try:
            user_id, username = get_user_auth(self)
            if self.invoice_data and self.invoice_data.get('id'):
                invoice_id = self.invoice_data['id']
                if update_invoice(invoice_id, data, items_to_save, user_id=user_id, username=username):
                    msg = f"Документ №{data['number']} бе успешно обновен."
                else:
                    raise Exception("Неуспешно обновяване в базата.")
            else:
                invoice_id = add_invoice(data, items_to_save)
                msg = f"Документ №{data['number']} бе успешно записан."
                
            if invoice_id:
                reply = QMessageBox.question(self, "Успех", 
                    f"{msg}\nЖелаете ли да генерирате PDF файл?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                
                if reply == QMessageBox.StandardButton.Yes:
                    self.export_to_pdf_action(data, items_to_save)
                
                self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Грешка", f"Грешка при запис на фактура: {str(e)}")

    def export_to_pdf_action(self, data, items):
        """Helper to trigger PDF generation and open it"""
        prefix = "Faktura" if data['type'] == 'INV' else "Proforma"
        default_name = f"{prefix}_{data['number']}.pdf"
        
        save_path = os.path.join(os.path.expanduser("~"), "Documents", "ContractsApp", "Invoices")
        os.makedirs(save_path, exist_ok=True)
        
        file_path = os.path.join(save_path, default_name)
        
        data_for_pdf = data.copy()
        data_for_pdf['items'] = items
        
        # Fetch seller details from settings
        from database import get_setting
        data_for_pdf['seller'] = {
            'name': get_setting('name', 'Д и Д Фискал Системс ЕООД'),
            'eik': get_setting('eik', '205634567'),
            'vat': get_setting('vat', 'BG205634567'),
            'city': get_setting('city', 'София'),
            'address': get_setting('address', 'гр. София, бул. България №1'),
            'mol': get_setting('mol', 'Александър Петров')
        }
        
        if generate_invoice_pdf(data_for_pdf, file_path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))
            return True
        return False


class AuditLogViewerDialog(QDialog):
    """Dialog for viewing the application's audit trail (history of changes)"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("История на промените (Audit Log)")
        self.setMinimumSize(1100, 700)
        
        self.con = get_connection()
        self.setup_ui()
        self.load_logs()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Filter Area
        filter_group = QGroupBox("Филтриране")
        filter_layout = QHBoxLayout()
        
        self.user_filter = QComboBox()
        self.user_filter.addItem("Всички потребители")
        # Load unique usernames from DB
        try:
            cur = self.con.cursor()
            cur.execute("SELECT DISTINCT username FROM audit_logs ORDER BY username")
            for row in cur.fetchall():
                if row[0]: self.user_filter.addItem(row[0])
        except: pass
            
        self.action_filter = QComboBox()
        self.action_filter.addItems(["Всички действия", "UPDATE_CLIENT", "UPDATE_DEVICE", "UPDATE_PRODUCT", "UPDATE_INVOICE", "DELETE", "LOGIN"])
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Търсене в детайли/договор...")
        
        btn_refresh = QPushButton("🔄 Опресни")
        btn_refresh.clicked.connect(self.load_logs)
        
        filter_layout.addWidget(QLabel("Потребител:"))
        filter_layout.addWidget(self.user_filter)
        filter_layout.addWidget(QLabel("Действие:"))
        filter_layout.addWidget(self.action_filter)
        filter_layout.addWidget(QLabel("Търсене:"))
        filter_layout.addWidget(self.search_input)
        filter_layout.addWidget(btn_refresh)
        
        filter_group.setLayout(filter_layout)
        layout.addWidget(filter_group)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Дата/Час", "Потребител", "Действие", "Договор №", "ID Обект", "Промени / Детайли"])
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.doubleClicked.connect(self.show_details)
        layout.addWidget(self.table)
        
        # Footer
        btns = QHBoxLayout()
        btn_close = QPushButton("Затвори")
        btn_close.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(btn_close)
        layout.addLayout(btns)
        
        # Connect signals
        self.user_filter.currentIndexChanged.connect(self.load_logs)
        self.action_filter.currentIndexChanged.connect(self.load_logs)
        self.search_input.textChanged.connect(self.load_logs)

    def load_logs(self):
        try:
            cur = self.con.cursor()
            query = "SELECT timestamp, username, action, contract_number, device_id, details FROM audit_logs WHERE 1=1"
            params = []
            
            user = self.user_filter.currentText()
            if user != "Всички потребители":
                query += " AND username = ?"
                params.append(user)
                
            action = self.action_filter.currentText()
            if action != "Всички действия":
                query += " AND action = ?"
                params.append(action)
                
            search = self.search_input.text().strip()
            if search:
                query += " AND (details LIKE ? OR contract_number LIKE ?)"
                search_param = f"%{search}%"
                params.append(search_param)
                params.append(search_param)
                
            query += " ORDER BY timestamp DESC LIMIT 500"
            
            cur.execute(query, params)
            rows = cur.fetchall()
            
            self.table.setRowCount(0)
            for row_idx, row_data in enumerate(rows):
                self.table.insertRow(row_idx)
                for col_idx, item in enumerate(row_data):
                    val = str(item) if item is not None else ""
                    table_item = QTableWidgetItem(val)
                    if col_idx == 2: # Highlight actions
                        if "DELETE" in val: table_item.setForeground(Qt.GlobalColor.red)
                        elif "UPDATE" in val: table_item.setForeground(Qt.GlobalColor.blue)
                    self.table.setItem(row_idx, col_idx, table_item)
        except Exception as e:
            print(f"Error loading logs: {e}")

    def show_details(self):
        row = self.table.currentRow()
        if row < 0: return
        
        timestamp = self.table.item(row, 0).text()
        user = self.table.item(row, 1).text()
        action = self.table.item(row, 2).text()
        details = self.table.item(row, 5).text()
        
        msg = f"<b>Дата:</b> {timestamp}<br>"
        msg += f"<b>Потребител:</b> {user}<br>"
        msg += f"<b>Действие:</b> {action}<br><br>"
        msg += f"<b>Детайли:</b><br>{details.replace(', ', '<br>')}"
        
        QMessageBox.information(self, "Детайли на промяната", msg)

    def closeEvent(self, event):
        if self.con:
            self.con.close()
        super().closeEvent(event)



class ProtocolDialog(QDialog):
    """Dialog for creating a Handover Protocol (Приемо-предавателен протокол)"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Нов приемо-предавателен протокол")
        self.resize(600, 700)
        self.setup_ui()
        self.load_counterparties()
        self.load_service_defaults()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 1. Counterparty Selection
        grp_client = QGroupBox("Информация за Контрагент (Получател)")
        lay_client = QFormLayout()
        
        self.combo_client = QComboBox()
        self.combo_client.setEditable(True)
        self.combo_client.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.combo_client.currentIndexChanged.connect(self.on_client_selected)
        
        self.cp_name = QLineEdit()
        self.cp_eik = QLineEdit()
        self.cp_address = QLineEdit()
        self.cp_mol = QLineEdit()
        
        lay_client.addRow("Избери съществуващ:", self.combo_client)
        lay_client.addRow("Име на фирма:", self.cp_name)
        
        # EIK + Check Button
        eik_layout = QHBoxLayout()
        eik_layout.addWidget(self.cp_eik)
        self.btn_check_vat = QPushButton("🔍")
        self.btn_check_vat.setFixedWidth(40)
        self.btn_check_vat.setToolTip("Провери по ЕИК в НАП/Търговски регистър")
        self.btn_check_vat.clicked.connect(self.check_vat_status)
        eik_layout.addWidget(self.btn_check_vat)
        
        lay_client.addRow("ЕИК:", eik_layout)
        lay_client.addRow("Адрес по рег.:", self.cp_address)
        lay_client.addRow("МОЛ:", self.cp_mol)
        
        grp_client.setLayout(lay_client)
        layout.addWidget(grp_client)
        
        # 2. Technician & Protocol Details
        grp_proto = QGroupBox("Детайли на протокола")
        lay_proto = QFormLayout()
        
        self.proto_date = QDateEdit(QDate.currentDate())
        self.proto_date.setCalendarPopup(True)
        self.proto_date.setDisplayFormat("dd.MM.yyyy")
        
        self.tech_egn = QLineEdit()
        self.tech_capacity = QLineEdit("Сервизен техник")
        
        self.proto_desc = QTextEdit()
        self.proto_desc.setPlaceholderText("Опишете какво се предава и приема (устройство, състояние, окомплектовка)...")
        self.proto_desc.setMaximumHeight(100)
        
        self.proto_notes = QLineEdit()
        self.proto_ref = QLineEdit()
        self.proto_ref.setPlaceholderText("Договор № или Фактура №")
        
        lay_proto.addRow("Дата:", self.proto_date)
        lay_proto.addRow("ЕГН на техник:", self.tech_egn)
        lay_proto.addRow("В качеството на:", self.tech_capacity)
        lay_proto.addRow("Описание на вещите:", self.proto_desc)
        lay_proto.addRow("Забележки:", self.proto_notes)
        lay_proto.addRow("Основание (№ дог/ф-ра):", self.proto_ref)
        
        grp_proto.setLayout(lay_proto)
        layout.addWidget(grp_proto)
        
        # Buttons
        btns = QHBoxLayout()
        btn_gen = QPushButton("📝 Генерирай и отвори Word файл")
        btn_gen.setStyleSheet("background-color: #2c3e50; color: white; font-weight: bold; padding: 10px;")
        btn_gen.clicked.connect(self.generate_protocol)
        
        btn_close = QPushButton("Отказ")
        btn_close.clicked.connect(self.reject)
        
        btns.addWidget(btn_gen)
        btns.addWidget(btn_close)
        layout.addLayout(btns)

    def load_counterparties(self):
        self.counterparties = get_all_counterparties()
        self.combo_client.clear()
        self.combo_client.addItem("-- Изберете или добавете нов --", None)
        for cp in self.counterparties:
            self.combo_client.addItem(cp['name'], cp)
            
        completer = QCompleter([cp['name'] for cp in self.counterparties])
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.combo_client.setCompleter(completer)

    def load_service_defaults(self):
        # Load from settings
        self.tech_egn.setText(get_setting('tech_egn', ''))
        # capacity remains default or last used? for now default

    def check_vat_status(self):
        """Check VAT registration status online and fill data"""
        eik = self.cp_eik.text().strip()
        if not eik:
            QMessageBox.warning(self, "Грешка", "Моля, въведете ЕИК първо.")
            return

        result = check_vat(eik)
        
        if result is None:
            QMessageBox.warning(self, "Няма връзка", "Няма информация или връзка с регистъра.")
        else:
            if result.get("name"):
                self.cp_name.setText(result.get("name", ""))
                
                # Combine City + Address for the single address field
                addr_full = f"{result.get('city', '')}, {result.get('address', '')}".strip(', ')
                self.cp_address.setText(addr_full)
                
                self.cp_mol.setText(result.get("mol", ""))
                
                QMessageBox.information(self, "Успех", f"Открита фирма:\n{result.get('name')}")
            else:
                QMessageBox.information(self, "Резултат", "Не бе открита информация за този ЕИК.")

    def on_client_selected(self, index):
        data = self.combo_client.itemData(index)
        if data:
            self.cp_name.setText(data['name'])
            self.cp_eik.setText(data['eik'])
            self.cp_address.setText(data['address'])
            self.cp_mol.setText(data['mol'])
        else:
            if index > 0: # Editing existing name
                pass 
            else: # Reset
                self.cp_name.clear()
                self.cp_eik.clear()
                self.cp_address.clear()
                self.cp_mol.clear()

    def generate_protocol(self):
        # 1. Validation
        if not self.cp_name.text().strip():
            QMessageBox.warning(self, "Грешка", "Моля въведете име на контрагент!")
            return
            
        # 2. Check if new counterparty or update
        cp_data = self.combo_client.currentData()
        cp_id = cp_data['id'] if cp_data else None
        
        name = self.cp_name.text().strip()
        eik = self.cp_eik.text().strip()
        addr = self.cp_address.text().strip()
        mol = self.cp_mol.text().strip()
        
        if not cp_id:
            # Check if name already exists in list (avoid duplicates)
            existing = next((cp for cp in self.counterparties if cp['name'].lower() == name.lower()), None)
            if existing:
                cp_id = existing['id']
                update_counterparty(cp_id, name, eik, addr, mol, "")
            else:
                cp_id = add_counterparty(name, eik, addr, mol, "")
        else:
            # Maybe update existing if changed?
            update_counterparty(cp_id, name, eik, addr, mol, "")

        # 3. Gather data for Word template
        data = {
            'date': self.proto_date.date().toString("dd.MM.yyyy"),
            'service_firm': get_setting('name', 'Д и Д Фискал Системс ЕООД'),
            'service_eik': get_setting('eik', '205634567'),
            'service_address': get_setting('address', 'гр. София, бул. България №1'),
            'service_mol': get_setting('mol', 'Александър Петров'),
            'tech_egn': self.tech_egn.text().strip(),
            'capacity': self.tech_capacity.text().strip(),
            'client_name': name,
            'client_eik': eik,
            'client_address': addr,
            'client_mol': mol,
            'description': self.proto_desc.toPlainText().strip(),
            'notes': self.proto_notes.text().strip(),
            'ref_number': self.proto_ref.text().strip()
        }
        
        # 4. Generate
        file_path = generate_handover_protocol(data)
        
        if file_path:
            # 5. Save record to DB
            proto_record = {
                'protocol_date': self.proto_date.date().toString("yyyy-MM-dd"),
                'technician_egn': data['tech_egn'],
                'capacity': data['capacity'],
                'counterparty_id': cp_id,
                'description': data['description'],
                'notes': data['notes'],
                'ref_number': data['ref_number'],
                'docx_path': file_path
            }
            add_handover_protocol(proto_record)
            
            QMessageBox.information(self, "Успех", f"Протоколът е генериран успешно:\n{file_path}\n\nФайлът ще бъде отворен автоматично.")
            
            # Open the file
            if os.path.exists(file_path):
                QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))
                
            self.accept()
        else:
            QMessageBox.critical(self, "Грешка", "Възникна грешка при генериране на Word документа!")
