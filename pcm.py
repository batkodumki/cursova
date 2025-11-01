"""
Модуль pcm.py - побудова та операції з матрицями попарних порівнянь (МПП)
Базується на джерелах: РЗОД-2011-2.pdf, РЗОД-2011-3.pdf, РЗОД-2011-4.pdf

Реалізує:
- Створення та оновлення МПП
- Додавання експертних оцінок з різними шкалами
- Перевірку зворотної симетрії (a_ji = 1/a_ij)
- Підтримку неповних МПП
- Перевірку зв'язності графу порівнянь
"""

import numpy as np
from typing import Dict, List, Tuple, Optional, Set
from enum import Enum
from scales import ScaleType, unify_judgment


class PCMStatus(Enum):
    """Статус матриці попарних порівнянь"""
    EMPTY = "empty"
    INCOMPLETE = "incomplete"
    COMPLETE = "complete"


class PairwiseComparisonMatrix:
    """
    Матриця попарних порівнянь (МПП/PCM) з підтримкою адаптивного вибору шкал.
    Базується на РЗОД-2011-3.pdf, РЗОД-2011-4.pdf
    """

    def __init__(self, alternatives: List[str], expert_id: str = "expert_1"):
        """
        Ініціалізація МПП

        Args:
            alternatives: Список назв альтернатив
            expert_id: Ідентифікатор експерта

        Examples:
            >>> pcm = PairwiseComparisonMatrix(["A1", "A2", "A3"])
            >>> pcm.n_alternatives
            3
        """
        self.alternatives = alternatives
        self.n_alternatives = len(alternatives)
        self.expert_id = expert_id

        # Уніфікована МПП (кардинальна шкала 1-9)
        self.unified_matrix = np.ones((self.n_alternatives, self.n_alternatives))

        # Зберігання інформації про вихідні оцінки
        # Формат: (i, j) -> (scale_type, n_gradations, original_value)
        self.original_judgments: Dict[Tuple[int, int], Tuple[ScaleType, int, float]] = {}

        # Маска заповнених елементів (True якщо оцінка надана)
        self.filled_mask = np.zeros((self.n_alternatives, self.n_alternatives), dtype=bool)
        # Діагональ завжди заповнена одиницями
        np.fill_diagonal(self.filled_mask, True)

    def add_judgment(self, alt_i: str, alt_j: str, value: float,
                    scale_type: ScaleType, n_gradations: int) -> None:
        """
        Додає експертну оцінку порівняння альтернатив i та j.
        Автоматично встановлює обернену оцінку a_ji = 1/a_ij (зворотна симетрія).
        Базується на РЗОД-2011-3.pdf, РЗОД-2011-4.pdf

        Args:
            alt_i: Назва альтернативи i (рядок)
            alt_j: Назва альтернативи j (стовпець)
            value: Значення оцінки на вихідній шкалі
            scale_type: Тип шкали оцінки
            n_gradations: Кількість градацій шкали

        Examples:
            >>> pcm = PairwiseComparisonMatrix(["A1", "A2", "A3"])
            >>> pcm.add_judgment("A1", "A2", 5.0, ScaleType.SAATY_9, 9)
            >>> pcm.unified_matrix[0, 1]
            5.0
        """
        # Знаходимо індекси альтернатив
        i = self.alternatives.index(alt_i)
        j = self.alternatives.index(alt_j)

        if i == j:
            raise ValueError("Неможливо порівняти альтернативу саму з собою")

        # Уніфікуємо оцінку до кардинальної шкали
        unified_value = unify_judgment(scale_type, n_gradations, value, is_reciprocal=False)

        # Зберігаємо уніфіковану оцінку
        self.unified_matrix[i, j] = unified_value
        self.filled_mask[i, j] = True

        # Зберігаємо вихідну інформацію
        self.original_judgments[(i, j)] = (scale_type, n_gradations, value)

        # Встановлюємо обернену оцінку (зворотна симетрія, РЗОД-2011-3.pdf)
        if unified_value != 0:
            self.unified_matrix[j, i] = 1.0 / unified_value
            self.filled_mask[j, i] = True
            # Зберігаємо інформацію про обернену оцінку
            self.original_judgments[(j, i)] = (scale_type, n_gradations, 1.0 / value)

    def get_status(self) -> PCMStatus:
        """
        Визначає статус заповненості МПП

        Returns:
            Статус матриці (EMPTY, INCOMPLETE, COMPLETE)

        Examples:
            >>> pcm = PairwiseComparisonMatrix(["A1", "A2"])
            >>> pcm.get_status()
            <PCMStatus.INCOMPLETE: 'incomplete'>
        """
        # Рахуємо заповнені елементи (без діагоналі)
        n_filled = np.sum(self.filled_mask) - self.n_alternatives
        n_required = self.n_alternatives * (self.n_alternatives - 1)

        if n_filled == 0:
            return PCMStatus.EMPTY
        elif n_filled < n_required:
            return PCMStatus.INCOMPLETE
        else:
            return PCMStatus.COMPLETE

    def check_connectivity(self) -> bool:
        """
        Перевіряє зв'язність графу порівнянь (важливо для неповних МПП).
        Базується на РЗОД-2011-2.pdf, РЗОД-2012-1.pdf

        Returns:
            True якщо граф зв'язний, False інакше

        Examples:
            >>> pcm = PairwiseComparisonMatrix(["A1", "A2", "A3"])
            >>> pcm.add_judgment("A1", "A2", 3.0, ScaleType.SAATY_9, 9)
            >>> pcm.add_judgment("A2", "A3", 5.0, ScaleType.SAATY_9, 9)
            >>> pcm.check_connectivity()
            True
        """
        # Будуємо матриці суміжності (ігноруємо діагональ)
        adjacency = self.filled_mask.copy()
        np.fill_diagonal(adjacency, False)

        # Використовуємо DFS для перевірки зв'язності
        visited = set()

        def dfs(node: int):
            visited.add(node)
            for neighbor in range(self.n_alternatives):
                if adjacency[node, neighbor] and neighbor not in visited:
                    dfs(neighbor)

        # Запускаємо DFS з першої вершини
        if self.n_alternatives > 0:
            dfs(0)

        # Граф зв'язний, якщо відвідали всі вершини
        return len(visited) == self.n_alternatives

    def get_missing_comparisons(self) -> List[Tuple[str, str]]:
        """
        Повертає список відсутніх порівнянь (для неповних МПП)

        Returns:
            Список пар альтернатив без оцінок

        Examples:
            >>> pcm = PairwiseComparisonMatrix(["A1", "A2", "A3"])
            >>> len(pcm.get_missing_comparisons())
            3
        """
        missing = []
        for i in range(self.n_alternatives):
            for j in range(i + 1, self.n_alternatives):
                if not self.filled_mask[i, j]:
                    missing.append((self.alternatives[i], self.alternatives[j]))
        return missing

    def fill_transitive(self) -> int:
        """
        Заповнює відсутні елементи МПП через транзитивність: a_ik = a_ij * a_jk.
        Базується на РЗОД-2012-1.pdf (методи заповнення неповних МПП)

        Returns:
            Кількість заповнених елементів

        Examples:
            >>> pcm = PairwiseComparisonMatrix(["A1", "A2", "A3"])
            >>> pcm.add_judgment("A1", "A2", 3.0, ScaleType.SAATY_9, 9)
            >>> pcm.add_judgment("A2", "A3", 5.0, ScaleType.SAATY_9, 9)
            >>> filled = pcm.fill_transitive()
            >>> filled > 0
            True
        """
        filled_count = 0
        max_iterations = self.n_alternatives ** 2  # Запобігання нескінченному циклу

        for iteration in range(max_iterations):
            made_progress = False

            for i in range(self.n_alternatives):
                for j in range(self.n_alternatives):
                    if i == j or self.filled_mask[i, j]:
                        continue

                    # Шукаємо проміжну вершину k: a_ij = a_ik * a_kj
                    for k in range(self.n_alternatives):
                        if k == i or k == j:
                            continue

                        if self.filled_mask[i, k] and self.filled_mask[k, j]:
                            # Обчислюємо транзитивне значення
                            transitive_value = self.unified_matrix[i, k] * self.unified_matrix[k, j]
                            # Обмежуємо діапазон [1/9, 9]
                            transitive_value = max(1/9, min(9, transitive_value))

                            self.unified_matrix[i, j] = transitive_value
                            self.unified_matrix[j, i] = 1.0 / transitive_value
                            self.filled_mask[i, j] = True
                            self.filled_mask[j, i] = True

                            filled_count += 1
                            made_progress = True
                            break

            if not made_progress:
                break

        return filled_count

    def get_filled_pairs(self) -> List[Tuple[int, int]]:
        """
        Повертає список пар індексів заповнених елементів (без діагоналі)

        Returns:
            Список (i, j) заповнених елементів

        Examples:
            >>> pcm = PairwiseComparisonMatrix(["A1", "A2"])
            >>> pcm.add_judgment("A1", "A2", 3.0, ScaleType.SAATY_9, 9)
            >>> len(pcm.get_filled_pairs())
            2
        """
        pairs = []
        for i in range(self.n_alternatives):
            for j in range(self.n_alternatives):
                if i != j and self.filled_mask[i, j]:
                    pairs.append((i, j))
        return pairs

    def to_dict(self) -> dict:
        """
        Експортує МПП у словник для серіалізації

        Returns:
            Словник з даними МПП

        Examples:
            >>> pcm = PairwiseComparisonMatrix(["A1", "A2"])
            >>> data = pcm.to_dict()
            >>> 'alternatives' in data
            True
        """
        return {
            'expert_id': self.expert_id,
            'alternatives': self.alternatives,
            'unified_matrix': self.unified_matrix.tolist(),
            'filled_mask': self.filled_mask.tolist(),
            'status': self.get_status().value,
            'n_judgments': len(self.original_judgments),
            'is_connected': self.check_connectivity(),
        }

    @staticmethod
    def from_judgments(alternatives: List[str],
                      judgments: List[Dict],
                      expert_id: str = "expert_1") -> 'PairwiseComparisonMatrix':
        """
        Створює МПП зі списку експертних оцінок

        Args:
            alternatives: Список альтернатив
            judgments: Список словників з оцінками
                      [{alt_i, alt_j, value, scale_type, n_gradations}, ...]
            expert_id: Ідентифікатор експерта

        Returns:
            Заповнена МПП

        Examples:
            >>> judgments = [
            ...     {'alt_i': 'A1', 'alt_j': 'A2', 'value': 3.0,
            ...      'scale_type': 'saaty_9', 'n_gradations': 9}
            ... ]
            >>> pcm = PairwiseComparisonMatrix.from_judgments(['A1', 'A2', 'A3'], judgments)
            >>> pcm.n_alternatives
            3
        """
        pcm = PairwiseComparisonMatrix(alternatives, expert_id)

        for judgment in judgments:
            alt_i = judgment['alt_i']
            alt_j = judgment['alt_j']
            value = judgment['value']
            scale_type_str = judgment['scale_type']
            n_gradations = judgment['n_gradations']

            # Конвертуємо строку в ScaleType
            scale_type = ScaleType(scale_type_str)

            pcm.add_judgment(alt_i, alt_j, value, scale_type, n_gradations)

        return pcm


