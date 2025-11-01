#!/usr/bin/env python3
"""
app.py - Головний файл запуску GUI застосунку
Метод експертних попарних порівнянь з уточненням ступеня переваги

Використання:
    python -m gui.app
    або
    python gui/app.py
"""

import tkinter as tk
from tkinter import ttk
import sys
import os

# Додаємо батьківську директорію до шляху пошуку модулів
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gui.controllers import MainController


def main():
    """Головна функція запуску застосунку"""
    # Створюємо головне вікно
    root = tk.Tk()

    # Встановлюємо іконку (якщо є)
    # root.iconbitmap('assets/icon.ico')

    # Встановлюємо стиль
    style = ttk.Style()
    style.theme_use('clam')  # Сучасний вигляд

    # Створюємо головний контролер
    controller = MainController(root)

    # Обробник закриття вікна
    def on_closing():
        if tk.messagebox.askokcancel("Вихід", "Ви дійсно хочете вийти?"):
            root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)

    # Запускаємо головний цикл
    root.mainloop()


if __name__ == "__main__":
    main()
