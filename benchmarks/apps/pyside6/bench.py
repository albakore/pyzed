"""Bench app: ROWS rows in a QScrollArea (see ../benchkit.py)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from benchkit import FOOTER, H, ROWS, TICK, W, A, Driver, color, label  # noqa: E402

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtGui import QColor, QPalette  # noqa: E402
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QLabel, QPushButton, QScrollArea,  # noqa: E402
                               QVBoxLayout, QWidget)

app = QApplication(sys.argv)
window = QWidget()
window.setWindowTitle("bench")
window.resize(W, H)
window.move(0, 0)
layout = QVBoxLayout(window)
layout.setContentsMargins(0, 0, 0, 0)
layout.setSpacing(0)
inner = QWidget()
rows = QVBoxLayout(inner)
labels = []
for i in range(ROWS):
    row = QHBoxLayout()
    text = QLabel(label(i, 0))
    row.addWidget(text, 1)
    row.addWidget(QPushButton("Open"))
    rows.addLayout(row)
    labels.append(text)
scroll = QScrollArea()
scroll.setWidgetResizable(True)
scroll.setWidget(inner)
layout.addWidget(scroll, 1)
footer = QWidget()
footer.setFixedHeight(FOOTER)
footer.setAutoFillBackground(True)


def paint(c):
    palette = footer.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(*c))
    footer.setPalette(palette)


paint(A)
layout.addWidget(footer)
driver = Driver()


def tick():
    k = driver.next()
    if k:
        for i, text in enumerate(labels):
            text.setText(label(i, k))
        paint(color(k))


timer = QTimer()
timer.timeout.connect(tick)
timer.start(int(TICK * 1000))
window.show()
app.exec()
