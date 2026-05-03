from decimal import Decimal

from app.pipeline.classifier import classify_filing
from app.pipeline.financial_extractor import extract_financial_row_from_text, validate_financials
from app.pipeline.transcript_parser import parse_transcript


def test_category_map_classifies_transcript():
    assert classify_filing("Concall", "Transcript", "Transcript of Earnings Call") == "concall_transcript"


def test_parse_transcript_sample_contract():
    text = """
V.V. Ravi Kumar: Thank you. On margins, we expect to see improvement in Q4.

Neha Manpuria (JPMorgan): My question is on the CDMO pipeline.
"""
    turns = parse_transcript(text)
    assert turns[0]["speaker_raw"] == "V.V. Ravi Kumar"
    assert turns[1]["speaker_name"] == "Neha Manpuria"
    assert turns[1]["speaker_org"] == "JPMorgan"
    assert turns[1]["speaker_role"] == "analyst"
    assert turns[1]["word_count"] == 7


def test_laurus_fixture_margin_contract():
    row = {"revenue": Decimal("1547.00"), "ebitda": Decimal("278.00"), "pat": Decimal("152.00"), "eps_basic": Decimal("2.81")}
    assert validate_financials(row) == []
    assert row["ebitda_margin"] == Decimal("0.1797")


def test_extract_financial_row_from_text_maps_labels():
    row = extract_financial_row_from_text("Revenue from Operations 1,547\nEBITDA 278\nProfit After Tax 152\nBasic EPS 2.81")
    assert row["revenue"] == Decimal("1547")
    assert row["ebitda"] == Decimal("278")
    assert row["pat"] == Decimal("152")
    assert row["eps_basic"] == Decimal("2.81")
