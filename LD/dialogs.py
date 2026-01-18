from PyQt6.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout,
    QComboBox, QMessageBox, QDateEdit, QCheckBox, QLabel, QTabWidget, QWidget,
    QFileDialog, QSpinBox, QCompleter, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView
)
from PyQt6.QtCore import QDate, Qt
from vat_check import check_vat
from database import (
    get_all_certificates, add_client, add_device, get_client_by_contract,
    get_all_contract_numbers, update_device, get_device_full,
    get_next_contract_number, get_devices_for_nra_report
)
from export_excel import export_to_excel
from export_word import export_to_word
from export_pdf import export_to_pdf
from date_utils import format_date_bg, qdate_to_db, db_to_qdate
from datetime import datetime
import os
import json
import re


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
                'bim_date': self.bim_date.date().toString('yyyy-MM-dd')
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
                'bim_date': self.bim_date.date().toString('yyyy-MM-dd')
            }
            
            if update_device(self.device_id, client_data, device_data):
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
        else:
            count = len(self.current_data)
            self.status_label.setText(f"✅ Намерени {count} изтичащи договора за {month:02d}.{year}")
            self.btn_export_excel.setVisible(True)
            self.btn_export_word.setVisible(True)
            self.btn_export_pdf.setVisible(True)
            
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
        
        btn_exit = QPushButton("ИЗХОД")
        btn_exit.setObjectName("btnExit")
        btn_exit.clicked.connect(self.reject)
        btn_exit.setCursor(Qt.CursorShape.PointingHandCursor)
        
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
            self.lbl_error.setText(f"Грешно име или парола! Остават {remaining} опита.")
            self.password.clear()
            self.password.setFocus()
            
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
        
        self.tab_config.setLayout(layout)

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
        from path_utils import get_app_root
        settings_path = os.path.join(get_app_root(), "data", "settings.json")
        
        if os.path.exists(settings_path):
            import json
            try:
                with open(settings_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Service Firm
                    self.s_name.setText(data.get('name', ''))
                    self.s_eik.setText(data.get('eik', ''))
                    self.s_vat.setText(data.get('vat', ''))
                    self.s_city.setText(data.get('city', ''))
                    self.s_post.setText(data.get('post', ''))
                    self.s_addr.setText(data.get('address', ''))
                    self.s_mol.setText(data.get('mol', ''))
                    self.s_phone1.setText(data.get('phone1', ''))
                    self.s_phone2.setText(data.get('phone2', ''))
                    self.s_vat_reg.setChecked(data.get('vat_registered', False))
                    
                    # Tech (handle old keys 'tech_name1' vs new/restored 'tech_f')
                    self.s_tech_f.setText(data.get('tech_f', data.get('tech_name1', '')))
                    self.s_tech_m.setText(data.get('tech_m', data.get('tech_name2', '')))
                    self.s_tech_l.setText(data.get('tech_l', data.get('tech_name3', '')))
                    self.s_tech_egn.setText(data.get('tech_egn', ''))
            except Exception as e:
                print(f"Error loading settings: {e}")

    def save_settings(self):
        import json
        data = {
            # Service Firm
            'name': self.s_name.text().strip(),
            'eik': self.s_eik.text().strip(),
            'vat': self.s_vat.text().strip(),
            'city': self.s_city.text().strip(),
            'post': self.s_post.text().strip(),
            'address': self.s_addr.text().strip(),
            'mol': self.s_mol.text().strip(),
            'phone1': self.s_phone1.text().strip(),
            'phone2': self.s_phone2.text().strip(),
            'vat_registered': self.s_vat_reg.isChecked(),
            
            # Tech
            'tech_f': self.s_tech_f.text().strip(),
            'tech_m': self.s_tech_m.text().strip(),
            'tech_l': self.s_tech_l.text().strip(),
            'tech_egn': self.s_tech_egn.text().strip(),
            # Save as old keys too for compatibility if needed elsewhere
            'tech_name1': self.s_tech_f.text().strip(),
            'tech_name2': self.s_tech_m.text().strip(),
            'tech_name3': self.s_tech_l.text().strip()
        }
        
        from path_utils import get_app_root
        data_dir = os.path.join(get_app_root(), "data")
        os.makedirs(data_dir, exist_ok=True)
        
        try:
            with open(os.path.join(data_dir, "settings.json"), 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            QMessageBox.information(self, "Успех", "Настройките са запазени!")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Грешка", f"Грешка при запис:\n{e}")


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
