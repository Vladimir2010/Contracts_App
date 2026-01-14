from PyQt6.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout,
    QComboBox, QMessageBox, QDateEdit, QCheckBox, QLabel, QTabWidget, QWidget,
    QFileDialog, QSpinBox, QCompleter
)
from PyQt6.QtCore import QDate, Qt
from vat_check import check_vat
from database import (
    get_all_certificates, add_client, add_device, get_client_by_contract,
    get_all_contract_numbers, update_device, get_device_full,
    get_next_contract_number
)
from export_excel import export_to_excel
from export_word import export_to_word
from export_pdf import export_to_pdf
from date_utils import format_date_bg, qdate_to_db, db_to_qdate
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
        
        # Add tabs
        tabs.addTab(client_tab, "Данни за клиент")
        tabs.addTab(device_tab, "Данни за устройство")
        
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
            flat_file = os.path.join(os.path.dirname(__file__), "bg_places_flat.json")
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
                'fiscal_memory': fiscal
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
        
        # Connect phone formatting
        self.phone1.editingFinished.connect(lambda: self.format_phone(self.phone1))
        self.phone2.editingFinished.connect(lambda: self.format_phone(self.phone2))
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
                'fiscal_memory': self.fiscal_memory.text().strip()
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
        
        # Add tabs
        tabs.addTab(client_tab, "Данни за клиент")
        tabs.addTab(device_tab, "Данни за устройство")
        
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
            flat_file = os.path.join(os.path.dirname(__file__), "bg_places_flat.json")
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
                'fiscal_memory': self.fiscal_memory.text().strip()
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
