import re
from decimal import Decimal, InvalidOperation

from app.core.config import settings

LABEL_DICT = {
    "revenue": ["revenue from operations", "net revenue from operations", "total revenue from operations", "net sales", "revenue", "total income from operations", "net revenue", "sales", "gross revenue from operations", "income from operations", "revenue from contracts with customers"],
    "ebitda": ["ebitda", "earnings before interest tax depreciation amortisation", "operating ebitda", "ebitda before exceptional"],
    "da": ["depreciation and amortisation", "depreciation & amortisation", "depreciation", "depreciation amortisation", "d&a", "depreciation depletion and amortisation"],
    "ebit": ["ebit", "operating profit", "profit from operations", "earnings before interest and tax"],
    "finance_costs": ["finance costs", "interest expense", "finance charges", "interest and finance charges", "borrowing costs"],
    "pbt": ["profit before tax", "pbt", "profit before exceptional items and tax", "profit before exceptional and tax"],
    "tax": ["tax expense", "income tax expense", "provision for tax", "total tax expense", "current tax", "tax"],
    "pat": ["profit after tax", "pat", "profit for the period", "profit for the year", "net profit", "profit attributable to owners", "profit attributable to equity shareholders"],
    "eps_basic": ["basic eps", "earnings per share basic", "basic earnings per share", "eps (basic)", "basic eps (not annualised)"],
    "eps_diluted": ["diluted eps", "earnings per share diluted", "diluted earnings per share", "eps (diluted)", "diluted eps (not annualised)"],
    "shares_cr": ["weighted average shares", "weighted average number of equity shares", "shares outstanding", "number of equity shares"],
}


def normalize_label(value: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", value.lower()).strip()


def map_label(label: str) -> str | None:
    normalized = normalize_label(label)
    label_text = re.sub(r"\d+(?:\.\d+)?", " ", normalized)
    label_text = re.sub(r"\s+", " ", label_text).strip()
    best_field: str | None = None
    best_len = -1
    for field, aliases in LABEL_DICT.items():
        for alias in aliases:
            normalized_alias = normalize_label(alias)
            if normalized_alias and normalized_alias in label_text:
                if len(normalized_alias) > best_len:
                    best_field = field
                    best_len = len(normalized_alias)
    return best_field


def parse_number(value: str) -> Decimal | None:
    match = re.search(r"\(?-?[\d,]+(?:\.\d+)?\)?", value)
    if not match:
        return None
    raw = match.group(0).replace(",", "")
    negative = raw.startswith("(") and raw.endswith(")")
    raw = raw.strip("()")
    try:
        number = Decimal(raw)
        return -number if negative else number
    except InvalidOperation:
        return None


def extract_financial_row_from_text(text: str) -> dict:
    row: dict = {}
    for line in text.splitlines():
        field = map_label(line)
        if not field:
            continue
        number = parse_number(line)
        if number is not None and field not in row:
            row[field] = number
    row["quality_flags"] = validate_financials(row)
    row["extraction_method"] = "table"
    return row


def _pct_delta(actual: Decimal, expected: Decimal) -> Decimal:
    if expected == 0:
        return Decimal("0") if actual == 0 else Decimal("999")
    return abs(actual - expected) / abs(expected)


def validate_financials(row: dict) -> list[str]:
    flags: list[str] = []
    tol = Decimal(str(settings.financial_consistency_tolerance))
    if all(row.get(field) is not None for field in ["eps_basic", "shares_cr", "pat"]):
        computed_pat = row["eps_basic"] * row["shares_cr"]
        if _pct_delta(computed_pat, row["pat"]) > tol:
            flags.append(f"EPS_PAT_MISMATCH: computed={computed_pat:.2f} stored={row['pat']:.2f}")
    if all(row.get(field) is not None for field in ["ebitda", "da", "ebit"]):
        computed_ebit = row["ebitda"] - row["da"]
        if _pct_delta(computed_ebit, row["ebit"]) > tol:
            flags.append(f"EBITDA_DA_EBIT_MISMATCH: computed={computed_ebit:.2f} stored={row['ebit']:.2f}")
    if all(row.get(field) is not None for field in ["ebit", "finance_costs", "pbt"]):
        computed_pbt = row["ebit"] - row["finance_costs"]
        if _pct_delta(computed_pbt, row["pbt"]) > tol:
            flags.append("PBT_MISMATCH")
    if row.get("revenue") is not None and row["revenue"] <= 0:
        flags.append("NEGATIVE_REVENUE")
    if row.get("revenue") and row.get("ebitda") is not None:
        row["ebitda_margin"] = (row["ebitda"] / row["revenue"]).quantize(Decimal("0.0001"))
    return flags
