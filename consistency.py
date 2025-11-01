"""
Модуль consistency.py - оцінка узгодженості МПП та генерація зворотного зв'язку
Базується на джерелах: РЗОД-2011-4.pdf, РЗОД-2012-1.pdf

Реалізує:
- Розрахунок спектрального показника узгодженості (λ_max)
- Індекс узгодженості (CI) та відношення узгодженості (CR)
- Побудову ідеальної узгодженої МПП
- Генерацію рекомендацій для покращення узгодженості
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from scipy.linalg import eig
import warnings

# Випадковий індекс (Random Index) для різних розмірів матриць
# Базується на стандартних значеннях Сааті (РЗОД-2011-4.pdf)
RANDOM_INDEX = {
    1: 0.00,
    2: 0.00,
    3: 0.58,
    4: 0.90,
    5: 1.12,
    6: 1.24,
    7: 1.32,
    8: 1.41,
    9: 1.45,
    10: 1.49,
    11: 1.51,
    12: 1.48,
    13: 1.56,
    14: 1.57,
    15: 1.59,
}


def calculate_lambda_max(matrix: np.ndarray) -> float:
    """
    Розраховує максимальне власне значення λ_max матриці.
    Базується на РЗОД-2011-4.pdf (спектральний показник узгодженості)

    Args:
        matrix: Матриця попарних порівнянь (n x n)

    Returns:
        Максимальне власне значення λ_max

    Examples:
        >>> matrix = np.array([[1, 3, 5], [1/3, 1, 3], [1/5, 1/3, 1]])
        >>> lambda_max = calculate_lambda_max(matrix)
        >>> 3.0 <= lambda_max <= 3.1
        True
    """
    n = matrix.shape[0]

    # Обчислюємо власні значення
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        eigenvalues, _ = eig(matrix)

    # Беремо дійсну частину максимального власного значення
    lambda_max = np.max(np.real(eigenvalues))

    return float(lambda_max)


def calculate_consistency_index(matrix: np.ndarray) -> float:
    """
    Розраховує індекс узгодженості (CI - Consistency Index).
    Формула: CI = (λ_max - n) / (n - 1)
    Базується на РЗОД-2011-4.pdf

    Args:
        matrix: Матриця попарних порівнянь (n x n)

    Returns:
        Індекс узгодженості CI

    Examples:
        >>> matrix = np.array([[1, 1, 1], [1, 1, 1], [1, 1, 1]])
        >>> ci = calculate_consistency_index(matrix)
        >>> abs(ci) < 0.01
        True
    """
    n = matrix.shape[0]

    if n <= 1:
        return 0.0

    lambda_max = calculate_lambda_max(matrix)
    ci = (lambda_max - n) / (n - 1)

    return float(ci)


def calculate_consistency_ratio(matrix: np.ndarray) -> float:
    """
    Розраховує відношення узгодженості (CR - Consistency Ratio).
    Формула: CR = CI / RI
    Базується на РЗОД-2011-4.pdf

    Args:
        matrix: Матриця попарних порівнянь (n x n)

    Returns:
        Відношення узгодженості CR

    Examples:
        >>> matrix = np.array([[1, 3, 5], [1/3, 1, 3], [1/5, 1/3, 1]])
        >>> cr = calculate_consistency_ratio(matrix)
        >>> cr < 0.2
        True
    """
    n = matrix.shape[0]

    if n <= 2:
        return 0.0

    ci = calculate_consistency_index(matrix)
    ri = RANDOM_INDEX.get(n, 1.49)  # За замовчуванням RI для n=15

    if ri == 0:
        return 0.0

    cr = ci / ri

    return float(cr)


def consistency_spectral(matrix: np.ndarray) -> Dict[str, float]:
    """
    Комплексна оцінка узгодженості з використанням спектральних показників.
    Базується на РЗОД-2011-4.pdf

    Args:
        matrix: Матриця попарних порівнянь (n x n)

    Returns:
        Словник з показниками: lambda_max, CI, CR, is_consistent

    Examples:
        >>> matrix = np.array([[1, 3], [1/3, 1]])
        >>> result = consistency_spectral(matrix)
        >>> result['is_consistent']
        True
    """
    n = matrix.shape[0]
    lambda_max = calculate_lambda_max(matrix)
    ci = calculate_consistency_index(matrix)
    cr = calculate_consistency_ratio(matrix)

    # Критерій узгодженості: CR < 0.10 (РЗОД-2011-4.pdf)
    is_consistent = cr < 0.10

    return {
        'lambda_max': float(lambda_max),
        'n': n,
        'CI': float(ci),
        'CR': float(cr),
        'RI': RANDOM_INDEX.get(n, 1.49),
        'is_consistent': bool(is_consistent),
        'threshold': 0.10,
    }


def calculate_weights_eigenvector(matrix: np.ndarray) -> np.ndarray:
    """
    Розраховує вагові коефіцієнти альтернатив методом власного вектора.
    Базується на РЗОД-2011-4.pdf, РЗОД-2012-1.pdf

    Args:
        matrix: Матриця попарних порівнянь (n x n)

    Returns:
        Вектор вагових коефіцієнтів (нормалізований)

    Examples:
        >>> matrix = np.array([[1, 3], [1/3, 1]])
        >>> weights = calculate_weights_eigenvector(matrix)
        >>> abs(weights.sum() - 1.0) < 0.01
        True
    """
    n = matrix.shape[0]

    # Обчислюємо власні вектори
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        eigenvalues, eigenvectors = eig(matrix)

    # Знаходимо індекс максимального власного значення
    max_idx = np.argmax(np.real(eigenvalues))

    # Беремо відповідний власний вектор
    principal_eigenvector = np.real(eigenvectors[:, max_idx])

    # Нормалізуємо (робимо суму = 1)
    weights = principal_eigenvector / np.sum(principal_eigenvector)

    # Забезпечуємо додатність
    weights = np.abs(weights)
    weights = weights / np.sum(weights)

    return weights


def calculate_weights_geometric_mean(matrix: np.ndarray) -> np.ndarray:
    """
    Розраховує вагові коефіцієнти методом середнього геометричного рядків.
    Базується на РЗОД-2012-1.pdf

    Args:
        matrix: Матриця попарних порівнянь (n x n)

    Returns:
        Вектор вагових коефіцієнтів (нормалізований)

    Examples:
        >>> matrix = np.array([[1, 3], [1/3, 1]])
        >>> weights = calculate_weights_geometric_mean(matrix)
        >>> abs(weights.sum() - 1.0) < 0.01
        True
    """
    n = matrix.shape[0]

    # Обчислюємо середнє геометричне для кожного рядка
    # Формула: w_i = (∏_j a_ij)^(1/n)
    row_products = np.prod(matrix, axis=1)
    geometric_means = np.power(row_products, 1.0 / n)

    # Нормалізуємо
    weights = geometric_means / np.sum(geometric_means)

    return weights


def ideal_pcm(weights: np.ndarray) -> np.ndarray:
    """
    Генерує ідеальну узгоджену МПП (ІУМПП) з вектора ваг.
    Формула: a_ij = w_i / w_j
    Базується на РЗОД-2011-4.pdf

    Args:
        weights: Вектор вагових коефіцієнтів (нормалізований)

    Returns:
        Ідеальна узгоджена матриця попарних порівнянь

    Examples:
        >>> weights = np.array([0.6, 0.3, 0.1])
        >>> ideal = ideal_pcm(weights)
        >>> ideal.shape
        (3, 3)
        >>> abs(ideal[0, 1] - 2.0) < 0.01
        True
    """
    n = len(weights)
    ideal_matrix = np.zeros((n, n))

    for i in range(n):
        for j in range(n):
            if weights[j] != 0:
                ideal_matrix[i, j] = weights[i] / weights[j]
            else:
                ideal_matrix[i, j] = 1.0

    return ideal_matrix


def generate_revision_suggestions(matrix: np.ndarray,
                                  alternatives: List[str],
                                  top_k: int = 5) -> List[Dict]:
    """
    Генерує рекомендації для перегляду найбільш неузгоджених оцінок.
    Базується на РЗОД-2011-4.pdf (зворотний зв'язок з експертом)

    Args:
        matrix: Поточна матриця попарних порівнянь
        alternatives: Список назв альтернатив
        top_k: Кількість рекомендацій для генерації

    Returns:
        Список словників з рекомендаціями

    Examples:
        >>> matrix = np.array([[1, 3, 9], [1/3, 1, 5], [1/9, 1/5, 1]])
        >>> alternatives = ["A1", "A2", "A3"]
        >>> suggestions = generate_revision_suggestions(matrix, alternatives, top_k=2)
        >>> len(suggestions) <= 2
        True
    """
    n = matrix.shape[0]

    # Розраховуємо ваги для ідеальної МПП
    weights = calculate_weights_eigenvector(matrix)

    # Генеруємо ідеальну МПП
    ideal_matrix = ideal_pcm(weights)

    # Обчислюємо відхилення від ідеальної МПП
    deviations = []

    for i in range(n):
        for j in range(i + 1, n):
            current_value = matrix[i, j]
            ideal_value = ideal_matrix[i, j]

            # Обчислюємо відносне відхилення
            if ideal_value != 0:
                deviation = abs(current_value - ideal_value) / ideal_value
            else:
                deviation = abs(current_value - ideal_value)

            deviations.append({
                'alt_i': alternatives[i],
                'alt_j': alternatives[j],
                'current_value': float(current_value),
                'ideal_value': float(ideal_value),
                'deviation': float(deviation),
                'i': i,
                'j': j,
            })

    # Сортуємо за відхиленням (найбільші спочатку)
    deviations.sort(key=lambda x: x['deviation'], reverse=True)

    # Формуємо рекомендації
    suggestions = []
    for dev in deviations[:top_k]:
        suggestion = {
            'comparison': f"{dev['alt_i']} vs {dev['alt_j']}",
            'alt_i': dev['alt_i'],
            'alt_j': dev['alt_j'],
            'current_value': dev['current_value'],
            'suggested_value': dev['ideal_value'],
            'deviation_percent': dev['deviation'] * 100,
            'message': (
                f"Рекомендується переглянути порівняння '{dev['alt_i']}' vs '{dev['alt_j']}'. "
                f"Поточне значення: {dev['current_value']:.2f}, "
                f"ідеальне значення: {dev['ideal_value']:.2f} "
                f"(відхилення {dev['deviation'] * 100:.1f}%)"
            ),
        }
        suggestions.append(suggestion)

    return suggestions


def rank_weights(weights: np.ndarray, alternatives: List[str]) -> List[Dict]:
    """
    Ранжує альтернативи за ваговими коефіцієнтами.

    Args:
        weights: Вектор вагових коефіцієнтів
        alternatives: Список назв альтернатив

    Returns:
        Відсортований список альтернатив з вагами та рангами

    Examples:
        >>> weights = np.array([0.5, 0.3, 0.2])
        >>> alternatives = ["A1", "A2", "A3"]
        >>> ranking = rank_weights(weights, alternatives)
        >>> ranking[0]['rank']
        1
        >>> ranking[0]['alternative']
        'A1'
    """
    # Створюємо список з альтернативами та вагами
    items = [
        {'alternative': alt, 'weight': float(w)}
        for alt, w in zip(alternatives, weights)
    ]

    # Сортуємо за вагою (спадання)
    items.sort(key=lambda x: x['weight'], reverse=True)

    # Додаємо ранги
    for rank, item in enumerate(items, start=1):
        item['rank'] = rank

    return items


if __name__ == "__main__":
    import doctest
    doctest.testmod()

    # Демонстрація роботи модуля
    print("=== Демонстрація модуля consistency.py ===\n")

    # Приклад матриці з помірною неузгодженістю
    matrix = np.array([
        [1, 3, 5, 7],
        [1/3, 1, 3, 5],
        [1/5, 1/3, 1, 3],
        [1/7, 1/5, 1/3, 1],
    ])
    alternatives = ["Варіант_A", "Варіант_B", "Варіант_C", "Варіант_D"]

    print("1. Спектральний аналіз узгодженості:")
    consistency = consistency_spectral(matrix)
    for key, value in consistency.items():
        print(f"   {key}: {value}")

    print("\n2. Вагові коефіцієнти (метод власного вектора):")
    weights_ev = calculate_weights_eigenvector(matrix)
    for alt, w in zip(alternatives, weights_ev):
        print(f"   {alt}: {w:.4f}")

    print("\n3. Вагові коефіцієнти (метод геометричного середнього):")
    weights_gm = calculate_weights_geometric_mean(matrix)
    for alt, w in zip(alternatives, weights_gm):
        print(f"   {alt}: {w:.4f}")

    print("\n4. Ідеальна узгоджена МПП:")
    ideal_matrix = ideal_pcm(weights_ev)
    print(np.round(ideal_matrix, 2))

    print("\n5. Рекомендації для покращення узгодженості:")
    suggestions = generate_revision_suggestions(matrix, alternatives, top_k=3)
    for i, sugg in enumerate(suggestions, 1):
        print(f"   {i}. {sugg['message']}")

    print("\n6. Ранжування альтернатив:")
    ranking = rank_weights(weights_ev, alternatives)
    for item in ranking:
        print(f"   Ранг {item['rank']}: {item['alternative']} (вага: {item['weight']:.4f})")
