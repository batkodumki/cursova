"""
Модуль models.py - адаптери між GUI та основними модулями
Забезпечує зв'язок між інтерфейсом користувача та логікою попарних порівнянь
"""

import json
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field, asdict
from enum import Enum

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from scales import ScaleType, get_scale_values, calculate_informativeness, unify_judgment, create_transformation_log
from pcm import PairwiseComparisonMatrix, PCMStatus
from consistency import (
    consistency_spectral,
    calculate_weights_eigenvector,
    generate_revision_suggestions,
    rank_weights
)
from aggregate import group_aggregate, aggregate_with_statistics


@dataclass
class Alternative:
    """Альтернатива для порівняння"""
    name: str
    index: int


@dataclass
class Judgment:
    """Експертна оцінка порівняння"""
    alt_i: str
    alt_j: str
    value: float
    scale_type: ScaleType
    n_gradations: int
    scale_history: List[Tuple[ScaleType, int]] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Конвертує оцінку в словник для серіалізації"""
        return {
            'alt_i': self.alt_i,
            'alt_j': self.alt_j,
            'value': float(self.value),
            'scale_type': self.scale_type.value,
            'n_gradations': self.n_gradations,
            'scale_history': [(st.value, n) for st, n in self.scale_history]
        }


@dataclass
class Expert:
    """Експерт з коефіцієнтом компетентності"""
    expert_id: str
    competence: float = 1.0
    judgments: List[Judgment] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Конвертує експерта в словник"""
        return {
            'expert_id': self.expert_id,
            'competence': self.competence,
            'judgments': [j.to_dict() for j in self.judgments]
        }


