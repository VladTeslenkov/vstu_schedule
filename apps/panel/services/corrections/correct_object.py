"""Функции для работы с CorrectObject."""

import logging
from typing import Optional

from django.db import transaction

from apps.panel.models import CorrectObject, Scope
from apps.panel.services.corrections.context import ContextElement, parse_context_elements

logger = logging.getLogger("apps.panel.services.corrections")


def find_or_create_correct_object(
    value: str,
    scope_id: int = 0,
    external_id: Optional[str] = None,
    name: Optional[str] = None,
    description: Optional[str] = None,
    required_context_elements: Optional[list[ContextElement]] = None,
    context: Optional[list[ContextElement]] = None,
) -> CorrectObject:
    """
    Поиск или создание CorrectObject с проверкой дубликатов.
    
    Ключ поиска:
    - external_id (приоритет, если указан)
    - value + required_context_elements (если external_id не указан)
    """
    if required_context_elements is None:
        required_context_elements = []
    if context is None:
        context = []
    
    # Преобразуем ContextElement в словари для JSONField
    required_context_dicts = [elem.to_dict() for elem in required_context_elements]
    context_dicts = [elem.to_dict() for elem in context]
    
    with transaction.atomic():
        # Поиск по external_id (приоритет)
        if external_id:
            try:
                correct_object = CorrectObject.objects.get(
                    external_id=external_id,
                    scope_id=scope_id
                )
                logger.debug(f"Найден CorrectObject #{correct_object.id} по external_id={external_id}")
                return correct_object
            except CorrectObject.DoesNotExist:
                pass
        
        # Поиск по value + required_context_elements
        try:
            correct_object = CorrectObject.objects.get(
                value=value,
                required_context_elements=required_context_dicts,
                scope_id=scope_id,
                external_id__isnull=True
            )
            logger.debug(f"Найден CorrectObject #{correct_object.id} по value и context")
            return correct_object
        except CorrectObject.DoesNotExist:
            pass
        
        # Создание нового
        correct_object = CorrectObject.objects.create(
            value=value,
            external_id=external_id,
            name=name,
            description=description,
            required_context_elements=required_context_dicts,
            context=context_dicts,
            scope_id=scope_id,
        )
        logger.info(f"Создан новый CorrectObject #{correct_object.id} для value={value[:50]}")
        return correct_object
