"""Reference app: add tasks (button or Enter), tick them off, delete them, see how many are left."""

import sys

from PySide6.QtWidgets import (QApplication, QCheckBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea,
                               QVBoxLayout, QWidget)


class Todo(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("To-do")
        self.resize(420, 480)
        self.tasks = []  # [title, done]
        self.left = QLabel()
        self.left.setStyleSheet("font-size: 16px; font-weight: bold")
        self.entry = QLineEdit()
        self.entry.returnPressed.connect(self.add)
        add = QPushButton("Add")
        add.clicked.connect(self.add)
        entry_row = QHBoxLayout()
        entry_row.addWidget(self.entry)
        entry_row.addWidget(add)
        self.list = QVBoxLayout()
        inner = QWidget()
        column = QVBoxLayout(inner)
        column.addLayout(self.list)
        column.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(inner)
        layout = QVBoxLayout(self)
        layout.addWidget(self.left)
        layout.addLayout(entry_row)
        layout.addWidget(scroll)
        self.refresh()

    def add(self):
        if self.entry.text().strip():
            self.tasks.append([self.entry.text().strip(), False])
            self.entry.clear()
            self.refresh()

    def toggle(self, task, done):
        task[1] = done
        self.refresh()

    def remove(self, task):
        self.tasks.remove(task)
        self.refresh()

    def refresh(self):
        while self.list.count():
            item = self.list.takeAt(0)
            item.widget().deleteLater()
        for task in self.tasks:
            row = QWidget()
            line = QHBoxLayout(row)
            check = QCheckBox(task[0])
            check.setChecked(task[1])
            check.toggled.connect(lambda done, t=task: self.toggle(t, done))
            delete = QPushButton("Delete")
            delete.clicked.connect(lambda _=False, t=task: self.remove(t))
            line.addWidget(check, 1)
            line.addWidget(delete)
            self.list.addWidget(row)
        self.left.setText(f"{sum(not done for _, done in self.tasks)} left")


app = QApplication(sys.argv)
window = Todo()
window.show()
app.exec()