class SessionModel:
    """
    Модель сесії експертизи.
    Зберігає стан всього процесу попарних порівнянь.
    """

    def __init__(self):
        self.alternatives: List[str] = []
        self.experts: List[Expert] = []
        self.current_expert_idx: int = 0
        self.current_pair_idx: int = 0
        self.all_pairs: List[Tuple[str, str]] = []

    def initialize_session(self, alternatives: List[str], expert_ids: List[str],
                          competence_coefficients: Optional[Dict[str, float]] = None):
        """
        Ініціалізує нову сесію експертизи

        Args:
            alternatives: Список назв альтернатив
            expert_ids: Список ідентифікаторів експертів
            competence_coefficients: Коефіцієнти компетентності
        """
        self.alternatives = alternatives
        self.all_pairs = self._generate_pairs(alternatives)

        # Створюємо експертів
        self.experts = []
        for expert_id in expert_ids:
            competence = 1.0
            if competence_coefficients and expert_id in competence_coefficients:
                competence = competence_coefficients[expert_id]
            self.experts.append(Expert(expert_id, competence))

        self.current_expert_idx = 0
        self.current_pair_idx = 0

    def _generate_pairs(self, alternatives: List[str]) -> List[Tuple[str, str]]:
        """Генерує всі пари альтернатив для порівняння"""
        pairs = []
        for i in range(len(alternatives)):
            for j in range(i + 1, len(alternatives)):
                pairs.append((alternatives[i], alternatives[j]))
        return pairs

    def get_current_pair(self) -> Optional[Tuple[str, str]]:
        """Повертає поточну пару для порівняння"""
        if self.current_pair_idx < len(self.all_pairs):
            return self.all_pairs[self.current_pair_idx]
        return None

    def get_current_expert(self) -> Optional[Expert]:
        """Повертає поточного експерта"""
        if 0 <= self.current_expert_idx < len(self.experts):
            return self.experts[self.current_expert_idx]
        return None

    def add_judgment(self, judgment: Judgment):
        """Додає експертну оцінку"""
        expert = self.get_current_expert()
        if expert:
            expert.judgments.append(judgment)

    def next_pair(self) -> bool:
        """
        Переходить до наступної пари

        Returns:
            True якщо є наступна пара, False якщо закінчились пари
        """
        self.current_pair_idx += 1
        if self.current_pair_idx >= len(self.all_pairs):
            # Переходимо до наступного експерта
            return self.next_expert()
        return True

    def prev_pair(self) -> bool:
        """
        Повертається до попередньої пари

        Returns:
            True якщо можливо повернутися
        """
        if self.current_pair_idx > 0:
            self.current_pair_idx -= 1
            return True
        elif self.current_expert_idx > 0:
            self.current_expert_idx -= 1
            self.current_pair_idx = len(self.all_pairs) - 1
            return True
        return False

    def next_expert(self) -> bool:
        """
        Переходить до наступного експерта

        Returns:
            True якщо є наступний експерт, False якщо закінчились експерти
        """
        self.current_expert_idx += 1
        self.current_pair_idx = 0
        return self.current_expert_idx < len(self.experts)

    def get_progress(self) -> Tuple[int, int]:
        """
        Повертає прогрес виконання

        Returns:
            (completed_pairs, total_pairs)
        """
        completed = self.current_expert_idx * len(self.all_pairs) + self.current_pair_idx
        total = len(self.experts) * len(self.all_pairs)
        return (completed, total)

    def is_complete(self) -> bool:
        """Перевіряє чи завершено всі порівняння"""
        return self.current_expert_idx >= len(self.experts)

    def build_pcm_list(self) -> List[PairwiseComparisonMatrix]:
        """Будує список МПП для всіх експертів"""
        pcm_list = []

        for expert in self.experts:
            judgments_dict = [j.to_dict() for j in expert.judgments]
            pcm = PairwiseComparisonMatrix.from_judgments(
                self.alternatives,
                judgments_dict,
                expert.expert_id
            )

            # Заповнюємо неповні МПП через транзитивність
            if pcm.get_status() == PCMStatus.INCOMPLETE and pcm.check_connectivity():
                pcm.fill_transitive()

            pcm_list.append(pcm)

        return pcm_list

    def calculate_results(self) -> Dict:
        """
        Обчислює остаточні результати з журналом трансформацій.
        Базується на РЗОД-2011-4.pdf (уніфікація та агрегація)

        Returns:
            Словник з результатами: ваги, узгодженість, рекомендації, transformations
        """
        pcm_list = self.build_pcm_list()

        # Коефіцієнти компетентності
        competence_coefficients = {
            expert.expert_id: expert.competence
            for expert in self.experts
        }

        # Агрегація
        aggregation_result = aggregate_with_statistics(pcm_list, competence_coefficients)
        aggregated_matrix = aggregation_result['aggregated_matrix']

        # Узгодженість
        consistency = consistency_spectral(aggregated_matrix)

        # Ваги
        weights = calculate_weights_eigenvector(aggregated_matrix)

        # Ранжування
        ranking = rank_weights(weights, self.alternatives)

        # Рекомендації
        suggestions = []
        if not consistency['is_consistent']:
            suggestions = generate_revision_suggestions(
                aggregated_matrix,
                self.alternatives,
                top_k=5
            )

        # Журнал трансформацій шкал
        transformations = []
        for expert in self.experts:
            for judgment in expert.judgments:
                # Створюємо запис трансформації
                comparison = f"{judgment.alt_i} vs {judgment.alt_j}"
                unified_value = unify_judgment(
                    judgment.scale_type,
                    judgment.n_gradations,
                    judgment.value
                )
                log_entry = create_transformation_log(
                    expert.expert_id,
                    comparison,
                    judgment.scale_type,
                    judgment.n_gradations,
                    judgment.value,
                    unified_value
                )
                transformations.append(log_entry)

        return {
            'aggregated_matrix': aggregated_matrix,
            'consistency': consistency,
            'weights': weights,
            'ranking': ranking,
            'suggestions': suggestions,
            'expert_weights': aggregation_result['expert_weights'],
            'expert_statistics': aggregation_result['expert_statistics'],
            'scale_transformations': transformations
        }

    def save_session(self, filename: str):
        """Зберігає сесію у JSON файл"""
        session_data = {
            'alternatives': self.alternatives,
            'experts': [expert.to_dict() for expert in self.experts],
            'competence_coefficients': {
                expert.expert_id: expert.competence
                for expert in self.experts
            },
            'current_expert_idx': self.current_expert_idx,
            'current_pair_idx': self.current_pair_idx
        }

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(session_data, f, ensure_ascii=False, indent=2)

    @staticmethod
    def load_session(filename: str) -> 'SessionModel':
        """Завантажує сесію з JSON файлу"""
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)

        session = SessionModel()
        session.alternatives = data['alternatives']
        session.all_pairs = session._generate_pairs(session.alternatives)

        # Завантажуємо експертів
        session.experts = []
        for expert_data in data['experts']:
            expert = Expert(
                expert_id=expert_data['expert_id'],
                competence=expert_data.get('competence', 1.0)
            )

            # Завантажуємо оцінки
            for judgment_data in expert_data['judgments']:
                scale_type = ScaleType(judgment_data['scale_type'])
                judgment = Judgment(
                    alt_i=judgment_data['alt_i'],
                    alt_j=judgment_data['alt_j'],
                    value=judgment_data['value'],
                    scale_type=scale_type,
                    n_gradations=judgment_data['n_gradations']
                )

                # Завантажуємо історію шкал
                if 'scale_history' in judgment_data:
                    judgment.scale_history = [
                        (ScaleType(st), n) for st, n in judgment_data['scale_history']
                    ]

                expert.judgments.append(judgment)

            session.experts.append(expert)

        session.current_expert_idx = data.get('current_expert_idx', 0)
        session.current_pair_idx = data.get('current_pair_idx', 0)

        return session


