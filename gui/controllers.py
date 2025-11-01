"""
Модуль controllers.py - контролери для зв'язку UI та бізнес-логіки
Реалізує MVC паттерн для GUI застосунку
"""

import tkinter as tk
from tkinter import messagebox, filedialog
from typing import Optional, Dict, List, Tuple
import json
import os
import csv

from models import SessionModel, Judgment, ScaleType, ScaleManager
from views import StartWindow, ProjectSetupWindow, ComparisonWindow, ResultsWindow


class MainController:
    """
    Головний контролер застосунку.
    Керує навігацією між вікнами та глобальним станом.
    """

    def __init__(self, root: tk.Tk):
        self.root = root
        self.session: Optional[SessionModel] = None
        self.current_frame: Optional[tk.Frame] = None

        # Налаштування вікна
        self.root.title("Метод попарних порівнянь з уточненням переваг")
        self.root.geometry("900x700")

        # Показуємо стартове вікно
        self.show_start_window()

    def show_start_window(self):
        """Показати стартове вікно"""
        self._clear_frame()

        frame = StartWindow(
            self.root,
            on_new_project=self.on_new_project,
            on_open_project=self.on_open_project
        )
        frame.pack(fill=tk.BOTH, expand=True)
        self.current_frame = frame

    def show_project_setup(self):
        """Показати вікно налаштування проекту"""
        self._clear_frame()

        frame = ProjectSetupWindow(
            self.root,
            on_start_comparison=self.on_start_comparison
        )
        frame.pack(fill=tk.BOTH, expand=True)
        self.current_frame = frame

    def show_comparison_window(self):
        """Показати вікно парних порівнянь"""
        self._clear_frame()

        frame = ComparisonWindow(
            self.root,
            on_judgment=self.on_judgment,
            on_skip=self.on_skip,
            on_back=self.on_back,
            on_finish=self.show_results
        )
        frame.pack(fill=tk.BOTH, expand=True)
        self.current_frame = frame

        # Оновити відображення першого порівняння
        self._update_comparison_display()

    def show_results(self):
        """Показати вікно результатів"""
        if not self.session:
            return

        # Обчислити результати
        try:
            results = self.session.calculate_results()
        except Exception as e:
            messagebox.showerror("Помилка", f"Не вдалося обчислити результати:\n{e}")
            return

        self._clear_frame()

        frame = ResultsWindow(
            self.root,
            on_export=lambda: self.on_export_results(results),
            on_save_session=self.on_save_session,
            on_new=self.on_new_project
        )
        frame.pack(fill=tk.BOTH, expand=True)
        self.current_frame = frame

        # Відобразити результати
        frame.display_results(results)

    def _clear_frame(self):
        """Очистити поточне вікно"""
        if self.current_frame:
            self.current_frame.destroy()
            self.current_frame = None

    def _update_comparison_display(self):
        """Оновити відображення поточного порівняння"""
        if not isinstance(self.current_frame, ComparisonWindow) or not self.session:
            return

        pair = self.session.get_current_pair()
        expert = self.session.get_current_expert()
        progress = self.session.get_progress()

        if pair and expert:
            self.current_frame.update_comparison(
                pair,
                expert.expert_id,
                progress
            )

    # === Обробники подій ===

    def on_new_project(self):
        """Обробник створення нового проекту"""
        self.session = SessionModel()
        self.show_project_setup()

    def on_open_project(self):
        """Обробник відкриття існуючого проекту"""
        filename = filedialog.askopenfilename(
            title="Відкрити сесію",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )

        if filename:
            try:
                self.session = SessionModel.load_session(filename)
                messagebox.showinfo("Успіх", "Сесію успішно завантажено")

                # Якщо сесія завершена, показуємо результати
                if self.session.is_complete():
                    self.show_results()
                else:
                    self.show_comparison_window()

            except Exception as e:
                messagebox.showerror("Помилка", f"Не вдалося завантажити сесію:\n{e}")

    def on_start_comparison(self, alternatives: List[str], expert_ids: List[str],
                           competence_coefficients: Dict[str, float]):
        """Обробник початку порівнянь"""
        if not self.session:
            self.session = SessionModel()

        self.session.initialize_session(alternatives, expert_ids, competence_coefficients)
        self.show_comparison_window()

    def on_judgment(self, value: float, scale_type: ScaleType, n_gradations: int):
        """Обробник додавання оцінки"""
        if not self.session:
            return

        pair = self.session.get_current_pair()
        if not pair:
            return

        # Створюємо оцінку
        judgment = Judgment(
            alt_i=pair[0],
            alt_j=pair[1],
            value=value,
            scale_type=scale_type,
            n_gradations=n_gradations
        )

        # Додаємо до сесії
        self.session.add_judgment(judgment)

        # Переходимо до наступної пари
        has_next = self.session.next_pair()

        if not has_next:
            # Закінчились пари, показуємо результати
            self.show_results()
        else:
            # Оновлюємо відображення
            self._update_comparison_display()

    def on_skip(self):
        """Обробник пропуску порівняння"""
        if not self.session:
            return

        # Переходимо до наступної пари без додавання оцінки
        has_next = self.session.next_pair()

        if not has_next:
            response = messagebox.askyesno(
                "Завершення",
                "Закінчились порівняння. Обчислити результати?\n" +
                "(Неповні МПП будуть заповнені автоматично)"
            )
            if response:
                self.show_results()
        else:
            self._update_comparison_display()

    def on_back(self):
        """Обробник повернення до попередньої пари"""
        if not self.session:
            return

        can_go_back = self.session.prev_pair()

        if can_go_back:
            # Видаляємо останню оцінку якщо вона є
            expert = self.session.get_current_expert()
            if expert and expert.judgments:
                expert.judgments.pop()

            self._update_comparison_display()
        else:
            messagebox.showinfo("Інформація", "Це перше порівняння")

    def on_save_session(self):
        """Обробник збереження сесії"""
        if not self.session:
            return

        filename = filedialog.asksaveasfilename(
            title="Зберегти сесію",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )

        if filename:
            try:
                self.session.save_session(filename)
                messagebox.showinfo("Успіх", f"Сесію збережено: {filename}")
            except Exception as e:
                messagebox.showerror("Помилка", f"Не вдалося зберегти сесію:\n{e}")

    def on_export_results(self, results: Dict):
        """Обробник експорту результатів"""
        directory = filedialog.askdirectory(title="Оберіть директорію для експорту")

        if not directory:
            return

        try:
            # 1. Експорт ваг у CSV
            weights_file = os.path.join(directory, "weights.csv")
            with open(weights_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=['rank', 'alternative', 'weight'])
                writer.writeheader()
                for item in results['ranking']:
                    writer.writerow({
                        'rank': item['rank'],
                        'alternative': item['alternative'],
                        'weight': f"{item['weight']:.6f}"
                    })

            # 2. Експорт узгодженості у JSON
            consistency_file = os.path.join(directory, "consistency.json")
            consistency_data = {
                'consistency_analysis': results['consistency'],
                'matrix_size': len(self.session.alternatives),
                'alternatives': self.session.alternatives,
                'aggregated_matrix': results['aggregated_matrix'].tolist()
            }
            with open(consistency_file, 'w', encoding='utf-8') as f:
                json.dump(consistency_data, f, ensure_ascii=False, indent=2)

            # 3. Експорт рекомендацій у JSON
            suggestions_file = os.path.join(directory, "suggestions.json")
            with open(suggestions_file, 'w', encoding='utf-8') as f:
                json.dump(results['suggestions'], f, ensure_ascii=False, indent=2)

            # 4. Експорт трансформацій шкал
            scale_transformations = []
            for expert in self.session.experts:
                for judgment in expert.judgments:
                    from scales import calculate_informativeness
                    entry = {
                        'expert_id': expert.expert_id,
                        'comparison': f"{judgment.alt_i} vs {judgment.alt_j}",
                        'alt_i': judgment.alt_i,
                        'alt_j': judgment.alt_j,
                        'scale_type': judgment.scale_type.value,
                        'n_gradations': judgment.n_gradations,
                        'value': judgment.value,
                        'informativeness': calculate_informativeness(judgment.n_gradations),
                        'scale_history': [
                            {'scale_type': st.value, 'n_gradations': n}
                            for st, n in judgment.scale_history
                        ]
                    }
                    scale_transformations.append(entry)

            transformations_file = os.path.join(directory, "scale_transformations.json")
            with open(transformations_file, 'w', encoding='utf-8') as f:
                json.dump(scale_transformations, f, ensure_ascii=False, indent=2)

            messagebox.showinfo(
                "Успіх",
                f"Результати експортовано до:\n{directory}\n\n" +
                "Файли:\n" +
                "- weights.csv\n" +
                "- consistency.json\n" +
                "- suggestions.json\n" +
                "- scale_transformations.json"
            )

        except Exception as e:
            messagebox.showerror("Помилка", f"Не вдалося експортувати результати:\n{e}")