if __name__ == "__main__":
    import doctest
    doctest.testmod()

    # Демонстрація роботи модуля
    print("=== Демонстрація модуля pcm.py ===\n")

    alternatives = ["Альтернатива_1", "Альтернатива_2", "Альтернатива_3", "Альтернатива_4"]
    pcm = PairwiseComparisonMatrix(alternatives, expert_id="Експерт_1")

    print("1. Додавання оцінок з різними шкалами:")
    pcm.add_judgment("Альтернатива_1", "Альтернатива_2", 5.0, ScaleType.SAATY_9, 9)
    pcm.add_judgment("Альтернатива_1", "Альтернатива_3", 3.0, ScaleType.SAATY_5, 5)
    pcm.add_judgment("Альтернатива_2", "Альтернатива_3", 7.0, ScaleType.SAATY_9, 9)
    pcm.add_judgment("Альтернатива_3", "Альтернатива_4", 5.0, ScaleType.SAATY_5, 5)
    print(f"   Статус: {pcm.get_status().value}")
    print(f"   Зв'язність: {pcm.check_connectivity()}")

    print("\n2. Уніфікована матриця:")
    print(np.round(pcm.unified_matrix, 2))

    print("\n3. Відсутні порівняння:")
    missing = pcm.get_missing_comparisons()
    print(f"   Кількість: {len(missing)}")
    if missing:
        for alt_i, alt_j in missing[:3]:
            print(f"   - {alt_i} vs {alt_j}")

    print("\n4. Заповнення через транзитивність:")
    filled = pcm.fill_transitive()
    print(f"   Заповнено елементів: {filled}")
    print(f"   Новий статус: {pcm.get_status().value}")

    print("\n5. Остаточна уніфікована матриця:")
    print(np.round(pcm.unified_matrix, 2))
