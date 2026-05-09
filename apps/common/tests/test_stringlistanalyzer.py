import pytest

from apps.common.services.timetable_update.version_core.stringlistanalyzer import (
    StringListAnalyzer,
)


def test_string_list_analyzer_keeps_best_first_match() -> None:
    analyzer = StringListAnalyzer(
        analyze_strings=["очная", "магистратура"],
        compare_strings=["заочная", "очная", "бакалавриат"],
    )

    assert analyzer.get_similar_string("очная") == "очная"
    assert analyzer.get_ratio_for_string("очная") == 1
    assert analyzer.get_strings_by_ratio_in_range(0.8, 1) == ["очная"]


def test_string_list_analyzer_rounds_string_ratios() -> None:
    analyzer = StringListAnalyzer(
        analyze_strings=["abc", "xyz"],
        compare_strings=["abd", "xxx"],
    )

    assert analyzer.get_strings_by_ratio(0.67, round_number=2) == ["abc"]


def test_string_list_analyzer_rejects_negative_rounding() -> None:
    analyzer = StringListAnalyzer(["abc"], ["abd"])

    with pytest.raises(ValueError):
        analyzer.get_strings_by_ratio(0.5, round_number=-1)
