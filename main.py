#!/usr/bin/env python3
"""
main.py - Головний модуль для методу експертних попарних порівнянь з уточненням ступеня переваги
Базується на джерелах: РЗОД-2011-2.pdf, РЗОД-2011-3.pdf, РЗОД-2011-4.pdf, РЗОД-2012-1.pdf

Реалізує повний цикл:
1. Завантаження експертних оцінок з JSON
2. Побудова та уніфікація МПП для кожного експерта
3. Оцінка узгодженості та генерація рекомендацій
4. Агрегація групових оцінок
5. Розрахунок вагових коефіцієнтів та ранжування
6. Збереження результатів (weights.csv, consistency.json, suggestions.json)

Використання:
    python main.py --input input.json --out output_dir/
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List
import numpy as np
import pandas as pd

from scales import ScaleType, calculate_informativeness, unify_to_cardinal
from pcm import PairwiseComparisonMatrix
from consistency import (
    consistency_spectral,
    calculate_weights_eigenvector,
    calculate_weights_geometric_mean,
    ideal_pcm,
    generate_revision_suggestions,
    rank_weights,
)
from aggregate import group_aggregate, aggregate_with_statistics, calculate_expert_weights


def load_input_data(input_file: str) -> Dict:
    """
    Завантажує вхідні дані з JSON файлу

    Args:
        input_file: Шлях до JSON файлу

    Returns:
        Словник з даними

    Examples:
        >>> # data = load_input_data("input.json")
        >>> # 'alternatives' in data
        True
    """
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except FileNotFoundError:
        print(f"Помилка: Файл {input_file} не знайдено")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Помилка розбору JSON: {e}")
        sys.exit(1)


def create_output_directory(output_dir: str) -> None:
    """
    Створює директорію для збереження результатів

    Args:
        output_dir: Шлях до директорії
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)


def log_scale_transformations(pcm_list: List[PairwiseComparisonMatrix], output_dir: str) -> None:
    """
    Записує журнал трансформацій шкал у файл

    Args:
        pcm_list: Список МПП від експертів
        output_dir: Директорія для збереження
    """
    log_entries = []

    for pcm in pcm_list:
        for (i, j), (scale_type, n_gradations, original_value) in pcm.original_judgments.items():
            # Пропускаємо обернені оцінки (нижня трикутна частина)
            if i > j:
                continue

            unified_value = pcm.unified_matrix[i, j]
            informativeness = calculate_informativeness(n_gradations)

            entry = {
                'expert_id': pcm.expert_id,
                'comparison': f"{pcm.alternatives[i]} vs {pcm.alternatives[j]}",
                'alt_i': pcm.alternatives[i],
                'alt_j': pcm.alternatives[j],
                'original_scale': scale_type.value,
                'n_gradations': n_gradations,
                'original_value': float(original_value),
                'unified_value': float(unified_value),
                'informativeness': float(informativeness),
            }
            log_entries.append(entry)

    # Зберігаємо як JSON
    log_file = os.path.join(output_dir, 'scale_transformations.json')
    with open(log_file, 'w', encoding='utf-8') as f:
        json.dump(log_entries, f, ensure_ascii=False, indent=2)

    print(f"Журнал трансформацій шкал збережено: {log_file}")


def save_weights(weights: np.ndarray, alternatives: List[str], output_dir: str) -> None:
    """
    Зберігає вагові коефіцієнти у CSV файл

    Args:
        weights: Вектор ваг
        alternatives: Список альтернатив
        output_dir: Директорія для збереження
    """
    # Створюємо ранжування
    ranking = rank_weights(weights, alternatives)

    # Конвертуємо у DataFrame
    df = pd.DataFrame(ranking)

    # Зберігаємо у CSV
    csv_file = os.path.join(output_dir, 'weights.csv')
    df.to_csv(csv_file, index=False, encoding='utf-8')

    print(f"Вагові коефіцієнти збережено: {csv_file}")


def save_consistency_report(consistency_results: Dict, matrix: np.ndarray,
                            alternatives: List[str], output_dir: str) -> None:
    """
    Зберігає звіт про узгодженість у JSON файл

    Args:
        consistency_results: Результати аналізу узгодженості
        matrix: Матриця попарних порівнянь
        alternatives: Список альтернатив
        output_dir: Директорія для збереження
    """
    report = {
        'consistency_analysis': consistency_results,
        'matrix_size': len(alternatives),
        'alternatives': alternatives,
        'aggregated_matrix': matrix.tolist(),
    }

    json_file = os.path.join(output_dir, 'consistency.json')
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"Звіт про узгодженість збережено: {json_file}")


def save_suggestions(suggestions: List[Dict], output_dir: str) -> None:
    """
    Зберігає рекомендації для покращення узгодженості у JSON файл

    Args:
        suggestions: Список рекомендацій
        output_dir: Директорія для збереження
    """
    json_file = os.path.join(output_dir, 'suggestions.json')
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(suggestions, f, ensure_ascii=False, indent=2)

    print(f"Рекомендації збережено: {json_file}")


