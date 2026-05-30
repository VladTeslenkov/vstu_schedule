from collections.abc import Mapping
from typing import Any, Literal, cast

from django.db.models import Q, QuerySet
from django.utils import timezone

import apps.common.services.timetable.read.filters as filters
from apps.common.models import (
    Alert,
    CommonModel,
)


def active_alerts() -> QuerySet[Alert]:
    now = timezone.now()
    return Alert.objects.filter(
        Q(starts_at__isnull=True) | Q(starts_at__lte=now),
        Q(expires_at__isnull=True) | Q(expires_at__gt=now),
        is_enabled=True,
    )


def public_alerts() -> QuerySet[Alert]:
    return active_alerts().filter(is_admin=False)


def admin_alerts() -> QuerySet[Alert]:
    return active_alerts().filter(is_admin=True)


class Selector:
    filter_query: dict[str, Any]
    q_filters: list[Q]
    filters_order: list[tuple[Literal["q"], Q] | tuple[Literal["dict"], list[str]]]
    found_models: QuerySet

    def __init__(self, filter_query: filters.FilterQuery | None = None):
        self.filter_query = {}
        self.q_filters = []
        self.filters_order = []

        if filter_query:
            self.add_filter(filter_query)

    def add_filter(self, filter_query: filters.FilterQuery):
        """Updates filter query by adding new filter

        Allows user manualy append filters in format {'field_name' : value}
        """
        if isinstance(filter_query, Q):
            self.q_filters.append(filter_query)
            self.filters_order.append(("q", filter_query))
            return

        if isinstance(filter_query, Mapping):
            keys = list(filter_query.keys())
            self.filter_query.update(dict(filter_query))
            self.filters_order.append(("dict", keys))
            return

        raise TypeError(f"Unsupported filter type: {type(filter_query)!r}")

    def remove_filter(self, index: int):
        if index < 0 or index >= len(self.filters_order):
            return

        filter_type, payload = self.filters_order.pop(index)

        if filter_type == "q":
            self.q_filters.remove(cast(Q, payload))
            return

        for key in cast(list[str], payload):
            self.filter_query.pop(key, None)

    def remove_first_filter(self):
        self.remove_filter(0)

    def remove_last_filter(self):
        self.remove_filter(len(self.filters_order) - 1)

    def clear_filter_query(self):
        self.filter_query = {}
        self.q_filters = []
        self.filters_order = []

    def find_models(self, model: type[CommonModel]):
        """Finds filtered models"""
        self.found_models = cast(Any, model).objects.filter(*self.q_filters, **self.filter_query)

    def get_found_models(self) -> QuerySet:
        """Returns found models

        Can be empty if nothing found
        """
        return self.found_models

    def get_filter_query(self) -> dict[str, Any]:
        return self.filter_query

    def get_q_filters(self) -> list[Q]:
        return self.q_filters

    def is_any_model_found(self):
        return self.found_models.exists()

    def is_single_model_found(self):
        return self.found_models.count() == 1

    def has_any_filter_added(self):
        return bool(self.filter_query or self.q_filters)
