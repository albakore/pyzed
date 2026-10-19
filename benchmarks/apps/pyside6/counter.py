"""Reference app: a counter with -, + and Reset."""

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


class Counter(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Counter")
        self.resize(320, 200)
        self.count = 0
        self.label = QLabel("0", alignment=Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet("font-size: 24px")
        buttons = QHBoxLayout()
        for text, step in (("-", -1), ("+", 1), ("Reset", None)):
            button = QPushButton(text)
            button.clicked.connect(lambda _=False, s=step: self.change(s))
            buttons.addWidget(button)
        layout = QVBoxLayout(self)
        layout.addStretch()
        layout.addWidget(self.label)
        layout.addLayout(buttons)
        layout.addStretch()

    def change(self, step):
        self.count = 0 if step is None else self.count + step
        self.label.setText(str(self.count))


app = QApplication(sys.argv)
window = Counter()
window.show()
app.exec()
