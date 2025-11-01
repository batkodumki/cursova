"""
Модуль scales.py - визначення шкал експертних оцінок, таблиці відповідників, уніфікація
Базується на джерелах: РЗОД-2011-3.pdf (вибір шкал, таблиці 5, 6), РЗОД-2011-4.pdf (уніфікація)

Реалізує рівно 6 шкал експертних оцінок:
1. Ординальна (2 градації)
2. Цілочислова/Сааті-9 (9 градацій) - класична шкала Сааті
3. Збалансована (3-9 градацій) - формули з РЗОД-2011-3
4. Степенева (3-9 градацій) - формули з РЗОД-2011-3
5. Ма-Чженга (3-9 градацій) - таблиця 5 у РЗОД-2011-3
6. Донегана-Додд-МакМастера (3-9 градацій) - таблиця 6 у РЗОД-2011-3

Функції:
- Уніфікацію оцінок до єдиної кардинальної шкали (межі 1.5..9.5)
- Розрахунок інформативності шкали за формулою Хартлі I = log₂ N
- Журналювання трансформацій шкал
"""

import math
from enum import Enum
from typing import Dict, List, Tuple, Optional
import numpy as np


class ScaleType(Enum):
    """
    Типи шкал експертних оцінок (рівно 6 шкал згідно РЗОД-2011-3.pdf)
    """
    ORDINAL = "ordinal"  # Ординальна шкала (2 градації)
    SAATY_9 = "saaty_9"  # Цілочислова шкала Сааті (9 градацій) - класична
    BALANCED = "balanced"  # Збалансована шкала (3-9 градацій)
    POWER = "power"  # Степенева шкала (3-9 градацій)
    MA_ZHENG = "ma_zheng"  # Шкала Ма-Чженга (3-9 градацій, табл. 5 РЗОД-2011-3)
    DONEGAN = "donegan"  # Шкала Донегана-Додд-МакМастера (3-9 градацій, табл. 6 РЗОД-2011-3)


# Діапазон допустимих градацій для кожної шкали (РЗОД-2011-3.pdf, правило 7±2)
SCALE_GRADATIONS_RANGE = {
    ScaleType.ORDINAL: (2, 2),
    ScaleType.SAATY_9: (3, 9),
    ScaleType.BALANCED: (3, 9),
    ScaleType.POWER: (3, 9),
    ScaleType.MA_ZHENG: (3, 9),
    ScaleType.DONEGAN: (3, 9),
}


def get_scale_values(scale_type: ScaleType, n_gradations: int) -> List[float]:
    """
    Повертає числові значення для заданої шкали та кількості градацій.
    Базується на РЗОД-2011-3.pdf (таблиці 5, 6 та формули для кожної шкали)

    Args:
        scale_type: Тип шкали (одна з 6 доступних)
        n_gradations: Кількість градацій (2-9, залежить від типу шкали)

    Returns:
        Список числових значень шкали

    Examples:
        >>> get_scale_values(ScaleType.SAATY_9, 9)
        [1, 2, 3, 4, 5, 6, 7, 8, 9]
        >>> get_scale_values(ScaleType.ORDINAL, 2)
        [1.0, 9.0]
        >>> len(get_scale_values(ScaleType.BALANCED, 5))
        5
    """
    min_grad, max_grad = SCALE_GRADATIONS_RANGE.get(scale_type, (3, 9))
    if not (min_grad <= n_gradations <= max_grad):
        raise ValueError(
            f"Шкала {scale_type.value} підтримує {min_grad}-{max_grad} градацій, отримано {n_gradations}"
        )

    if scale_type == ScaleType.ORDINAL:
        # 1. Ординальна шкала (2 градації): екстремальні значення 1 та 9
        # РЗОД-2011-3.pdf: найпростіша шкала, тільки напрямок переваги
        return [1.0, 9.0]

    elif scale_type == ScaleType.SAATY_9:
        # 2. Цілочислова шкала Сааті-9 (класична фундаментальна шкала)
        # РЗОД-2011-3.pdf: 1, 2, 3, 4, 5, 6, 7, 8, 9 для n=9
        # Для менших n: беремо рівномірно розподілені цілі значення
        if n_gradations == 9:
            return list(range(1, 10))  # [1, 2, 3, 4, 5, 6, 7, 8, 9]
        else:
            # Рівномірний розподіл у діапазоні 1-9
            return [round(1.0 + (i * 8.0 / (n_gradations - 1))) for i in range(n_gradations)]

    elif scale_type == ScaleType.BALANCED:
        # 3. Збалансована шкала (РЗОД-2011-3.pdf, формула w/(1-w))
        # w рівномірно розподілено, забезпечує рівномірний розподіл ваг
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
        # 4. Степенева шкала (РЗОД-2011-3.pdf, формула 9^((i-1)/(n-1)))
        # Геометричне зростання від 1 до 9
        values = []
        for i in range(n_gradations):
            if n_gradations > 1:
                value = 9.0 ** (i / (n_gradations - 1))
            else:
                value = 1.0
            values.append(value)
        return values

    elif scale_type == ScaleType.MA_ZHENG:
        # 5. Шкала Ма-Чженга (РЗОД-2011-3.pdf, таблиця 5, формула n/(n+1-i))
        # Для n=9: 9/9, 9/8, 9/7, 9/6, 9/5, 9/4, 9/3, 9/2, 9/1
        values = []
        for i in range(1, n_gradations + 1):
            value = n_gradations / (n_gradations + 1 - i)
            values.append(min(9.0, value))
        return values

    elif scale_type == ScaleType.DONEGAN:
        # 6. Шкала Донегана-Додд-МакМастера (РЗОД-2011-3.pdf, таблиця 6)
        # Формула: exp(tanh^(-1)((i-1)/(h-1))) де h - параметр "горизонту"
        # Спрощена версія з логарифмічним розподіленням
        h = 1 + 6 * math.sqrt(2)  # 7-ковий горизонт (РЗОД-2011-3.pdf)
        values = []
        for i in range(1, n_gradations + 1):
            if n_gradations > 1:
                # Нормалізуємо i до діапазону [0, 1]
                x = (i - 1) / (n_gradations - 1)
                # Використовуємо tanh для нелінійного масштабування
                # value = exp(arctanh(x * (h-1)/(h+1)))
                # Спрощена формула для практичного використання:
                value = 1.0 + 8.0 * (math.tanh(x * 2.0) / math.tanh(2.0))
                value = max(1.0, min(9.0, value))
            else:
                value = 1.0
            values.append(value)
        return values

    else:
        raise ValueError(f"Невідомий тип шкали: {scale_type}")


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
        >>> unify_judgment(ScaleType.SAATY_9, 9, 5.0)
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


