"""Tests for the stringified-list coercion in RichMetadataPhoto.

The Anthropic tool_use path occasionally emits a CSV-quoted string
instead of a JSON array for `list[str]` fields. Real failure caught
during the Times Square 50-photo smoke test:

    generic_tags: 'times square", "new york", "tourist destination"]'

The before-validator parses it back to a list. Belt-and-suspenders
since the tool_use input_schema is a hint to the model, not a hard
validator.
"""

from __future__ import annotations

import pytest

from impact_crater.pipeline.types import RichMetadataPhoto


def test_string_with_trailing_bracket_parses_to_list() -> None:
    """The exact failure pattern from the Times Square run."""
    raw = {
        "time_of_day": "midday",
        "generic_tags": 'times square", "new york", "tourist destination"]',
    }
    p = RichMetadataPhoto.model_validate(raw)
    assert p.generic_tags == ["times square", "new york", "tourist destination"]


def test_string_with_full_brackets_parses_as_json_array() -> None:
    raw = {"generic_tags": '["alps", "summit", "hike"]'}
    p = RichMetadataPhoto.model_validate(raw)
    assert p.generic_tags == ["alps", "summit", "hike"]


def test_already_a_list_passes_through() -> None:
    raw = {"generic_tags": ["a", "b", "c"]}
    p = RichMetadataPhoto.model_validate(raw)
    assert p.generic_tags == ["a", "b", "c"]


def test_empty_string_becomes_empty_list() -> None:
    raw = {"generic_tags": ""}
    p = RichMetadataPhoto.model_validate(raw)
    assert p.generic_tags == []


def test_csv_fallback_for_random_string() -> None:
    """Last-ditch CSV split when neither JSON parse works."""
    raw = {"generic_tags": 'foo", "bar", "baz'}
    p = RichMetadataPhoto.model_validate(raw)
    # All variants of "[" + s + "]" / "[" + s / s + "]" should produce a list.
    assert "foo" in p.generic_tags
    assert "bar" in p.generic_tags
    assert "baz" in p.generic_tags


def test_coercion_applied_to_objects_clothing_task_tags() -> None:
    raw = {
        "objects": 'phone", "backpack"]',
        "clothing": 'jacket", "hat"]',
        "task_context_tags": 'urban", "tourist"]',
    }
    p = RichMetadataPhoto.model_validate(raw)
    assert p.objects == ["phone", "backpack"]
    assert p.clothing == ["jacket", "hat"]
    assert p.task_context_tags == ["urban", "tourist"]


def test_coercion_applied_to_people_in_focus() -> None:
    raw = {"people": {"count": 2, "in_focus": 'adult woman center", "child left"]'}}
    p = RichMetadataPhoto.model_validate(raw)
    assert p.people.in_focus == ["adult woman center", "child left"]


def test_non_string_non_list_value_unchanged() -> None:
    """Pydantic still rejects truly bad inputs (e.g. a number where a list
    is required)."""
    raw = {"generic_tags": 42}
    with pytest.raises(Exception):
        RichMetadataPhoto.model_validate(raw)


# ---- Nested-model coercion (real failure 2026-05-07) -------------------
#
# Sonnet sometimes leaks its tool-use parameter wrapper into the value as
# a raw string, e.g.
#     people   = '\n<parameter name="count">3'
#     location = '\n<parameter name="description">Foothills in Zion National Park'
# instead of the structured PeopleObservation / LocationObservation dicts.
# The before-validators recover what they can and don't kill the job.


def test_people_xml_leak_extracts_count() -> None:
    raw = {"people": '\n<parameter name="count">3'}
    p = RichMetadataPhoto.model_validate(raw)
    assert p.people.count == 3
    assert p.people.in_focus == []


def test_people_xml_leak_with_quoted_count() -> None:
    raw = {"people": '<parameter name="count">"7"</parameter>'}
    p = RichMetadataPhoto.model_validate(raw)
    assert p.people.count == 7


def test_people_already_a_dict_passes_through() -> None:
    raw = {"people": {"count": 4, "in_focus": ["father", "child"]}}
    p = RichMetadataPhoto.model_validate(raw)
    assert p.people.count == 4
    assert p.people.in_focus == ["father", "child"]


def test_people_json_string_parses() -> None:
    raw = {"people": '{"count": 5, "in_focus": ["a", "b"]}'}
    p = RichMetadataPhoto.model_validate(raw)
    assert p.people.count == 5
    assert p.people.in_focus == ["a", "b"]


def test_people_unrecoverable_string_defaults_empty() -> None:
    raw = {"people": "totally garbage string with no markers"}
    p = RichMetadataPhoto.model_validate(raw)
    assert p.people.count == 0
    assert p.people.in_focus == []


def test_location_xml_leak_extracts_description() -> None:
    raw = {"location": '\n<parameter name="description">Foothills in Zion National Park'}
    p = RichMetadataPhoto.model_validate(raw)
    assert p.location.description == "Foothills in Zion National Park"
    assert p.location.lat_long is None


def test_location_already_a_dict_passes_through() -> None:
    raw = {"location": {"description": "Times Square", "lat_long": (40.758, -73.985)}}
    p = RichMetadataPhoto.model_validate(raw)
    assert p.location.description == "Times Square"
    assert p.location.lat_long == (40.758, -73.985)


def test_location_json_string_parses() -> None:
    raw = {"location": '{"description": "Eiffel Tower", "lat_long": null}'}
    p = RichMetadataPhoto.model_validate(raw)
    assert p.location.description == "Eiffel Tower"
    assert p.location.lat_long is None


def test_full_xml_leak_combo_from_real_job() -> None:
    """The exact failure pattern from user job 2a245c1b on 2026-05-07."""
    raw = {
        "time_of_day": "midday",
        "people": '\n<parameter name="count">3',
        "location": '\n<parameter name="description">Foothills in Zion National Park',
        "mood": "adventurous",
        "objects": ["backpack", "hiking poles"],
    }
    p = RichMetadataPhoto.model_validate(raw)
    assert p.people.count == 3
    assert p.location.description == "Foothills in Zion National Park"
    assert p.mood == "adventurous"
    assert p.objects == ["backpack", "hiking poles"]
