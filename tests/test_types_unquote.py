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
