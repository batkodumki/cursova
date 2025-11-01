#!/usr/bin/env python3
"""
Тестування моделей GUI без використання tkinter
"""

import sys
import os

# Додаємо поточну директорію до шляху
sys.path.insert(0, os.path.dirname(__file__))

from gui.models import SessionModel, Judgment, Expert, ScaleType, ScaleManager


def test_session_model():
    """Тестування SessionModel"""
    print("=" * 60)
    print("Тестування SessionModel")
    print("=" * 60)

    # Створюємо сесію
    session = SessionModel()

    # Ініціалізуємо
    alternatives = ["Проект_A", "Проект_B", "Проект_C"]
    expert_ids = ["Експерт_1", "Експерт_2"]
    competence = {"Експерт_1": 0.85, "Експерт_2": 0.60}

    session.initialize_session(alternatives, expert_ids, competence)

    print(f"\n1. Ініціалізація:")
    print(f"   Альтернативи: {session.alternatives}")
    print(f"   Експерти: {[e.expert_id for e in session.experts]}")
    print(f"   Кількість пар: {len(session.all_pairs)}")

    # Додаємо оцінки
    print(f"\n2. Додавання оцінок:")
    for i in range(min(3, len(session.all_pairs))):
        pair = session.get_current_pair()
        expert = session.get_current_expert()

        if pair and expert:
            judgment = Judgment(
                alt_i=pair[0],
                alt_j=pair[1],
                value=3.0,
                scale_type=ScaleType.SAATY_9,
                n_gradations=9
            )
            session.add_judgment(judgment)
            print(f"   {expert.expert_id}: {pair[0]} vs {pair[1]} = 3.0 (Сааті-9)")

            session.next_pair()

    # Прогрес
    progress = session.get_progress()
    print(f"\n3. Прогрес: {progress[0]}/{progress[1]}")

    # Збереження
    session_file = "test_session.json"
    session.save_session(session_file)
    print(f"\n4. Сесію збережено: {session_file}")

    # Завантаження
    loaded_session = SessionModel.load_session(session_file)
    print(f"5. Сесію завантажено: {len(loaded_session.experts)} експертів")

    # Очистка
    os.remove(session_file)

    print("\n✓ Тест SessionModel пройдено успішно!")
    return True


def test_scale_manager():
    """Тестування ScaleManager"""
    print("\n" + "=" * 60)
    print("Тестування ScaleManager")
    print("=" * 60)

    # Доступні шкали
    scales = ScaleManager.get_available_scales()
    print(f"\n1. Доступні шкали ({len(scales)}):")
    for scale_type, desc in scales:
        min_grad, max_grad = ScaleManager.get_scale_gradations_range(scale_type)
        print(f"   - {desc} (діапазон: {min_grad}-{max_grad} градацій)")

    # Лінгвістичні мітки
    print(f"\n2. Лінгвістичні мітки для Сааті-9:")
    for i in range(9):
        label = ScaleManager.get_linguistic_label(ScaleType.SAATY_9, 9, i)
        print(f"   Градація {i}: {label}")

    # Уточнення шкали
    print(f"\n3. Уточнення шкали:")
    refinement = ScaleManager.suggest_scale_refinement(ScaleType.SAATY_5, 5)
    if refinement:
        new_scale, new_grad = refinement
        print(f"   Сааті-5 (5) → {new_scale.value} ({new_grad} градацій)")

    print("\n✓ Тест ScaleManager пройдено успішно!")
    return True


def test_demo_session():
    """Тестування завантаження демо-сесії"""
    print("\n" + "=" * 60)
    print("Тестування завантаження demo_session.json")
    print("=" * 60)

    demo_file = "demo_session.json"
    if not os.path.exists(demo_file):
        print(f"\n✗ Файл {demo_file} не знайдено")
        return False

    try:
        session = SessionModel.load_session(demo_file)
        print(f"\n1. Завантажено:")
        print(f"   Альтернативи: {len(session.alternatives)}")
        print(f"   Експерти: {len(session.experts)}")

        # Показуємо статистику по експертах
        print(f"\n2. Статистика по експертах:")
        for expert in session.experts:
            print(f"   {expert.expert_id}:")
            print(f"      Компетентність: {expert.competence:.2f}")
            print(f"      Кількість оцінок: {len(expert.judgments)}")

        # Обчислюємо результати
        if session.is_complete():
            print(f"\n3. Обчислення результатів...")
            results = session.calculate_results()

            print(f"\n4. Результати:")
            print(f"   Узгодженість:")
            print(f"      λ_max = {results['consistency']['lambda_max']:.4f}")
            print(f"      CI = {results['consistency']['CI']:.4f}")
            print(f"      CR = {results['consistency']['CR']:.4f}")
            print(f"      Узгоджена: {'Так' if results['consistency']['is_consistent'] else 'Ні'}")

            print(f"\n   Ранжування:")
            for item in results['ranking'][:3]:
                print(f"      {item['rank']}. {item['alternative']}: {item['weight']:.4f}")

        print("\n✓ Тест demo_session.json пройдено успішно!")
        return True

    except Exception as e:
        print(f"\n✗ Помилка: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Головна функція тестування"""
    print("\n" + "=" * 60)
    print("ТЕСТУВАННЯ GUI МОДЕЛЕЙ")
    print("=" * 60)

    tests = [
        ("SessionModel", test_session_model),
        ("ScaleManager", test_scale_manager),
        ("Demo Session", test_demo_session),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"\n✗ Тест '{name}' провалено з помилкою: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 60)
    print(f"РЕЗУЛЬТАТИ: {passed} пройдено, {failed} провалено")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
