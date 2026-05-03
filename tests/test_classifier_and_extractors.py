from decimal import Decimal

from extraction.financial_extractor import FinancialExtractor
from extraction.transcript_parser import TranscriptParser
from ingestion.document_classifier import DocumentClassifier


def test_document_classifier_category_and_headline() -> None:
    classifier = DocumentClassifier()
    assert classifier.classify("Concall", "Transcript", "Transcript of Earnings Call") == "concall_transcript"
    assert classifier.classify("Unknown", "", "Appointment of Chief Financial Officer") == "management_change"


def test_transcript_parser_expected_shape() -> None:
    text = """V.V. Ravi Kumar: Thank you. On margins, we expect to see improvement in Q4.

Neha Manpuria (JPMorgan): My question is on the CDMO pipeline.

V.V. Ravi Kumar: Yes, we have added three new molecules this quarter."""
    turns = TranscriptParser().parse(text)
    assert turns[0].turn_index == 0
    assert turns[1].speaker_name == "Neha Manpuria"
    assert turns[1].speaker_org == "JPMorgan"
    assert turns[1].speaker_role == "analyst"


def test_laurus_anchor_financials() -> None:
    row = FinancialExtractor().extract_from_text("Laurus Labs 3QFY25")
    assert row is not None
    assert row["period"] == "3QFY25"
    assert row["revenue"] == Decimal("1547.00")
    assert row["ebitda"] == Decimal("278.00")
    assert row["ebitda_margin"] == Decimal("0.1797")
    assert row["pat"] == Decimal("152.00")
    assert row["eps_basic"] == Decimal("2.81")
