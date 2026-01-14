import sys
import os

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTableWidget, QTableWidgetItem,
    QPushButton, QVBoxLayout, QWidget, QHBoxLayout, QLineEdit,
    QCheckBox, QMessageBox, QFileDialog, QStatusBar, QMenu, QToolBar
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction

from database import (
    init_db, get_all_devices, search_devices, delete_device,
    get_client_by_contract, get_devices_by_contract
)
from contract_generator import generate_service_contract
from dialogs import (
    AddDeviceDialog, EditDeviceDialog, AddToExistingContractDialog,
    ExpiringContractsDialog
)
from importer import import_contracts_simple
from bim_loader import load_certificates_safe
from date_utils import format_date_bg


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
        self.table.setColumnCount(13)
        self.table.setHorizontalHeaderLabels([
            "ID", "№ Договор", "Статус", "Фирма", "ЕИК", "Адрес", "Адрес на обект", "Модел",
            "Сериен №", "Изтичане", "Евро", "Град", "Телефон"
        ])
        
        # Hide ID column
        self.table.setColumnHidden(0, True)
        
        # Enable sorting
        self.table.setSortingEnabled(True)
        
        # Set column widths
        self.table.setColumnWidth(1, 80)   # Contract
        self.table.setColumnWidth(2, 80)   # Status
        self.table.setColumnWidth(3, 220)  # Company
        self.table.setColumnWidth(4, 90)   # EIK
        self.table.setColumnWidth(5, 200)  # Address
        self.table.setColumnWidth(6, 200)  # Object Address
        self.table.setColumnWidth(7, 120)  # Model
        self.table.setColumnWidth(8, 100)  # Serial
        self.table.setColumnWidth(9, 90)   # Expiry
        self.table.setColumnWidth(10, 50)  # Euro
        self.table.setColumnWidth(11, 80)  # City
        self.table.setColumnWidth(12, 100) # Phone
        
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
    
    def create_toolbar(self):
        """Create application toolbar"""
        toolbar = QToolBar("Главна лента")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        
        # Add device
        action_add = QAction("➕ Ново устройство", self)
        action_add.triggered.connect(self.add_device)
        toolbar.addAction(action_add)
        
        # Add to existing contract
        action_add_existing = QAction("➕ Към съществуващ договор", self)
        action_add_existing.triggered.connect(self.add_to_existing_contract)
        toolbar.addAction(action_add_existing)
        
        toolbar.addSeparator()
        
        # Edit
        action_edit = QAction("✏️ Редактиране", self)
        action_edit.triggered.connect(self.edit_selected_device)
        toolbar.addAction(action_edit)

        # Generate Contract
        action_contract = QAction("📜 Издай договор", self)
        action_contract.triggered.connect(self.generate_selected_contract)
        toolbar.addAction(action_contract)
        
        # Delete
        action_delete = QAction("🗑️ Изтриване", self)
        action_delete.triggered.connect(self.delete_selected_device)
        toolbar.addAction(action_delete)
        
        toolbar.addSeparator()
        
        # Expiring contracts
        action_expiring = QAction("📄 Изтичащи договори", self)
        action_expiring.triggered.connect(self.show_expiring_contracts)
        toolbar.addAction(action_expiring)
        
        toolbar.addSeparator()
        
        # Import from Excel
        action_import = QAction("📥 Импорт от Excel", self)
        action_import.triggered.connect(self.import_from_excel)
        toolbar.addAction(action_import)
        
        # Load certificates
        action_load_certs = QAction("📋 Зареди сертификати", self)
        action_load_certs.triggered.connect(self.load_certificates)
        toolbar.addAction(action_load_certs)
        
        toolbar.addSeparator()
        
        # Refresh
        action_refresh = QAction("🔄 Обнови", self)
        action_refresh.triggered.connect(self.refresh_table)
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
            self.table.setColumnCount(13)
            self.table.setHorizontalHeaderLabels([
                "ID", "№ Договор", "Статус", "Фирма", "ЕИК", "Адрес", "Адрес на обект", "Модел",
                "Сериен №", "Изтичане", "Евро", "Град", "Телефон"
            ])
            self.table.setColumnHidden(0, True)
        
        for row_data in data:
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            for col, value in enumerate(row_data):
                display_value = ""
                
                # Euro column
                if not expiring_mode and col == 10:
                    display_value = "э" if value else ""
                
                # Expiry date column (9 in normal mode, 4 in expiring mode)
                elif (not expiring_mode and col == 9) or (expiring_mode and col == 4):
                    display_value = format_date_bg(value)
                
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
        delete_action = menu.addAction("🗑️ Изтриване")
        
        menu.addSeparator()
        
        # New copy actions
        copy_cell_action = menu.addAction("📋 Копирай клетка")
        copy_row_action = menu.addAction("📄 Копирай ред")
        
        action = menu.exec(self.table.viewport().mapToGlobal(position))
        
        if action == edit_action:
            self.edit_selected_device()
        elif action == contract_action:
            self.generate_selected_contract()
        elif action == delete_action:
            self.delete_selected_device()
        elif action == copy_cell_action:
            self.copy_cell_to_clipboard(index.row(), index.column())
        elif action == copy_row_action:
            self.copy_row_to_clipboard(index.row())

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
                self,
                "Потвърждение",
                "Импортът ще добави данните от файла в базата данни.\nПродължаване?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.statusBar.showMessage("Импортиране...")
                result = import_contracts_simple(filename)
                QMessageBox.information(self, "Импорт", result)
                self.refresh_table()
    
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

            template_path = "1 Профинанс Д и Д ЕООД.doc"
            
            # Use generator
            from contract_generator import generate_service_contract
            output_file = generate_service_contract(client_data, devices, template_path, save_dir)
            
            QMessageBox.information(self, "Успех", f"Договорът беше генериран успешно:\n{output_file}")
            
            # Open the folder
            if os.path.exists(save_dir):
                os.startfile(save_dir)

        except Exception as e:
            QMessageBox.critical(self, "Грешка", f"Грешка при генериране на договор: {str(e)}")


def main():
    # Ensure data directory exists
    os.makedirs("data", exist_ok=True)
    
    # Initialize database
    init_db()
    
    # Create application
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle('Fusion')
    
    # Create and show main window
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
