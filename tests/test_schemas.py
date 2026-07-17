"""LLM extraction resilience: placeholder strings must not crash validation."""

from datetime import date

from backend.schemas import PolicyData, Recommendation


def test_unknown_placeholders_become_none():
    # This mirrors what a real model emitted: '<UNKNOWN>' in typed fields instead of null.
    policy = PolicyData.model_validate(
        {
            "insurer": "Allianz",
            "vehicle": "<UNKNOWN>",
            "coverage_type": "<UNKNOWN>",  # non-nullable enum -> falls back to default
            "annual_premium": "<UNKNOWN>",
            "anniversary_date": "<UNKNOWN>",
            "notice_period_days": "<UNKNOWN>",
            "glass_cover": "<UNKNOWN>",
            "animal_cover": "N/A",
        }
    )
    assert policy.insurer == "Allianz"
    assert policy.vehicle is None
    assert policy.coverage_type == "PZP"  # sentinel fell back to the default
    assert policy.annual_premium is None
    assert policy.anniversary_date is None
    assert policy.notice_period_days is None
    assert policy.glass_cover is None
    assert policy.animal_cover is None


def test_real_values_still_parse():
    policy = PolicyData.model_validate(
        {
            "coverage_type": "kasko",
            "annual_premium": "210",  # string number still coerces
            "anniversary_date": "2025-09-01",
            "notice_period_days": 42,
        }
    )
    assert policy.coverage_type == "kasko"
    assert policy.annual_premium == 210.0
    assert policy.anniversary_date == date(2025, 9, 1)
    assert policy.notice_period_days == 42


def test_recommendation_placeholder_verdict_falls_back():
    rec = Recommendation.model_validate({"verdict": "unknown", "rationale": "<UNKNOWN>"})
    assert rec.verdict == "stay"
    assert rec.rationale == ""
