from itertools import islice

from django.db.models import QuerySet

import apps.common.services.timetable.read.filters as filters
from apps.common.models import (
    CommonModel,
)


class Selector:
    filter_query : dict
    found_models : QuerySet

    def __init__(self, filter_query : dict | None = None):
        self.filter_query = filter_query or {}

    def add_filter(self, filter : filters.UtilityFilterBase | dict):
        """Updates filter query by adding new filter

        Allows user manualy append filters in format {'field_name' : value}
        """
        # TODO: UtilityFilterBase не словарь, поэтому с ним это не сработает
        self.filter_query.update(filter)

    def remove_filter(self, index : int):
        if index < len(self.filter_query):
            del self.filter_query[next(islice(self.filter_query, index, None))]

    def remove_first_filter(self):
        self.remove_filter(0)

    def remove_last_filter(self):
        self.remove_filter(len(self.filter_query) - 1)

    def clear_filter_query(self):
        self.filter_query = {}

    def find_models(self, model : type[CommonModel]):
        """Finds filtered models
        """
        self.found_models = model.objects.filter(**self.filter_query)

    def get_found_models(self) -> QuerySet:
        """Returns found models

        Can be empty if nothing found
        """
        return self.found_models

    def get_filter_query(self) -> dict:
        return self.filter_query

    def is_any_model_found(self):
        return self.found_models.exists()

    def is_single_model_found(self):
        return self.found_models.count() == 1

    def has_any_filter_added(self):
        return bool(self.filter_query)
