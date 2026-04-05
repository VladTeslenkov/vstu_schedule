from django.test import TestCase

from apps.common.models import (
    ScheduleTemplateMetadata,
)
from apps.common.services.timetable.utilities.normalizers import (
    normalize_place_building_and_room,
    normalize_time_slot_display_name,
)
from apps.common.services.timetable.utilities.utilities import (
    get_name_from_month_number,
    get_scope_from_label,
    replace_roman_with_arabic_numerals,
)

"""python manage.py test apps.common.tests.test_utilities
"""


class TestUtilities(TestCase):
    def test_normalize_full_place_repr(self):
        EXPECTED_VALUE = ("В", "902б")

        self.assertSequenceEqual(
            normalize_place_building_and_room("В, 902б"),
            EXPECTED_VALUE
        )
        self.assertSequenceEqual(
            normalize_place_building_and_room("В,902б"),
            EXPECTED_VALUE
        )
        self.assertSequenceEqual(
            normalize_place_building_and_room("В 902б"),
            EXPECTED_VALUE
        )
        self.assertSequenceEqual(
            normalize_place_building_and_room("В-902б"),
            EXPECTED_VALUE
        )

    def test_normalize_half_place_repr(self):
        self.assertSequenceEqual(
            normalize_place_building_and_room("902б"),
            ("", "902б")
        )
        self.assertEqual(
            normalize_place_building_and_room("В-"),
            None
        )
        self.assertSequenceEqual(
            normalize_place_building_and_room("В902б"),
            ("", "В902б")
        )

    def test_month_number_into_name(self):
        MONTH_NUMBERS = [1, 6, 12]
        NOT_EXISTING_MONTH_NUMBERS = [0, -12, 13]
        EXISTING_AND_NOT_MONTH_NUMBERS = [9, -1, 3, 99]

        EXPECTED_MONTH_NAMES = ["Январь", "Июнь", "Декабрь"]
        EXPECTED_NOT_EXISTING_MONTH_NAMES = [None, None, None]
        EXPECTED_EXISTING_AND_NOT_MONTH_NAMES = ["Сентябрь", None, "Март", None]

        self.assertEqual(
            get_name_from_month_number(MONTH_NUMBERS[0]),
            EXPECTED_MONTH_NAMES[0]
        )
        self.assertSequenceEqual(
            get_name_from_month_number(MONTH_NUMBERS),
            EXPECTED_MONTH_NAMES
        )
        self.assertSequenceEqual(
            get_name_from_month_number(NOT_EXISTING_MONTH_NUMBERS),
            EXPECTED_NOT_EXISTING_MONTH_NAMES
        )
        self.assertSequenceEqual(
            get_name_from_month_number(EXISTING_AND_NOT_MONTH_NUMBERS),
            EXPECTED_EXISTING_AND_NOT_MONTH_NAMES
        )

    def test_normalize_time_slot(self):
        self.assertSequenceEqual(
            normalize_time_slot_display_name("1-2"),
            ("1-2", "", "")
        )
        self.assertSequenceEqual(
            normalize_time_slot_display_name("13.00"),
            ("", "13:00", "")
        )
        self.assertSequenceEqual(
            normalize_time_slot_display_name("18:00"),
            ("", "18:00", "")
        )
        self.assertSequenceEqual(
            normalize_time_slot_display_name("8:30 - 10.00"),
            ("", "8:30", "10:00")
        )
        self.assertSequenceEqual(
            normalize_time_slot_display_name("8.30 10:00"),
            ("", "8:30", "10:00")
        )

    def test_get_scope_value(self):
        # common
        self.assertEqual(
            get_scope_from_label("бакалавриат"),
            ScheduleTemplateMetadata.Scope.BACHELOR
        )
        self.assertEqual(
            get_scope_from_label("Магистратура"),
            ScheduleTemplateMetadata.Scope.MASTER
        )
        self.assertEqual(
            get_scope_from_label("   аспирантура "),
            ScheduleTemplateMetadata.Scope.POSTGRADUATE
        )
        self.assertEqual(
            get_scope_from_label("Консультация   "),
            ScheduleTemplateMetadata.Scope.CONSULTATION
        )

        self.assertEqual(
            get_scope_from_label("бакалавры"),
            ScheduleTemplateMetadata.Scope.BACHELOR
        )
        self.assertEqual(
            get_scope_from_label(" бакалавров"),
            ScheduleTemplateMetadata.Scope.BACHELOR
        )
        self.assertEqual(
            get_scope_from_label("магистры "),
            ScheduleTemplateMetadata.Scope.MASTER
        )
        self.assertEqual(
            get_scope_from_label("магистров"),
            ScheduleTemplateMetadata.Scope.MASTER
        )
        self.assertEqual(
            get_scope_from_label("  аспиранты "),
            ScheduleTemplateMetadata.Scope.POSTGRADUATE
        )
        self.assertEqual(
            get_scope_from_label(" аспирантов  "),
            ScheduleTemplateMetadata.Scope.POSTGRADUATE
        )
        self.assertEqual(
            get_scope_from_label("консульт."),
            ScheduleTemplateMetadata.Scope.CONSULTATION
        )

        self.assertEqual(
            get_scope_from_label("бак."),
            None
        )
        self.assertEqual(
            get_scope_from_label("асп."),
            None
        )

    def test_replace_roman_with_arabic_numerals(self):
        self.assertEqual(
            replace_roman_with_arabic_numerals("Учебные занятия 3 курса ФАТ магистров I-ого семестра 2024-2025 учебного года"),
            "Учебные занятия 3 курса ФАТ магистров 1-ого семестра 2024-2025 учебного года"
        )
        self.assertEqual(
            replace_roman_with_arabic_numerals("Учебные занятия 4 курса ФЭВТ аспирантов на II-й семестр 2023-2024 учебного года"),
            "Учебные занятия 4 курса ФЭВТ аспирантов на 2-й семестр 2023-2024 учебного года"
        )

        self.assertEqual(
            replace_roman_with_arabic_numerals("X"),
            "10"
        )
        self.assertEqual(
            replace_roman_with_arabic_numerals("IX"),
            "9"
        )
        self.assertEqual(
            replace_roman_with_arabic_numerals("VIII II"),
            "8 2"
        )
        self.assertEqual(
            replace_roman_with_arabic_numerals("VII"),
            "7"
        )
        self.assertEqual(
            replace_roman_with_arabic_numerals("VI"),
            "6"
        )
        self.assertEqual(
            replace_roman_with_arabic_numerals("V"),
            "5"
        )
        self.assertEqual(
            replace_roman_with_arabic_numerals("I IV"),
            "1 4"
        )
        self.assertEqual(
            replace_roman_with_arabic_numerals("III II I I II III"),
            "3 2 1 1 2 3"
        )
