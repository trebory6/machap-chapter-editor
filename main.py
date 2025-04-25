import sys
from PySide6.QtWidgets import QApplication
from gui import ChapterEditor, KeyPressFilter

if __name__ == "__main__":
    app = QApplication(sys.argv)

    key_filter = KeyPressFilter(None)
    app.installEventFilter(key_filter)

    window = ChapterEditor()
    key_filter.editor = window

    window.resize(800, 600)
    window.show()
    sys.exit(app.exec())
