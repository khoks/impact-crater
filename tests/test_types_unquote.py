"""Stage 3 coercion: a 5.x tool input may wrap enum / string values in literal quotes
(seen once in 50 Haiku 5.5 shots during the S-2.10.9 A/B: time_of_day='"midday"')."""

from __future__ import annotations

from impact_crater.pipeline.types import RichMetadataPhoto


def test_quoted_scalars_are_unwrapped_before_validation() -> None:
    meta = RichMetadataPhoto(
        time_of_day='"midday"',
        shot_type='"wide"',
        safety_level='"safe"',
        mood='"calm and bright"',
        quality=0.7,
    )
    assert meta.time_of_day == "midday"
    assert meta.shot_type == "wide"
    assert meta.safety_level == "safe"
    assert meta.mood == "calm and bright"


def test_plain_values_and_lone_quote_are_untouched() -> None:
    meta = RichMetadataPhoto(mood='"', scenery_description="red rock")
    assert meta.mood == '"'
    assert meta.scenery_description == "red rock"


def test_leaked_xml_parameters_are_split_back_into_keys() -> None:
    """Real Haiku 5.5 payload shape from the S-2.10.9 Zion smoke job (10 of 75 shots)."""
    raw = {
        "quality": 0.8,
        "obstruction_level": (
            '0.25</obstruction_level>\n<parameter name="obstruction_notes">Vehicle roof edge '
            "across top and dashboard along bottom partially frame the view."
        ),
        "scenery_description": (
            "Tan and orange sandstone cliffs, a deep canyon curving ahead.</scenery_description>"
            '\n<parameter name="shot_type">wide'
        ),
    }
    meta = RichMetadataPhoto.model_validate(raw)
    assert meta.obstruction_level == 0.25
    assert meta.obstruction_notes.startswith("Vehicle roof edge across top")
    assert (
        meta.scenery_description == "Tan and orange sandstone cliffs, a deep canyon curving ahead."
    )
    assert meta.shot_type == "wide"


def test_recovered_parameter_never_overrides_a_real_key() -> None:
    raw = {
        "mood": 'calm</mood>\n<parameter name="shot_type">close_up</parameter>',
        "shot_type": "wide",
    }
    meta = RichMetadataPhoto.model_validate(raw)
    assert meta.mood == "calm"
    assert meta.shot_type == "wide"


def test_people_leak_without_its_own_closing_tag_is_left_to_its_validator() -> None:
    meta = RichMetadataPhoto.model_validate({"people": '\n<parameter name="count">3'})
    assert meta.people.count == 3
