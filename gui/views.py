"""
Модуль views.py - візуальні компоненти GUI
Містить всі вікна та віджети інтерфейсу користувача
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
from typing import Optional, Callable, List, Tuple, Dict
import os

from models import ScaleType, ScaleManager


class StartWindow(tk.Frame):
    """
    Початкове вікно для створення нової експертизи або відкриття існуючої
    """

    def __init__(self, parent, on_new_project: Callable, on_open_project: Callable):
        super().__init__(parent)
        self.on_new_project = on_new_project
        self.on_open_project = on_open_project

        self._setup_ui()

    def _setup_ui(self):
        """Налаштування інтерфейсу"""
        # Заголовок
        title_label = tk.Label(
            self,
            text="Метод попарних порівнянь",
            font=("Arial", 20, "bold")
        )
        title_label.pack(pady=20)

        subtitle_label = tk.Label(
            self,
            text="з уточненням ступеня переваги",
            font=("Arial", 14)
        )
        subtitle_label.pack(pady=(0, 40))

        # Кнопки
        btn_frame = tk.Frame(self)
        btn_frame.pack(pady=20)

        new_btn = ttk.Button(
            btn_frame,
            text="Нова експертиза",
            command=self.on_new_project,
            width=25
        )
        new_btn.pack(pady=10)

        open_btn = ttk.Button(
            btn_frame,
            text="Відкрити існуючу...",
            command=self.on_open_project,
            width=25
        )
        open_btn.pack(pady=10)


class ProjectSetupWindow(tk.Frame):
    """
    Вікно налаштування проекту: альтернативи та експерти
    """

    def __init__(self, parent, on_start_comparison: Callable):
        super().__init__(parent)
        self.on_start_comparison = on_start_comparison

        self._setup_ui()

    def _setup_ui(self):
        """Налаштування інтерфейсу"""
        # Заголовок
        title_label = tk.Label(
            self,
            text="Налаштування експертизи",
            font=("Arial", 16, "bold")
        )
        title_label.pack(pady=20)

        # Секція альтернатив
        alt_frame = ttk.LabelFrame(self, text="Альтернативи", padding=10)
        alt_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        ttk.Label(alt_frame, text="Введіть альтернативи (одна на рядок):").pack(anchor=tk.W)

        self.alternatives_text = scrolledtext.ScrolledText(
            alt_frame,
            height=8,
            width=50
        )
        self.alternatives_text.pack(fill=tk.BOTH, expand=True, pady=5)

        # Кнопки завантаження
        btn_frame = tk.Frame(alt_frame)
        btn_frame.pack(fill=tk.X, pady=5)

        ttk.Button(
            btn_frame,
            text="Завантажити з CSV",
            command=self._load_from_csv
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            btn_frame,
            text="Приклад (4 альтернативи)",
            command=self._load_example
        ).pack(side=tk.LEFT, padx=5)

        # Секція експертів
        expert_frame = ttk.LabelFrame(self, text="Експерти", padding=10)
        expert_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Список експертів
        self.experts_list = []
        self.experts_listbox = tk.Listbox(expert_frame, height=5)
        self.experts_listbox.pack(fill=tk.BOTH, expand=True, pady=5)

        # Форма додавання експерта
        add_expert_frame = tk.Frame(expert_frame)
        add_expert_frame.pack(fill=tk.X, pady=5)

        ttk.Label(add_expert_frame, text="ID експерта:").pack(side=tk.LEFT, padx=5)
        self.expert_id_entry = ttk.Entry(add_expert_frame, width=20)
        self.expert_id_entry.pack(side=tk.LEFT, padx=5)

        ttk.Label(add_expert_frame, text="Компетентність (0-1):").pack(side=tk.LEFT, padx=5)
        self.expert_competence_entry = ttk.Entry(add_expert_frame, width=10)
        self.expert_competence_entry.insert(0, "1.0")
        self.expert_competence_entry.pack(side=tk.LEFT, padx=5)

        ttk.Button(
            add_expert_frame,
            text="Додати",
            command=self._add_expert
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            add_expert_frame,
            text="Видалити",
            command=self._remove_expert
        ).pack(side=tk.LEFT, padx=5)

        # Кнопка початку
        start_btn = ttk.Button(
            self,
            text="Почати порівняння",
            command=self._on_start,
            width=25
        )
        start_btn.pack(pady=20)

    def _load_from_csv(self):
        """Завантаження альтернатив з CSV"""
        filename = filedialog.askopenfilename(
            title="Відкрити CSV файл",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.alternatives_text.delete(1.0, tk.END)
                self.alternatives_text.insert(1.0, content)
            except Exception as e:
                messagebox.showerror("Помилка", f"Не вдалося завантажити файл:\n{e}")

    def _load_example(self):
        """Завантаження прикладу"""
        example = "Проект_A\nПроект_B\nПроект_C\nПроект_D"
        self.alternatives_text.delete(1.0, tk.END)
        self.alternatives_text.insert(1.0, example)

        # Додати приклад експертів
        self.experts_list = [
            ("Експерт_1", 0.85),
            ("Експерт_2", 0.60)
        ]
        self._update_experts_listbox()

    def _add_expert(self):
        """Додати експерта"""
        expert_id = self.expert_id_entry.get().strip()
        if not expert_id:
            messagebox.showwarning("Увага", "Введіть ID експерта")
            return

        try:
            competence = float(self.expert_competence_entry.get())
            if not 0 <= competence <= 1:
                raise ValueError()
        except ValueError:
            messagebox.showerror("Помилка", "Компетентність має бути числом від 0 до 1")
            return

        self.experts_list.append((expert_id, competence))
        self._update_experts_listbox()

        # Очистити поля
        self.expert_id_entry.delete(0, tk.END)
        self.expert_competence_entry.delete(0, tk.END)
        self.expert_competence_entry.insert(0, "1.0")

    def _remove_expert(self):
        """Видалити експерта"""
        selection = self.experts_listbox.curselection()
        if selection:
            idx = selection[0]
            self.experts_list.pop(idx)
            self._update_experts_listbox()

    def _update_experts_listbox(self):
        """Оновити список експертів"""
        self.experts_listbox.delete(0, tk.END)
        for expert_id, competence in self.experts_list:
            self.experts_listbox.insert(tk.END, f"{expert_id} (компетентність: {competence:.2f})")

    def _on_start(self):
        """Обробник кнопки початку"""
        # Отримати альтернативи
        alternatives_text = self.alternatives_text.get(1.0, tk.END)
        alternatives = [line.strip() for line in alternatives_text.split('\n') if line.strip()]

        if len(alternatives) < 2:
            messagebox.showerror("Помилка", "Потрібно принаймні 2 альтернативи")
            return

        if len(self.experts_list) < 1:
            messagebox.showerror("Помилка", "Потрібно принаймні 1 експерт")
            return

        # Повернути дані
        expert_ids = [expert_id for expert_id, _ in self.experts_list]
        competence_coefficients = {expert_id: comp for expert_id, comp in self.experts_list}

        self.on_start_comparison(alternatives, expert_ids, competence_coefficients)

    def get_data(self) -> Optional[Tuple[List[str], List[str], Dict[str, float]]]:
        """Отримати дані проекту"""
        alternatives_text = self.alternatives_text.get(1.0, tk.END)
        alternatives = [line.strip() for line in alternatives_text.split('\n') if line.strip()]

        if len(alternatives) < 2 or len(self.experts_list) < 1:
            return None

        expert_ids = [expert_id for expert_id, _ in self.experts_list]
        competence_coefficients = {expert_id: comp for expert_id, comp in self.experts_list}

        return alternatives, expert_ids, competence_coefficients


class ComparisonWindow(tk.Frame):
    """
    Головне вікно парних порівнянь з вибором шкали та уточненням
    """

    def __init__(self, parent, on_judgment: Callable, on_skip: Callable,
                 on_back: Callable, on_finish: Callable):
        super().__init__(parent)
        self.on_judgment = on_judgment
        self.on_skip = on_skip
        self.on_back = on_back
        self.on_finish = on_finish

        self.current_pair: Optional[Tuple[str, str]] = None
        self.current_expert: str = ""
        self.current_scale: ScaleType = ScaleType.SAATY_9
        self.current_gradations: int = 9

        self._setup_ui()

    def _setup_ui(self):
        """Налаштування інтерфейсу"""
        # Шапка з інформацією
        header_frame = tk.Frame(self, bg="#e0e0e0")
        header_frame.pack(fill=tk.X, pady=(0, 10))

        self.expert_label = tk.Label(
            header_frame,
            text="Експерт: -",
            font=("Arial", 12),
            bg="#e0e0e0"
        )
        self.expert_label.pack(side=tk.LEFT, padx=20, pady=10)

        self.progress_label = tk.Label(
            header_frame,
            text="Прогрес: 0/0",
            font=("Arial", 12),
            bg="#e0e0e0"
        )
        self.progress_label.pack(side=tk.RIGHT, padx=20, pady=10)

        # Поточна пара
        pair_frame = tk.Frame(self)
        pair_frame.pack(pady=20)

        ttk.Label(
            pair_frame,
            text="Порівняння:",
            font=("Arial", 14)
        ).pack()

        self.pair_label = tk.Label(
            pair_frame,
            text="А vs Б",
            font=("Arial", 18, "bold"),
            fg="#0066cc"
        )
        self.pair_label.pack(pady=10)

        # Вибір шкали
        scale_frame = ttk.LabelFrame(self, text="Вибір шкали", padding=10)
        scale_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Label(scale_frame, text="Тип шкали:").pack(side=tk.LEFT, padx=5)

        self.scale_var = tk.StringVar(value="Сааті-9 (9 градацій)")
        self.scale_combo = ttk.Combobox(
            scale_frame,
            textvariable=self.scale_var,
            state="readonly",
            width=30
        )

        # Заповнюємо доступні шкали
        scales = ScaleManager.get_available_scales()
        scale_options = [f"{desc}" for scale_type, desc in scales]
        self.scale_combo['values'] = scale_options
        self.scale_combo.current(2)  # Сааті-9 за замовчуванням
        self.scale_combo.bind('<<ComboboxSelected>>', self._on_scale_change)
        self.scale_combo.pack(side=tk.LEFT, padx=5)

        # Slider з градаціями
        slider_frame = ttk.LabelFrame(self, text="Оцінка переваги", padding=10)
        slider_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Мітка градації
        self.gradation_label = tk.Label(
            slider_frame,
            text="Рівноцінні",
            font=("Arial", 14, "bold")
        )
        self.gradation_label.pack(pady=10)

        # Slider
        self.slider = ttk.Scale(
            slider_frame,
            from_=0,
            to=8,
            orient=tk.HORIZONTAL,
            command=self._on_slider_change
        )
        self.slider.set(4)  # Середина
        self.slider.pack(fill=tk.X, padx=20, pady=10)

        # Числове значення
        self.value_label = tk.Label(
            slider_frame,
            text="Значення: 5",
            font=("Arial", 12)
        )
        self.value_label.pack(pady=5)

        # Підказка інформативності
        self.info_label = tk.Label(
            slider_frame,
            text="Інформативність: 3.17 біт",
            font=("Arial", 10),
            fg="gray"
        )
        self.info_label.pack(pady=5)

        # Кнопка уточнення
        refine_btn = ttk.Button(
            slider_frame,
            text="Уточнити ступінь (збільшити детальність)",
            command=self._on_refine
        )
        refine_btn.pack(pady=10)

        # Кнопки навігації
        nav_frame = tk.Frame(self)
        nav_frame.pack(pady=20)

        ttk.Button(
            nav_frame,
            text="← Назад",
            command=self.on_back,
            width=15
        ).pack(side=tk.LEFT, padx=10)

        ttk.Button(
            nav_frame,
            text="Пропустити",
            command=self.on_skip,
            width=15
        ).pack(side=tk.LEFT, padx=10)

        ttk.Button(
            nav_frame,
            text="Підтвердити →",
            command=self._on_confirm,
            width=15
        ).pack(side=tk.LEFT, padx=10)

        # Bind клавіші
        self.master.bind('<Left>', lambda e: self._adjust_slider(-1))
        self.master.bind('<Right>', lambda e: self._adjust_slider(1))
        self.master.bind('<Return>', lambda e: self._on_confirm())

        self._update_scale_info()

    def _on_scale_change(self, event=None):
        """Обробник зміни шкали"""
        scale_text = self.scale_var.get()

        # Визначаємо тип шкали
        scales = ScaleManager.get_available_scales()
        for scale_type, desc in scales:
            if desc in scale_text:
                self.current_scale = scale_type
                min_grad, max_grad = ScaleManager.get_scale_gradations_range(scale_type)
                self.current_gradations = max_grad
                break

        self._update_scale_info()

    def _on_slider_change(self, value):
        """Обробник зміни слайдера"""
        self._update_scale_info()

    def _adjust_slider(self, delta: int):
        """Зміна значення слайдера клавішами"""
        current = self.slider.get()
        new_value = max(0, min(self.current_gradations - 1, current + delta))
        self.slider.set(new_value)
        self._update_scale_info()

    def _update_scale_info(self):
        """Оновлює інформацію про поточну градацію"""
        from scales import get_scale_values, calculate_informativeness

        # Отримуємо поточний індекс
        grade_index = int(self.slider.get())

        # Налаштовуємо slider
        self.slider.configure(to=self.current_gradations - 1)

        # Отримуємо значення
        values = get_scale_values(self.current_scale, self.current_gradations)
        if grade_index < len(values):
            value = values[grade_index]
        else:
            value = 1.0

        # Лінгвістична мітка
        label = ScaleManager.get_linguistic_label(
            self.current_scale,
            self.current_gradations,
            grade_index
        )
        self.gradation_label.config(text=label)

        # Числове значення
        self.value_label.config(text=f"Значення: {value:.2f}")

        # Інформативність
        informativeness = calculate_informativeness(self.current_gradations)
        self.info_label.config(
            text=f"Інформативність шкали: {informativeness:.2f} біт ({self.current_gradations} градацій)"
        )

    def _on_refine(self):
        """Уточнення ступеня переваги (збільшення детальності)"""
        refinement = ScaleManager.suggest_scale_refinement(
            self.current_scale,
            self.current_gradations
        )

        if refinement:
            new_scale, new_gradations = refinement
            response = messagebox.askyesno(
                "Уточнення шкали",
                f"Перейти до шкали з {new_gradations} градаціями для більшої точності?"
            )

            if response:
                self.current_scale = new_scale
                self.current_gradations = new_gradations
                self._update_scale_info()
        else:
            messagebox.showinfo(
                "Уточнення",
                "Досягнуто максимальної детальності для цієї шкали"
            )

    def _on_confirm(self):
        """Підтвердження оцінки"""
        from scales import get_scale_values

        grade_index = int(self.slider.get())
        values = get_scale_values(self.current_scale, self.current_gradations)

        if grade_index < len(values):
            value = values[grade_index]
            self.on_judgment(value, self.current_scale, self.current_gradations)

    def update_comparison(self, pair: Tuple[str, str], expert: str,
                         progress: Tuple[int, int]):
        """Оновлює відображення поточного порівняння"""
        self.current_pair = pair
        self.current_expert = expert

        self.pair_label.config(text=f"{pair[0]} vs {pair[1]}")
        self.expert_label.config(text=f"Експерт: {expert}")
        self.progress_label.config(text=f"Прогрес: {progress[0]}/{progress[1]}")

        # Скидаємо slider на середину
        self.slider.set(self.current_gradations // 2)
        self._update_scale_info()


class ResultsWindow(tk.Frame):
    """
    Вікно результатів з вагами, узгодженістю та рекомендаціями
    """

    def __init__(self, parent, on_export: Callable, on_save_session: Callable,
                 on_new: Callable):
        super().__init__(parent)
        self.on_export = on_export
        self.on_save_session = on_save_session
        self.on_new = on_new

        self._setup_ui()

    def _setup_ui(self):
        """Налаштування інтерфейсу"""
        # Заголовок
        title_label = tk.Label(
            self,
            text="Результати експертизи",
            font=("Arial", 16, "bold")
        )
        title_label.pack(pady=20)

        # Notebook з вкладками
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Вкладка: Ваги та ранжування
        weights_frame = tk.Frame(self.notebook)
        self.notebook.add(weights_frame, text="Ваги та ранжування")
        self._setup_weights_tab(weights_frame)

        # Вкладка: Узгодженість
        consistency_frame = tk.Frame(self.notebook)
        self.notebook.add(consistency_frame, text="Узгодженість")
        self._setup_consistency_tab(consistency_frame)

        # Вкладка: Рекомендації
        suggestions_frame = tk.Frame(self.notebook)
        self.notebook.add(suggestions_frame, text="Рекомендації")
        self._setup_suggestions_tab(suggestions_frame)

        # Кнопки експорту
        export_frame = tk.Frame(self)
        export_frame.pack(pady=20)

        ttk.Button(
            export_frame,
            text="Експорт результатів",
            command=self.on_export,
            width=20
        ).pack(side=tk.LEFT, padx=10)

        ttk.Button(
            export_frame,
            text="Зберегти сесію",
            command=self.on_save_session,
            width=20
        ).pack(side=tk.LEFT, padx=10)

        ttk.Button(
            export_frame,
            text="Нова експертиза",
            command=self.on_new,
            width=20
        ).pack(side=tk.LEFT, padx=10)

    def _setup_weights_tab(self, parent):
        """Налаштування вкладки ваг"""
        # Таблиця ранжування
        columns = ('rank', 'alternative', 'weight')
        self.weights_tree = ttk.Treeview(parent, columns=columns, show='headings', height=10)

        self.weights_tree.heading('rank', text='Ранг')
        self.weights_tree.heading('alternative', text='Альтернатива')
        self.weights_tree.heading('weight', text='Вага')

        self.weights_tree.column('rank', width=80, anchor=tk.CENTER)
        self.weights_tree.column('alternative', width=300)
        self.weights_tree.column('weight', width=150, anchor=tk.CENTER)

        self.weights_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Scrollbar
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.weights_tree.yview)
        self.weights_tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _setup_consistency_tab(self, parent):
        """Налаштування вкладки узгодженості"""
        info_frame = tk.Frame(parent)
        info_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        self.consistency_text = scrolledtext.ScrolledText(
            info_frame,
            height=15,
            width=60,
            font=("Courier", 10)
        )
        self.consistency_text.pack(fill=tk.BOTH, expand=True)

    def _setup_suggestions_tab(self, parent):
        """Налаштування вкладки рекомендацій"""
        self.suggestions_text = scrolledtext.ScrolledText(
            parent,
            height=15,
            width=60
        )
        self.suggestions_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def display_results(self, results: Dict):
        """Відображає результати"""
        # Ваги та ранжування
        self.weights_tree.delete(*self.weights_tree.get_children())
        for item in results['ranking']:
            self.weights_tree.insert('', tk.END, values=(
                item['rank'],
                item['alternative'],
                f"{item['weight']:.4f}"
            ))

        # Узгодженість
        consistency = results['consistency']
        self.consistency_text.delete(1.0, tk.END)

        text = f"""