def process_pairwise_comparisons(input_file: str, output_dir: str) -> None:
    """
    Головна функція обробки попарних порівнянь

    Args:
        input_file: Шлях до вхідного JSON файлу
        output_dir: Директорія для збереження результатів
    """
    print("=" * 80)
    print("МЕТОД ЕКСПЕРТНИХ ПОПАРНИХ ПОРІВНЯНЬ З УТОЧНЕННЯМ СТУПЕНЯ ПЕРЕВАГИ")
    print("=" * 80)
    print()

    # 1. Завантаження даних
    print("1. Завантаження вхідних даних...")
    data = load_input_data(input_file)
    alternatives = data['alternatives']
    experts_data = data['experts']
    competence_coefficients = data.get('competence_coefficients', {})

    print(f"   Альтернативи: {len(alternatives)}")
    print(f"   Експерти: {len(experts_data)}")
    print()

    # 2. Створення МПП для кожного експерта
    print("2. Побудова матриць попарних порівнянь...")
    pcm_list = []

    for expert_data in experts_data:
        expert_id = expert_data['expert_id']
        judgments = expert_data['judgments']

        pcm = PairwiseComparisonMatrix.from_judgments(alternatives, judgments, expert_id)

        # Заповнення неповних МПП через транзитивність
        if pcm.get_status().value == 'incomplete':
            filled_count = pcm.fill_transitive()
            print(f"   {expert_id}: заповнено {filled_count} елементів транзитивно")

        pcm_list.append(pcm)
        print(f"   {expert_id}: {len(judgments)} оцінок, статус: {pcm.get_status().value}")

    print()

    # 3. Оцінка узгодженості для кожного експерта
    print("3. Оцінка узгодженості індивідуальних МПП...")
    for pcm in pcm_list:
        consistency = consistency_spectral(pcm.unified_matrix)
        print(f"   {pcm.expert_id}:")
        print(f"      λ_max = {consistency['lambda_max']:.4f}")
        print(f"      CI = {consistency['CI']:.4f}")
        print(f"      CR = {consistency['CR']:.4f}")
        print(f"      Узгоджена: {'Так' if consistency['is_consistent'] else 'Ні'}")

    print()

    # 4. Агрегація групових оцінок
    print("4. Агрегація групових експертних оцінок...")
    aggregation_result = aggregate_with_statistics(pcm_list, competence_coefficients)
    aggregated_matrix = aggregation_result['aggregated_matrix']

    print("   Ваги експертів:")
    for stats in aggregation_result['expert_statistics']:
        print(f"      {stats['expert_id']}: {stats['weight']:.4f} " +
              f"(компетентність: {stats['competence']:.2f})")

    print()

    # 5. Оцінка узгодженості агрегованої МПП
    print("5. Оцінка узгодженості агрегованої МПП...")
    group_consistency = consistency_spectral(aggregated_matrix)
    print(f"   λ_max = {group_consistency['lambda_max']:.4f}")
    print(f"   CI = {group_consistency['CI']:.4f}")
    print(f"   CR = {group_consistency['CR']:.4f}")
    print(f"   Узгоджена: {'Так' if group_consistency['is_consistent'] else 'Ні'}")
    print()

    # 6. Генерація рекомендацій (якщо неузгоджена)
    suggestions = []
    if not group_consistency['is_consistent']:
        print("6. Генерація рекомендацій для покращення узгодженості...")
        suggestions = generate_revision_suggestions(aggregated_matrix, alternatives, top_k=5)
        for i, sugg in enumerate(suggestions, 1):
            print(f"   {i}. {sugg['comparison']}: "
                  f"поточне {sugg['current_value']:.2f} → "
                  f"рекомендоване {sugg['suggested_value']:.2f} "
                  f"(відхилення {sugg['deviation_percent']:.1f}%)")
        print()

    # 7. Розрахунок вагових коефіцієнтів
    print("7. Розрахунок вагових коефіцієнтів...")
    weights_eigenvector = calculate_weights_eigenvector(aggregated_matrix)
    weights_geometric = calculate_weights_geometric_mean(aggregated_matrix)

    print("   Метод власного вектора:")
    for alt, w in zip(alternatives, weights_eigenvector):
        print(f"      {alt}: {w:.4f}")

    print()
    print("   Метод геометричного середнього:")
    for alt, w in zip(alternatives, weights_geometric):
        print(f"      {alt}: {w:.4f}")

    print()

    # 8. Ранжування альтернатив
    print("8. Ранжування альтернатив (метод власного вектора):")
    ranking = rank_weights(weights_eigenvector, alternatives)
    for item in ranking:
        print(f"   Ранг {item['rank']}: {item['alternative']} (вага: {item['weight']:.4f})")

    print()

    # 9. Збереження результатів
    print("9. Збереження результатів...")
    create_output_directory(output_dir)

    save_weights(weights_eigenvector, alternatives, output_dir)
    save_consistency_report(group_consistency, aggregated_matrix, alternatives, output_dir)
    save_suggestions(suggestions, output_dir)
    log_scale_transformations(pcm_list, output_dir)

    print()
    print("=" * 80)
    print("ОБРОБКА ЗАВЕРШЕНА")
    print("=" * 80)


def main():
    """
    Точка входу програми
    """
    parser = argparse.ArgumentParser(
        description='Метод експертних попарних порівнянь з уточненням ступеня переваги'
    )
    parser.add_argument(
        '--input',
        type=str,
        required=True,
        help='Шлях до вхідного JSON файлу з експертними оцінками'
    )
    parser.add_argument(
        '--out',
        type=str,
        default='out',
        help='Директорія для збереження результатів (за замовчуванням: out/)'
    )

    args = parser.parse_args()

    try:
        process_pairwise_comparisons(args.input, args.out)
    except Exception as e:
        print(f"\nПомилка під час обробки: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