class ScaleManager:
    """
    Менеджер для роботи зі шкалами та адаптивним уточненням.
    Реалізує покрокове уточнення ступеня переваги.
    """

    # Лінгвістичні фрази для кожної шкали (українською)
    # Базується на РЗОД-2011-3.pdf та класичній шкалі Сааті
    LINGUISTIC_LABELS = {
        ScaleType.ORDINAL: {
            2: ["Рівноцінні", "Переважає"]
        },
        ScaleType.SAATY_9: {
            3: ["Рівноцінні", "Помірно", "Дуже сильно"],
            5: ["Рівноцінні", "Слабко", "Помірно", "Сильно", "Дуже сильно"],
            7: ["Рівноцінні", "Дуже слабко", "Слабко", "Помірно слабко",
                "Помірно", "Помірно сильно", "Сильно", "Дуже сильно"],
            9: ["Рівноцінні", "Дуже слабко", "Слабко", "Помірно слабко",
                "Помірно", "Помірно сильно", "Сильно", "Дуже сильно",
                "Надзвичайно сильно"]
        },
        ScaleType.BALANCED: {},  # Генеруються автоматично
        ScaleType.POWER: {},  # Генеруються автоматично
        ScaleType.MA_ZHENG: {},  # Генеруються автоматично
        ScaleType.DONEGAN: {}  # Генеруються автоматично
    }

    @staticmethod
    def get_available_scales() -> List[Tuple[ScaleType, str]]:
        """
        Повертає список всіх 6 доступних шкал з описами.
        Базується на РЗОД-2011-3.pdf
        """
        return [
            (ScaleType.ORDINAL, "Ординальна (2 градації)"),
            (ScaleType.SAATY_9, "Цілочислова/Сааті-9 (3-9 градацій)"),
            (ScaleType.BALANCED, "Збалансована (3-9 градацій)"),
            (ScaleType.POWER, "Степенева (3-9 градацій)"),
            (ScaleType.MA_ZHENG, "Ма-Чженга (3-9 градацій)"),
            (ScaleType.DONEGAN, "Донегана-Додд-МакМастера (3-9 градацій)"),
        ]

    @staticmethod
    def get_scale_gradations_range(scale_type: ScaleType) -> Tuple[int, int]:
        """Повертає діапазон градацій для шкали"""
        from scales import SCALE_GRADATIONS_RANGE
        return SCALE_GRADATIONS_RANGE.get(scale_type, (3, 9))

    @staticmethod
    def get_linguistic_label(scale_type: ScaleType, n_gradations: int,
                            grade_index: int) -> str:
        """
        Повертає лінгвістичну мітку для градації

        Args:
            scale_type: Тип шкали
            n_gradations: Кількість градацій
            grade_index: Індекс градації (0-based)

        Returns:
            Лінгвістична мітка
        """
        if scale_type in ScaleManager.LINGUISTIC_LABELS:
            labels_dict = ScaleManager.LINGUISTIC_LABELS[scale_type]
            if n_gradations in labels_dict:
                labels = labels_dict[n_gradations]
                if 0 <= grade_index < len(labels):
                    return labels[grade_index]

        # Генеруємо числову мітку за замовчуванням
        values = get_scale_values(scale_type, n_gradations)
        if 0 <= grade_index < len(values):
            return f"Градація {grade_index + 1} (≈ {values[grade_index]:.1f})"

        return f"Градація {grade_index + 1}"

    @staticmethod
    def suggest_scale_refinement(scale_type: ScaleType, n_gradations: int) -> Optional[Tuple[ScaleType, int]]:
        """
        Пропонує уточнення шкали (збільшення детальності).
        Реалізує покрокове уточнення згідно Opys_Рівень.doc та РЗОД-2011-2.pdf

        Args:
            scale_type: Поточний тип шкали
            n_gradations: Поточна кількість градацій

        Returns:
            (новий_тип, нова_кількість) або None якщо уточнення неможливе

        Логіка уточнення:
            Ординальна (2) → Сааті-9 (3) → Сааті-9 (5) → Сааті-9 (7) → Сааті-9 (9)
            Або вибір іншої шкали (Збалансована/Степенева/Ма-Чженга/Донегана)
        """
        min_grad, max_grad = ScaleManager.get_scale_gradations_range(scale_type)

        # Можемо збільшити кількість градацій у межах поточної шкали
        if n_gradations < max_grad:
            # Збільшуємо на 2 градації (3→5→7→9)
            new_n = min(n_gradations + 2, max_grad)
            return (scale_type, new_n)

        # Якщо ординальна - переходимо до Сааті-9 з 3 градаціями
        if scale_type == ScaleType.ORDINAL:
            return (ScaleType.SAATY_9, 3)

        # Якщо досягнуто максимуму для поточної шкали - пропонуємо іншу
        if scale_type == ScaleType.SAATY_9 and n_gradations == 9:
            # Можна запропонувати спробувати іншу шкалу для експериментів
            return None

        return None