ПОКАЗНИКИ УЗГОДЖЕНОСТІ

Максимальне власне значення (λ_max): {consistency['lambda_max']:.4f}
Індекс узгодженості (CI):             {consistency['CI']:.4f}
Відношення узгодженості (CR):         {consistency['CR']:.4f}
Випадковий індекс (RI):                {consistency['RI']:.2f}

Поріг узгодженості:                    {consistency['threshold']:.2f}
Результат:                             {'✓ УЗГОДЖЕНА' if consistency['is_consistent'] else '✗ НЕУЗГОДЖЕНА'}

"""
        if consistency['is_consistent']:
            text += "\nМатриця попарних порівнянь є достатньо узгодженою.\n"
            text += "Результати можна використовувати для прийняття рішень.\n"
        else:
            text += "\nМатриця має високу неузгодженість!\n"
            text += "Рекомендується переглянути оцінки (дивіться вкладку 'Рекомендації').\n"

        self.consistency_text.insert(1.0, text)

        # Колір індикатора
        if consistency['is_consistent']:
            self.consistency_text.tag_add("good", "7.0", "7.end")
            self.consistency_text.tag_config("good", foreground="green", font=("Courier", 10, "bold"))
        else:
            self.consistency_text.tag_add("bad", "7.0", "7.end")
            self.consistency_text.tag_config("bad", foreground="red", font=("Courier", 10, "bold"))

        # Рекомендації
        self.suggestions_text.delete(1.0, tk.END)
        suggestions = results['suggestions']

        if not suggestions:
            self.suggestions_text.insert(
                1.0,
                "Рекомендацій немає.\nМатриця попарних порівнянь є узгодженою."
            )
        else:
            text = "РЕКОМЕНДАЦІЇ ДЛЯ ПОКРАЩЕННЯ УЗГОДЖЕНОСТІ\n\n"
            text += f"Знайдено {len(suggestions)} порівнянь з найбільшими відхиленнями:\n\n"

            for i, sugg in enumerate(suggestions, 1):
                text += f"{i}. {sugg['comparison']}\n"
                text += f"   Поточне значення:     {sugg['current_value']:.2f}\n"
                text += f"   Рекомендоване значення: {sugg['suggested_value']:.2f}\n"
                text += f"   Відхилення:           {sugg['deviation_percent']:.1f}%\n\n"

            self.suggestions_text.insert(1.0, text)
