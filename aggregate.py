"""
Модуль aggregate.py - агрегація групових експертних оцінок
Базується на джерелах: РЗОД-2011-4.pdf, РЗОД-2012-1.pdf

Реалізує:
- Агрегацію МПП від кількох експертів
- Зважування за інформативністю шкал (log₂ N)
- Зважування за коефіцієнтами компетентності експертів
- Комбінаторний метод агрегації
- Геометричне середнє зважене
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from pcm import PairwiseComparisonMatrix
from scales import calculate_informativeness
import warnings


def calculate_judgment_weight(scale_informativeness: float,
                              expert_competence: float) -> float:
    """
    Розраховує ваговий коефіцієнт для окремої експертної оцінки.
    Базується на РЗОД-2011-4.pdf: вага залежить від інформативності шкали та компетентності

    Args:
        scale_informativeness: Інформативність шкали I = log₂ N
        expert_competence: Коефіцієнт компетентності експерта c_l ∈ [0, 1]

    Returns:
        Ваговий коефіцієнт оцінки

    Examples:
        >>> weight = calculate_judgment_weight(3.17, 0.8)
        >>> weight > 0
        True
    """
    # Формула з РЗОД-2011-4.pdf: вага = інформативність × компетентність
    weight = scale_informativeness * expert_competence
    return float(weight)


def aggregate_judgments_geometric(judgments: List[Tuple[float, float]]) -> float:
    """
    Агрегує оцінки різних експертів використовуючи зважене геометричне середнє.
    Базується на РЗОД-2011-4.pdf, РЗОД-2012-1.pdf

    Args:
        judgments: Список пар (значення, вага)

    Returns:
        Агреговане значення

    Examples:
        >>> judgments = [(3.0, 1.0), (5.0, 1.0)]
        >>> result = aggregate_judgments_geometric(judgments)
        >>> 3.5 < result < 4.5
        True
    """
    if not judgments:
        return 1.0

    # Зважене геометричне середнє: (∏ v_i^w_i)^(1/∑w_i)
    values = np.array([j[0] for j in judgments])
    weights = np.array([j[1] for j in judgments])

    # Нормалізуємо ваги
    if np.sum(weights) > 0:
        weights = weights / np.sum(weights)
    else:
        weights = np.ones_like(weights) / len(weights)

    # Обчислюємо зважене геометричне середнє
    # log(GM) = Σ w_i * log(v_i)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        log_values = np.log(values)

    weighted_log_sum = np.sum(weights * log_values)
    geometric_mean = np.exp(weighted_log_sum)

    return float(geometric_mean)


def group_aggregate(pcm_list: List[PairwiseComparisonMatrix],
                   competence_coefficients: Optional[Dict[str, float]] = None) -> np.ndarray:
    """
    Агрегує МПП від кількох експертів у групову МПП з урахуванням інформативності та компетентності.
    Базується на РЗОД-2011-4.pdf (комбінаторний метод агрегації)

    Args:
        pcm_list: Список МПП від різних експертів
        competence_coefficients: Словник {expert_id: коефіцієнт_компетентності}

    Returns:
        Агрегована матриця попарних порівнянь

    Examples:
        >>> from pcm import PairwiseComparisonMatrix
        >>> from scales import ScaleType
        >>> pcm1 = PairwiseComparisonMatrix(["A1", "A2"], "E1")
        >>> pcm1.add_judgment("A1", "A2", 3.0, ScaleType.SAATY_9, 9)
        >>> pcm2 = PairwiseComparisonMatrix(["A1", "A2"], "E2")
        >>> pcm2.add_judgment("A1", "A2", 5.0, ScaleType.SAATY_5, 5)
        >>> aggregated = group_aggregate([pcm1, pcm2])
        >>> aggregated.shape
        (2, 2)
    """
    if not pcm_list:
        raise ValueError("Список МПП порожній")

    # Перевіряємо, що всі МПП мають однакові альтернативи
    n = pcm_list[0].n_alternatives
    alternatives = pcm_list[0].alternatives

    for pcm in pcm_list[1:]:
        if pcm.n_alternatives != n or pcm.alternatives != alternatives:
            raise ValueError("Усі МПП повинні мати однакові альтернативи")

    # Ініціалізуємо агреговану матрицю
    aggregated_matrix = np.ones((n, n))

    # Якщо коефіцієнти компетентності не задані, всі експерти рівнокомпетентні
    if competence_coefficients is None:
        competence_coefficients = {pcm.expert_id: 1.0 for pcm in pcm_list}

    # Агрегуємо кожний елемент матриці
    for i in range(n):
        for j in range(n):
            if i == j:
                aggregated_matrix[i, j] = 1.0
                continue

            # Збираємо оцінки від усіх експертів для цієї пари
            judgments_with_weights = []

            for pcm in pcm_list:
                if pcm.filled_mask[i, j]:
                    # Отримуємо уніфіковане значення
                    value = pcm.unified_matrix[i, j]

                    # Отримуємо інформацію про вихідну шкалу
                    if (i, j) in pcm.original_judgments:
                        scale_type, n_gradations, _ = pcm.original_judgments[(i, j)]
                        informativeness = calculate_informativeness(n_gradations)
                    else:
                        # Якщо інформація про шкалу відсутня (транзитивне заповнення),
                        # використовуємо мінімальну інформативність
                        informativeness = 1.0

                    # Коефіцієнт компетентності
                    competence = competence_coefficients.get(pcm.expert_id, 1.0)

                    # Обчислюємо вагу оцінки
                    weight = calculate_judgment_weight(informativeness, competence)

                    judgments_with_weights.append((value, weight))

            # Агрегуємо за допомогою зваженого геометричного середнього
            if judgments_with_weights:
                aggregated_value = aggregate_judgments_geometric(judgments_with_weights)
                aggregated_matrix[i, j] = aggregated_value
            else:
                # Якщо немає оцінок від жодного експерта, залишаємо 1
                aggregated_matrix[i, j] = 1.0

    # Забезпечуємо зворотну симетрію
    for i in range(n):
        for j in range(i + 1, n):
            if aggregated_matrix[i, j] != 0:
                aggregated_matrix[j, i] = 1.0 / aggregated_matrix[i, j]

    return aggregated_matrix


def calculate_expert_weights(pcm_list: List[PairwiseComparisonMatrix],
                            competence_coefficients: Optional[Dict[str, float]] = None) -> Dict[str, float]:
    """
    Розраховує ваги експертів на основі інформативності їх оцінок та компетентності.
    Базується на РЗОД-2011-4.pdf

    Args:
        pcm_list: Список МПП від різних експертів
        competence_coefficients: Словник {expert_id: коефіцієнт_компетентності}

    Returns:
        Словник {expert_id: нормалізована_вага}

    Examples:
        >>> from pcm import PairwiseComparisonMatrix
        >>> from scales import ScaleType
        >>> pcm1 = PairwiseComparisonMatrix(["A1", "A2"], "E1")
        >>> pcm1.add_judgment("A1", "A2", 3.0, ScaleType.SAATY_9, 9)
        >>> pcm2 = PairwiseComparisonMatrix(["A1", "A2"], "E2")
        >>> pcm2.add_judgment("A1", "A2", 5.0, ScaleType.SAATY_5, 5)
        >>> weights = calculate_expert_weights([pcm1, pcm2])
        >>> sum(weights.values())
        1.0
    """
    if not pcm_list:
        return {}

    if competence_coefficients is None:
        competence_coefficients = {pcm.expert_id: 1.0 for pcm in pcm_list}

    expert_total_weights = {}

    for pcm in pcm_list:
        total_informativeness = 0.0
        n_judgments = 0

        # Рахуємо загальну інформативність оцінок експерта
        for (i, j), (scale_type, n_gradations, _) in pcm.original_judgments.items():
            if i < j:  # Рахуємо тільки верхню трикутну частину
                informativeness = calculate_informativeness(n_gradations)
                total_informativeness += informativeness
                n_judgments += 1

        # Середня інформативність оцінок експерта
        avg_informativeness = total_informativeness / n_judgments if n_judgments > 0 else 1.0

        # Коефіцієнт компетентності
        competence = competence_coefficients.get(pcm.expert_id, 1.0)

        # Загальна вага експерта
        expert_weight = avg_informativeness * competence
        expert_total_weights[pcm.expert_id] = expert_weight

    # Нормалізуємо ваги
    total_weight = sum(expert_total_weights.values())
    if total_weight > 0:
        expert_weights = {
            expert_id: weight / total_weight
            for expert_id, weight in expert_total_weights.items()
        }
    else:
        # Якщо всі ваги 0, розподіляємо рівномірно
        expert_weights = {
            expert_id: 1.0 / len(expert_total_weights)
            for expert_id in expert_total_weights.keys()
        }

    return expert_weights


def aggregate_with_statistics(pcm_list: List[PairwiseComparisonMatrix],
                              competence_coefficients: Optional[Dict[str, float]] = None) -> Dict:
    """
    Агрегує МПП з детальною статистикою процесу агрегації.

    Args:
        pcm_list: Список МПП від різних експертів
        competence_coefficients: Словник {expert_id: коефіцієнт_компетентності}

    Returns:
        Словник з агрегованою матрицею та статистикою

    Examples:
        >>> from pcm import PairwiseComparisonMatrix
        >>> from scales import ScaleType
        >>> pcm1 = PairwiseComparisonMatrix(["A1", "A2"], "E1")
        >>> pcm1.add_judgment("A1", "A2", 3.0, ScaleType.SAATY_9, 9)
        >>> pcm2 = PairwiseComparisonMatrix(["A1", "A2"], "E2")
        >>> pcm2.add_judgment("A1", "A2", 5.0, ScaleType.SAATY_5, 5)
        >>> result = aggregate_with_statistics([pcm1, pcm2])
        >>> 'aggregated_matrix' in result
        True
    """
    # Агрегуємо матриці
    aggregated_matrix = group_aggregate(pcm_list, competence_coefficients)

    # Розраховуємо ваги експертів
    expert_weights = calculate_expert_weights(pcm_list, competence_coefficients)

    # Статистика по експертах
    expert_stats = []
    for pcm in pcm_list:
        n_original_judgments = len([
            (i, j) for (i, j) in pcm.original_judgments.keys() if i < j
        ])

        stats = {
            'expert_id': pcm.expert_id,
            'weight': expert_weights.get(pcm.expert_id, 0.0),
            'competence': competence_coefficients.get(pcm.expert_id, 1.0) if competence_coefficients else 1.0,
            'n_judgments': n_original_judgments,
            'status': pcm.get_status().value,
        }
        expert_stats.append(stats)

    return {
        'aggregated_matrix': aggregated_matrix,
        'expert_weights': expert_weights,
        'expert_statistics': expert_stats,
        'n_experts': len(pcm_list),
        'alternatives': pcm_list[0].alternatives,
    }


if __name__ == "__main__":
    import doctest
    doctest.testmod()

    # Демонстрація роботи модуля
    print("=== Демонстрація модуля aggregate.py ===\n")

    from pcm import PairwiseComparisonMatrix
    from scales import ScaleType

    alternatives = ["Проект_A", "Проект_B", "Проект_C", "Проект_D"]

    # Експерт 1 (висока компетентність, шкала Сааті-9)
    pcm1 = PairwiseComparisonMatrix(alternatives, expert_id="Експерт_1")
    pcm1.add_judgment("Проект_A", "Проект_B", 3.0, ScaleType.SAATY_9, 9)
    pcm1.add_judgment("Проект_A", "Проект_C", 5.0, ScaleType.SAATY_9, 9)
    pcm1.add_judgment("Проект_A", "Проект_D", 7.0, ScaleType.SAATY_9, 9)
    pcm1.add_judgment("Проект_B", "Проект_C", 3.0, ScaleType.SAATY_9, 9)
    pcm1.add_judgment("Проект_B", "Проект_D", 5.0, ScaleType.SAATY_9, 9)
    pcm1.add_judgment("Проект_C", "Проект_D", 3.0, ScaleType.SAATY_9, 9)

    # Експерт 2 (середня компетентність, шкала Сааті-5)
    pcm2 = PairwiseComparisonMatrix(alternatives, expert_id="Експерт_2")
    pcm2.add_judgment("Проект_A", "Проект_B", 5.0, ScaleType.SAATY_5, 5)
    pcm2.add_judgment("Проект_A", "Проект_C", 7.0, ScaleType.SAATY_5, 5)
    pcm2.add_judgment("Проект_A", "Проект_D", 9.0, ScaleType.SAATY_5, 5)
    pcm2.add_judgment("Проект_B", "Проект_C", 5.0, ScaleType.SAATY_5, 5)
    pcm2.add_judgment("Проект_B", "Проект_D", 5.0, ScaleType.SAATY_5, 5)
    pcm2.add_judgment("Проект_C", "Проект_D", 5.0, ScaleType.SAATY_5, 5)

    # Коефіцієнти компетентності
    competence = {
        "Експерт_1": 0.8,
        "Експерт_2": 0.6,
    }

    print("1. Ваги експертів:")
    expert_weights = calculate_expert_weights([pcm1, pcm2], competence)
    for expert_id, weight in expert_weights.items():
        print(f"   {expert_id}: {weight:.4f}")

    print("\n2. Агрегація МПП:")
    result = aggregate_with_statistics([pcm1, pcm2], competence)
    print(f"   Кількість експертів: {result['n_experts']}")

    print("\n3. Агрегована матриця:")
    print(np.round(result['aggregated_matrix'], 2))

    print("\n4. Статистика по експертах:")
    for stats in result['expert_statistics']:
        print(f"   {stats['expert_id']}:")
        print(f"      Вага: {stats['weight']:.4f}")
        print(f"      Компетентність: {stats['competence']:.2f}")
        print(f"      Кількість оцінок: {stats['n_judgments']}")
        print(f"      Статус МПП: {stats['status']}")
