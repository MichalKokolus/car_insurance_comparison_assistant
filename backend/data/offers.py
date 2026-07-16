"""Canned Slovak-market PZP offers used by the PoC.

This is the mock behind the `web_search` tool. Swap this list (or the tool) for a real
search integration to make the research step live.
"""

from __future__ import annotations

from backend.schemas import Offer

CANNED_OFFERS: list[Offer] = [
    Offer(
        insurer="Union poisťovňa",
        product="PZP Klasik",
        coverage_type="PZP",
        annual_premium=168.0,
        deductible="—",
        glass_cover=True,
        animal_cover=True,
        liability_limit="7 mil. € / 1,3 mil. €",
        source="union.sk",
    ),
    Offer(
        insurer="KOOPERATIVA",
        product="PZP Standard",
        coverage_type="PZP",
        annual_premium=185.0,
        deductible="—",
        glass_cover=False,
        animal_cover=True,
        liability_limit="6 mil. € / 1,2 mil. €",
        source="koop.sk",
    ),
    Offer(
        insurer="Generali",
        product="PZP Plus",
        coverage_type="PZP",
        annual_premium=199.0,
        deductible="—",
        glass_cover=True,
        animal_cover=False,
        liability_limit="5,24 mil. € / 1,05 mil. €",
        source="generali.sk",
    ),
]
