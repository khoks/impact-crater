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
