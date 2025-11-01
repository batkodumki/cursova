"""
Модуль scales.py - визначення шкал експертних оцінок, таблиці відповідників, уніфікація
Базується на джерелах: РЗОД-2011-3.pdf (вибір шкал), РЗОД-2011-4.pdf (уніфікація)

Реалізує:
- Визначення шкал: порядкова, Сааті-5, Сааті-9, збалансована, степенева
- Таблиці відповідників між шкалами
- Уніфікацію оцінок до єдиної кардинальної шкали (1-9)
- Розрахунок інформативності шкали за формулою Хартлі I = log₂ N
"""

import math
from enum import Enum
from typing import Dict, List, Tuple
import numpy as np


class ScaleType(Enum):
    """
    Типи шкал експертних оцінок (РЗОД-2011-3.pdf)
    """
    ORDINAL = "ordinal"  # Порядкова шкала (2 градації)
    SAATY_5 = "saaty_5"  # Фундаментальна шкала Сааті (5 градацій)
    SAATY_9 = "saaty_9"  # Фундаментальна шкала Сааті (9 градацій)
    BALANCED = "balanced"  # Збалансована шкала
    POWER = "power"  # Степенева шкала
    MA_ZHENG = "ma_zheng"  # Шкала Ма-Жена
    DONEGAN = "donegan"  # Шкала Донегана-Додда-МакМастера


# Діапазон допустимих градацій для кожної шкали (РЗОД-2011-3.pdf, правило обмеження 7±2)
SCALE_GRADATIONS_RANGE = {
    ScaleType.ORDINAL: (2, 2),
    ScaleType.SAATY_5: (3, 5),
    ScaleType.SAATY_9: (3, 9),
    ScaleType.BALANCED: (3, 9),
    ScaleType.POWER: (3, 9),
    ScaleType.MA_ZHENG: (3, 9),
    ScaleType.DONEGAN: (3, 9),
}


def get_scale_values(scale_type: ScaleType, n_gradations: int) -> List[float]:
    """
    Повертає числові значення для заданої шкали та кількості градацій.
    Базується на РЗОД-2011-3.pdf (таблиці відповідників шкал)

    Args:
        scale_type: Тип шкали
        n_gradations: Кількість градацій (3-9)

    Returns:
        Список числових значень шкали

    Examples:
        >>> get_scale_values(ScaleType.SAATY_9, 9)
        [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0]
        >>> get_scale_values(ScaleType.ORDINAL, 2)
        [1.0, 9.0]
    """
    min_grad, max_grad = SCALE_GRADATIONS_RANGE.get(scale_type, (3, 9))
    if not (min_grad <= n_gradations <= max_grad):
        raise ValueError(
            f"Шкала {scale_type.value} підтримує {min_grad}-{max_grad} градацій, отримано {n_gradations}"
        )

    if scale_type == ScaleType.ORDINAL:
        # Порядкова: екстремальні значення 1 та 9
        return [1.0, 9.0]

    elif scale_type == ScaleType.SAATY_9:
        # Фундаментальна шкала Сааті (РЗОД-2011-3.pdf)
        # 1, 2, 3, 4, 5, 6, 7, 8, 9 для n=9
        # Для менших n беремо перші n значень
        return list(range(1, n_gradations + 1))

    elif scale_type == ScaleType.SAATY_5:
        # Сааті з 5 градаціями: 1, 3, 5, 7, 9 (РЗОД-2011-3.pdf)
        if n_gradations == 5:
            return [1.0, 3.0, 5.0, 7.0, 9.0]
        elif n_gradations == 3:
            return [1.0, 5.0, 9.0]
        elif n_gradations == 4:
            return [1.0, 3.0, 5.0, 9.0]
        else:
            # Для інших n інтерполюємо
            return [1.0 + (i * 8.0 / (n_gradations - 1)) for i in range(n_gradations)]

    elif scale_type == ScaleType.BALANCED:
        # Збалансована шкала: w/(1-w), де w рівномірно розподілено (РЗОД-2011-3.pdf)
        # Формула: для градації i від 1 до n, w_i = i/n, значення = w/(1-w)
        values = []
        for i in range(1, n_gradations + 1):
            w = i / (n_gradations + 1)
            if w >= 1.0:
                w = 0.99  # Уникнення ділення на нуль
            value = w / (1 - w)
            # Обмежуємо діапазон 1-9
            value = max(1.0, min(9.0, value))
            values.append(value)
        return values

    elif scale_type == ScaleType.POWER:
        # Степенева шкала: 9^((x-1)/(n-1)) (РЗОД-2011-3.pdf)
        values = []
        for i in range(n_gradations):
            value = 9.0 ** (i / (n_gradations - 1)) if n_gradations > 1 else 1.0
            values.append(value)
        return values

    elif scale_type == ScaleType.MA_ZHENG:
        # Шкала Ма-Жена: n/(n+1-i) (РЗОД-2011-3.pdf)
        values = []
        for i in range(1, n_gradations + 1):
            value = n_gradations / (n_gradations + 1 - i)
            values.append(min(9.0, value))
        return values

    elif scale_type == ScaleType.DONEGAN:
        # Шкала Донегана-Додда-МакМастера (РЗОД-2011-3.pdf)
        # Логарифмічне розподілення
        values = []
        for i in range(n_gradations):
            if n_gradations > 1:
                value = 1.0 + 8.0 * (math.log(1 + i) / math.log(n_gradations))
            else:
                value = 1.0
            values.append(value)
        return values

    else:
        # За замовчуванням лінійна шкала 1-9
        return [1.0 + (i * 8.0 / (n_gradations - 1)) for i in range(n_gradations)]