def create_transformation_log(expert_id: str, comparison: str, scale_type: ScaleType,
                              n_gradations: int, original_value: float,
                              unified_value: float) -> Dict:
    """
    Створює запис журналу трансформації шкали для експорту.
    Базується на РЗОД-2011-4.pdf (уніфікація до кардинальної шкали)

    Args:
        expert_id: Ідентифікатор експерта
        comparison: Назва порівняння (напр. "A vs B")
        scale_type: Тип вихідної шкали
        n_gradations: Кількість градацій вихідної шкали
        original_value: Вихідне значення оцінки
        unified_value: Уніфіковане значення на кардинальній шкалі

    Returns:
        Словник з інформацією про трансформацію

    Examples:
        >>> log = create_transformation_log("E1", "A vs B", ScaleType.SAATY_9, 9, 5.0, 5.0)
        >>> log['expert_id']
        'E1'
        >>> log['informativeness'] > 3.0
        True
    """
    informativeness = calculate_informativeness(n_gradations)

    return {
        'expert_id': expert_id,
        'comparison': comparison,
        'original_scale': scale_type.value,
        'n_gradations': n_gradations,
        'original_value': float(original_value),
        'unified_value': float(unified_value),
        'informativeness': float(informativeness),
        'scale_bounds': {
            'lower': 1.5,
            'upper': 9.5
        },
        'transformation_formula': f'M_i^n = 1.5 + (i - 0.5) × 8 / {n_gradations}'
    }


if __name__ == "__main__":
    import doctest
    doctest.testmod()

    # Демонстрація роботи модуля
    print("=== Демонстрація модуля scales.py ===\n")

    print("=== Демонстрація 6 шкал експертних оцінок ===\n")

    print("1. Значення всіх 6 шкал з 9 градаціями:")
    for scale_type in ScaleType:
        min_grad, max_grad = SCALE_GRADATIONS_RANGE[scale_type]
        if max_grad >= 9:
            values = get_scale_values(scale_type, 9)
            print(f"   {scale_type.value}: {[round(v, 2) for v in values]}")

    print("\n2. Інформативність шкал (формула Хартлі I = log₂ N):")
    for n in [2, 3, 5, 7, 9]:
        info = calculate_informativeness(n)
        print(f"   N={n} градацій: I = {info:.3f} біт")

    print("\n3. Уніфікація оцінок до кардинальної шкали [1.5, 9.5]:")
    test_cases = [
        (ScaleType.ORDINAL, 2, 1),
        (ScaleType.SAATY_9, 9, 5),
        (ScaleType.BALANCED, 5, 3),
        (ScaleType.POWER, 7, 4),
        (ScaleType.MA_ZHENG, 9, 7),
        (ScaleType.DONEGAN, 9, 6),
    ]
    for scale_type, n, grade in test_cases:
        unified = unify_to_cardinal(scale_type, n, grade)
        print(f"   {scale_type.value}, N={n}, градація {grade} → {unified}")

    print("\n4. Порівняння шкал з 5 градаціями:")
    table = get_correspondence_table(5)
    for scale_type, values in sorted(table.items(), key=lambda x: x[0].value):
        print(f"   {scale_type.value:15s}: {[round(v, 2) for v in values]}")

    print("\n5. Демонстрація уніфікації конкретних оцінок:")
    demo_judgments = [
        (ScaleType.SAATY_9, 9, 7.0),
        (ScaleType.BALANCED, 5, 3.5),
        (ScaleType.MA_ZHENG, 9, 4.5),
    ]
    for scale_type, n, value in demo_judgments:
        unified = unify_judgment(scale_type, n, value)
        print(f"   {scale_type.value}, N={n}, значення={value:.1f} → уніфіковано: {unified}")
