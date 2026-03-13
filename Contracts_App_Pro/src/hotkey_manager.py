import keyboard
import threading
from PyQt6.QtCore import QObject, pyqtSignal

class HotkeyManager(QObject):
    """
    Manages global system-wide hotkeys.
    Uses 'keyboard' library which runs in its own thread.
    Emits a Qt signal when the hotkey is triggered to safely interact with the GUI thread.
    """
    hotkey_triggered = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False
        self._hotkeys = ["alt+d", "alt+д"] # Support both EN and BG layouts

    def start(self):
        """Register hotkeys and start listening"""
        if self._running:
            return
        
        for hk in self._hotkeys:
            try:
                keyboard.add_hotkey(hk, self._on_hotkey_pressed)
                print(f"HotkeyManager: Registered {hk}")
            except Exception as e:
                print(f"HotkeyManager: Could not register {hk}: {e}")
        
        self._running = True

    def stop(self):
        """Unregister all hotkeys"""
        if not self._running:
            return
            
        try:
            keyboard.unhook_all_hotkeys()
            self._running = False
            print("HotkeyManager: Stopped")
        except Exception as e:
            print(f"HotkeyManager: Error during stop: {e}")

    def _on_hotkey_pressed(self):
        """Internal callback called by 'keyboard' thread"""
        # Emit signal to be handled in the main Qt thread
        self.hotkey_triggered.emit()