def unify_to_cardinal(scale_type: ScaleType, n_gradations: int, grade_index: int) -> float:
    """
    Уніфікація оцінки до єдиної кардинальної шкали (1-9) через центри інтервалів.
    Базується на РЗОД-2011-4.pdf: M_i^n = l + (i - 1/2) * (p - l) / n, де l=1.5, p=9.5

    Args:
        scale_type: Тип вихідної шкали
        n_gradations: Кількість градацій вихідної шкали
        grade_index: Індекс градації (1-based: 1, 2, ..., n)

    Returns:
        Уніфіковане значення на кардинальній шкалі [1, 9]

    Examples:
        >>> unify_to_cardinal(ScaleType.SAATY_5, 5, 3)  # 3-я градація з 5
        5.0
        >>> unify_to_cardinal(ScaleType.SAATY_9, 9, 5)  # 5-я градація з 9
        5.0
    """
    if not (1 <= grade_index <= n_gradations):
        raise ValueError(
            f"Індекс градації {grade_index} поза межами [1, {n_gradations}]"
        )

    # Параметри уніфікованої кардинальної шкали (РЗОД-2011-4.pdf)
    l = 1.5  # Нижня межа
    p = 9.5  # Верхня межа

    # Формула центру інтервалу (РЗОД-2011-4.pdf)
    unified_value = l + (grade_index - 0.5) * (p - l) / n_gradations

    # Округлення до найближчого цілого в діапазоні [1, 9]
    return round(max(1.0, min(9.0, unified_value)))


def calculate_informativeness(n_gradations: int) -> float:
    """
    Розрахунок інформативності шкали за формулою Хартлі: I = log₂ N
    Базується на РЗОД-2011-2.pdf, РЗОД-2011-4.pdf

    Args:
        n_gradations: Кількість градацій шкали

    Returns:
        Інформативність шкали (біти)

    Examples:
        >>> calculate_informativeness(2)
        1.0
        >>> calculate_informativeness(9)
        3.169925001442312
    """
    if n_gradations < 2:
        raise ValueError("Кількість градацій має бути >= 2")

    return math.log2(n_gradations)


def get_correspondence_table(n_gradations: int) -> Dict[ScaleType, List[float]]:
    """
    Генерує таблицю відповідників для всіх типів шкал з заданою кількістю градацій.
    Базується на РЗОД-2011-3.pdf (таблиці відповідників між шкалами)

    Args:
        n_gradations: Кількість градацій

    Returns:
        Словник {тип_шкали: [значення]}

    Examples:
        >>> table = get_correspondence_table(5)
        >>> len(table[ScaleType.SAATY_5])
        5
    """
    correspondence = {}

    for scale_type in ScaleType:
        min_grad, max_grad = SCALE_GRADATIONS_RANGE.get(scale_type, (3, 9))
        if min_grad <= n_gradations <= max_grad:
            try:
                correspondence[scale_type] = get_scale_values(scale_type, n_gradations)
            except ValueError:
                pass  # Пропускаємо шкали, які не підтримують дану кількість градацій

    return correspondence


def unify_judgment(scale_type: ScaleType, n_gradations: int,
                   original_value: float, is_reciprocal: bool = False) -> float:
    """
    Уніфікує одну експертну оцінку до єдиної кардинальної шкали.

    Args:
        scale_type: Тип шкали оцінки
        n_gradations: Кількість градацій шкали
        original_value: Вихідне значення оцінки
        is_reciprocal: Чи є оцінка оберненою (a_ji = 1/a_ij)

    Returns:
        Уніфіковане значення на шкалі [1, 9]

    Examples:
        >>> unify_judgment(ScaleType.SAATY_5, 5, 5.0)
        5
        >>> unify_judgment(ScaleType.SAATY_9, 9, 3.0)
        3
    """
    # Обробка обернених оцінок
    if is_reciprocal and original_value != 0:
        original_value = 1.0 / original_value

    # Отримуємо значення шкали
    scale_values = get_scale_values(scale_type, n_gradations)

    # Знаходимо найближчу градацію
    closest_index = min(range(len(scale_values)),
                       key=lambda i: abs(scale_values[i] - original_value))

    # Конвертуємо в уніфіковану шкалу (1-based індекс)
    grade_index = closest_index + 1

    return unify_to_cardinal(scale_type, n_gradations, grade_index)


if __name__ == "__main__":
    import doctest
    doctest.testmod()

    # Демонстрація роботи модуля
    print("=== Демонстрація модуля scales.py ===\n")

    print("1. Значення шкали Сааті-9 з 9 градаціями:")
    print(get_scale_values(ScaleType.SAATY_9, 9))

    print("\n2. Інформативність шкал:")
    for n in [2, 5, 9]:
        info = calculate_informativeness(n)
        print(f"   N={n} градацій: I = {info:.3f} біт")

    print("\n3. Уніфікація оцінок:")
    test_cases = [
        (ScaleType.SAATY_5, 5, 3),
        (ScaleType.SAATY_9, 9, 5),
        (ScaleType.ORDINAL, 2, 2),
    ]
    for scale_type, n, grade in test_cases:
        unified = unify_to_cardinal(scale_type, n, grade)
        print(f"   {scale_type.value}, N={n}, градація {grade} → {unified}")

    print("\n4. Таблиця відповідників для N=5:")
    table = get_correspondence_table(5)
    for scale_type, values in table.items():
        print(f"   {scale_type.value}: {[round(v, 2) for v in values]}")
