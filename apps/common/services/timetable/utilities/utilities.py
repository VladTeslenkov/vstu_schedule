import re

from apps.common.models import (
    Event,
    ScheduleTemplateMetadata,
)
from apps.common.services.timetable.utilities.normalizers import (
    normalize_scope,
)


def replace_roman_with_arabic_numerals(string_ : str) -> str:
    """Replaces roman numerals in given string with arabic numerals

    Works only with numbers <= 10
    """

    NUMERALS = [
        ("IX", "9"),
        ("X", "10"),
        ("VIII", "8"),
        ("VII", "7"),
        ("VI", "6"),
        ("IV", "4"),
        ("V", "5"),
        ("III", "3"),
        ("II", "2"),
        ("I", "1")
    ]

    corrected_string = string_
    
    for roman, arabic in NUMERALS:
        corrected_string = corrected_string.replace(roman, arabic)

    return corrected_string

def get_number_from_month_name(name : str) -> int:
    """Returns month number from month name
    """
    
    MONTHS = { 
        "январь" : 1, 
        "февраль" : 2, 
        "март" : 3, 
        "апрель" : 4, 
        "май" : 5, 
        "июнь" : 6, 
        "июль" : 7, 
        "август" : 8, 
        "сентябрь" : 9, 
        "октябрь" : 10, 
        "ноябрь": 11, 
        "декабрь" : 12
    }
    
    return MONTHS[name.lower()]

def get_name_from_month_number(month_number : int|list[int]) -> str|None|list[str|None]:
    """Returns month name from month number

    Returns None for not-existing month number
    """
    
    MONTH_NAMES = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
    
    if type(month_number) is list:
        names = []

        for i in month_number:
            names.append(
                MONTH_NAMES[i - 1] 
                if i >= 1 and i <= 12 
                else None
            )

        return names

    return MONTH_NAMES[month_number - 1] if month_number >= 1 and month_number <= 12 else None 

def get_scope_from_label(scope_label : str) -> ScheduleTemplateMetadata.Scope|None:
        SCOPES_REG_EXS = [
            (ScheduleTemplateMetadata.Scope.BACHELOR, r"(([бБ]акалавр)[а-яА-ЯёЁ]*)"),
            (ScheduleTemplateMetadata.Scope.MASTER, r"(([мМ]агистр)[а-яА-ЯёЁ]*)"),
            (ScheduleTemplateMetadata.Scope.POSTGRADUATE, r"(([аА]спирант)[а-яА-ЯёЁ]*)"),
            (ScheduleTemplateMetadata.Scope.CONSULTATION, r"(([кК]онсульт)[а-яА-ЯёЁ]*)")
        ]
        
        for scope, reg_ex in SCOPES_REG_EXS:
            if re.search(reg_ex, normalize_scope(scope_label)):
                return scope
            
        return None

def is_events_follow_each_other(first_event : Event, second_event : Event) -> bool:
    """Checks is Events follow one after other by time slot
    """
    
    # Consider Events to be consecutive
    # when their time slot follow one after other

    # Takes FIRST digit from SECOND_EVENT time slot alt name ('3-4' -> 3)
    # and LAST digit from FIRST_EVENT time slot alt name ('1-2' -> 2)
    # then subtracts second one from first one (3 - 2)
    return (
        int(re.findall(r"\d+", second_event.time_slot_override.alt_name)[0]) - 
        int(re.findall(r"\d+", first_event.time_slot_override.alt_name)[-1])
    ) == 1
            

def is_similar_events(first_event : Event, second_event : Event) -> bool:
    """Checks is Events are similar based on model fields
    """

    return (
        first_event.subject_override == second_event.subject_override and
        list(first_event.get_groups()) == list(second_event.get_groups()) and
        list(first_event.get_teachers()) == list(second_event.get_teachers()) and
        list(first_event.places_override.all()) == list(second_event.places_override.all())
    )
