import sys
import os
import zipfile
import shutil
import threading
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QLineEdit, QPushButton, QFileDialog, QProgressBar, 
    QMessageBox, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtGui import QIcon, QPixmap, QFont
from win32com.client import Dispatch

# Internal App data
APP_NAME = "ContractsAppPro"
ZIP_NAME = "ContractsAppPro.zip"
EXE_NAME = "ContractsAppPro.exe"
LOG_NAME = "vladpos_logo.png"

class InstallWorker(QObject):
    finished = pyqtSignal(bool, str)
    progress = pyqtSignal(int, str)

    def __init__(self, zip_path, target_dir):
        super().__init__()
        self.zip_path = zip_path
        self.target_dir = target_dir

    def run(self):
        try:
            # 1. Cleanup old if exists
            if os.path.exists(self.target_dir):
                self.progress.emit(10, "Почистване на съществуваща инсталация...")
                # Use a small delay/retry logic if files are locked? 
                # For now just rmtree
                try:
                    shutil.rmtree(self.target_dir)
                except Exception as e:
                    self.finished.emit(False, f"Неуспешно изтриване на стара версия. Проверете дали програмата е затворена.\n{e}")
                    return

            os.makedirs(self.target_dir, exist_ok=True)

            # 2. Extract
            self.progress.emit(20, "Разархивиране на файлове...")
            with zipfile.ZipFile(self.zip_path, 'r') as zip_ref:
                all_files = zip_ref.namelist()
                total = len(all_files)
                for i, file in enumerate(all_files):
                    zip_ref.extract(file, self.target_dir)
                    if i % 50 == 0: # Update progress every 50 files
                        p = int(20 + (i / total) * 70)
                        self.progress.emit(p, f"Разархивиране: {file}")
            
            # 3. Shortcut
            self.progress.emit(95, "Създаване на пряк път...")
            self.create_shortcut()
            
            self.progress.emit(100, "Инсталацията завършена!")
            self.finished.emit(True, "SUCCESS")

        except Exception as e:
            self.finished.emit(False, str(e))

    def create_shortcut(self):
        try:
            shell = Dispatch('WScript.Shell')
            desktop = shell.SpecialFolders("Desktop")
            shortcut_path = os.path.join(desktop, "Contracts App Pro.lnk")
            target_exe = os.path.join(self.target_dir, EXE_NAME)
            icon_path = os.path.join(self.target_dir, "resources", LOG_NAME)
            
            if not os.path.exists(icon_path):
                icon_path = target_exe # Fallback

            shortcut = shell.CreateShortCut(shortcut_path)
            shortcut.Targetpath = target_exe
            shortcut.WorkingDirectory = self.target_dir
            # Use the icon embedded in the EXE (index 0)
            shortcut.IconLocation = f"{target_exe},0"
            shortcut.save()
        except Exception:
            pass

class InstallerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Инсталатор - Contracts App Pro")
        self.setFixedSize(500, 400)
        
        # Icon
        self.res_path = os.path.join("Contracts_App_Pro", "resources", LOG_NAME)
        if os.path.exists(self.res_path):
            self.setWindowIcon(QIcon(self.res_path))

        self.init_ui()

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(15)

        # Header with Logo
        header_layout = QHBoxLayout()
        if os.path.exists(self.res_path):
            logo_label = QLabel()
            pix = QPixmap(self.res_path).scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            logo_label.setPixmap(pix)
            header_layout.addWidget(logo_label)
        
        title_label = QLabel("Contracts App Pro\nИнсталационен съветник")
        title_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

        # Path selection
        path_label = QLabel("Изберете папка за инсталация:")
        path_label.setFont(QFont("Segoe UI", 10))
        layout.addWidget(path_label)

        self.path_edit = QLineEdit()
        default_path = os.path.join(os.environ['LOCALAPPDATA'], APP_NAME)
        self.path_edit.setText(default_path)
        
        path_btn_layout = QHBoxLayout()
        path_btn_layout.addWidget(self.path_edit)
        
        self.browse_btn = QPushButton("📂 Избор...")
        self.browse_btn.clicked.connect(self.browse_path)
        path_btn_layout.addWidget(self.browse_btn)
        layout.addLayout(path_btn_layout)

        layout.addStretch()

        # Progress
        self.progress_label = QLabel("Готовност за старт")
        self.progress_label.hide()
        layout.addWidget(self.progress_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        # Install button
        self.install_btn = QPushButton("⬇️ ИНСТАЛИРАЙ")
        self.install_btn.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.install_btn.setFixedHeight(45)
        self.install_btn.setStyleSheet("background-color: #28a745; color: white; border-radius: 5px;")
        self.install_btn.clicked.connect(self.start_installation)
        layout.addWidget(self.install_btn)

    def browse_path(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Изберете папка")
        if dir_path:
            # Append App Name if not present?
            if not dir_path.endswith(APP_NAME):
                dir_path = os.path.join(dir_path, APP_NAME)
            self.path_edit.setText(dir_path)

    def start_installation(self):
        target = self.path_edit.text().strip()
        if not target:
            QMessageBox.warning(self, "Грешка", "Моля изберете валидна папка.")
            return

        # Check if zip exists
        zip_path = ZIP_NAME
        if not os.path.exists(zip_path):
            # Try to find it next to exe if frozen
            if hasattr(sys, '_MEIPASS'):
                pass # Usually it's external though
            
        if not os.path.exists(zip_path):
            QMessageBox.critical(self, "Грешка", f"Файлът {ZIP_NAME} не бе намерен!")
            return

        # UI State
        self.install_btn.setEnabled(False)
        self.browse_btn.setEnabled(False)
        self.path_edit.setEnabled(False)
        self.progress_bar.show()
        self.progress_label.show()
        
        # Start work
        self.worker = InstallWorker(zip_path, target)
        self.thread = threading.Thread(target=self.worker.run)
        
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.installation_done)
        
        self.thread.start()

    def update_progress(self, val, msg):
        self.progress_bar.setValue(val)
        self.progress_label.setText(msg)

    def installation_done(self, success, error_msg):
        if success:
            QMessageBox.information(self, "Успех", "Инсталацията завърши успешно!\nМожете да стартирате програмата от десктопа.")
            self.close()
        else:
            QMessageBox.critical(self, "Грешка", f"Възникна грешка по време на инсталацията:\n{error_msg}")
            self.install_btn.setEnabled(True)
            self.browse_btn.setEnabled(True)
            self.path_edit.setEnabled(True)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = InstallerWindow()
    window.show()
    sys.exit(app.exec())
