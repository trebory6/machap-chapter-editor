import sys
from PySide6.QtWidgets import QApplication
from gui import ChapterEditor

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ChapterEditor()
    window.resize(800, 600)
    window.show()
    sys.exit(app.exec())
