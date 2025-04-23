import sys
from PySide6.QtWidgets import QApplication
from gui import ChapterEditor, KeyPressFilter  # ✅ import KeyPressFilter too

if __name__ == "__main__":
    app = QApplication(sys.argv)

    key_filter = KeyPressFilter(None)           # ✅ Create event filter with no editor yet
    app.installEventFilter(key_filter)          # ✅ Install globally

    window = ChapterEditor()
    key_filter.editor = window                  # ✅ Link it to the main window

    window.resize(800, 600)
    window.show()
    sys.exit(app.exec())
