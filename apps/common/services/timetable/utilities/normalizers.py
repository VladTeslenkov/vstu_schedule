import re


def normalize_place_building_and_room(building_and_room : str) -> tuple[str, str]|None:
    """Take Place building and room and convert it into acceptable format

    Place must be in format: {building}{room} separated by
    ' ' or ',' or '-'         
    
    Returns None if no room given

    If no building given, first string will be empty: ("", {room})
    """
    
    if building_and_room is None:
        return None

    place = building_and_room.strip()

    if not place:
        return None
    
    # SPACE should be always the last one
    for separator in [",", "-", " "]:
        if separator in place:
            building_part, room_part = place.split(separator, 1)
            building = building_part.strip()
            room = room_part.strip()

            if room:
                return building, room
            
            return None

    return "", place

def normalize_time_slot_display_name(display_name : str) -> tuple[str, str, str]|None:
    """Take time slot display name and convert it into acceptable format

    Display name must be present
        as alt name: \\d-\\d
        as start time: HH:MM or HH.MM
        as start and end times: START_TIME-END_TIME or START_TIME END_TIME

    Returns time slot display name structured as (ALT_NAME, START_TIME, END_TIME) 
    and formated as (\\d-\\d HH:MM HH:MM). Empty values equals ''
    """

    # 1-2
    # 3 -  4
    # exclude 8:30-10.00
    ALT_NAME_REG_EX = r"^\d{1,2}\s*\-+\s*\d{1,2}$"

    if display_name is None:
        return None
    
    time_slot = display_name.strip()

    if not time_slot:
        return None
    
    # check for alt_name format
    match_ = re.search(ALT_NAME_REG_EX, time_slot)

    if match_:
        return match_[0], "", ""
    
    time_slot = time_slot.replace(".", ":")

    for separator in ["-", " "]:
        if separator in time_slot:
            start_time, end_time = time_slot.split(separator, 1)

            return "", start_time.strip(), end_time.strip()
    
    return "", time_slot, ""

def normalize_subject_name(name : str) -> str:
    return name.strip()

def normalize_kind_name(kind : str) -> str:
    return kind.strip().capitalize()

def normalize_participant_name(name : str) -> str:
    return name.strip()

def format_participant_name(surname : str, name : str, patronymic : str) -> str:
    """Makes EventParticipant name from given parameters in format:
    SURNAME N.P. (where N - first char of name and P - first char of patronymic)

    When name and/or patronymic empty skip it in resulting name (without dot)
    """
    return "{surname} {name}{patronymic}".format(
        surname=surname,
        name=f"{name[0]}." if name else "",
        patronymic=f"{patronymic[0]}." if patronymic else ""
    )

def normalize_scope(scope : str):
    return scope.strip().capitalize()
