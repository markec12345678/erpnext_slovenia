"""
MT940 (SWIFT) bank statement parser for Slovenian banks.

MT940 is the international SWIFT format for electronic bank statements.
Slovenian banks (NLB, NKBM, SKB, Abanka, UniCredit, Sparkasse) all use MT940
for end-of-day statement delivery to corporate customers.

This module provides:
- parse_mt940(content): Parse raw MT940 text into structured transactions
- import_to_bank_transaction(parsed, company, bank_account): Create Bank Transaction records
- demo_mt940(): Generate a sample MT940 statement for testing

Format reference:
  :20: - Transaction reference number
  :25: - Account identification (IBAN)
  :28C: - Statement number / sequence number
  :60F: - Opening balance (C/D, YYMMDD, currency, amount)
  :61: - Statement line (date, amount, transaction type, reference)
  :86: - Information to account owner (structured SI reference)
  :62F: - Closing balance
  :64: - Available balance
"""
import re
import datetime
import frappe
from frappe import _


# MT940 field regex patterns
FIELD_20 = re.compile(r":20:([^\r\n]*)")           # Transaction reference
FIELD_25 = re.compile(r":25:([^\r\n]*)")            # Account ID (IBAN)
FIELD_28C = re.compile(r":28C:([^\r\n]*)")          # Statement number
FIELD_60F = re.compile(r":60F:(C|D)(\d{6})([A-Z]{3})([\d,\.]+)")  # Opening balance
FIELD_61 = re.compile(
    r":61:(\d{6})(\d{4})?(C|D|RC|RD)([A-Z]{1})([A-Z0-9]+)?//?([^\r\n]*)"
)
FIELD_86 = re.compile(r":86:([^\r\n]*(?:\r?\n(?![ ]*:\d{2}[A-Z]?)[^\r\n]*)*)")
FIELD_62F = re.compile(r":62F:(C|D)(\d{6})([A-Z]{3})([\d,\.]+)")  # Closing balance
FIELD_64 = re.compile(r":64:(C|D)(\d{6})([A-Z]{3})([\d,\.]+)")    # Available balance


def parse_mt940(content: str) -> dict:
    """Parse MT940 text into a structured dict.

    Args:
        content: Raw MT940 text (string)

    Returns:
        Dict with:
          - transaction_reference (str)
          - account_iban (str)
          - statement_number (str)
          - opening_balance (dict with date, currency, amount, debit/credit)
          - closing_balance (dict)
          - available_balance (dict)
          - transactions (list of dicts: date, amount, debit_or_credit, reference, description)
    """
    # Normalize line endings
    content = content.replace("\r\n", "\n").replace("\r", "\n")

    result = {
        "transaction_reference": "",
        "account_iban": "",
        "statement_number": "",
        "opening_balance": None,
        "closing_balance": None,
        "available_balance": None,
        "transactions": [],
    }

    # Extract simple fields
    m = FIELD_20.search(content)
    if m:
        result["transaction_reference"] = m.group(1).strip()

    m = FIELD_25.search(content)
    if m:
        result["account_iban"] = m.group(1).strip()

    m = FIELD_28C.search(content)
    if m:
        result["statement_number"] = m.group(1).strip()

    m = FIELD_60F.search(content)
    if m:
        result["opening_balance"] = _parse_balance(m)

    m = FIELD_62F.search(content)
    if m:
        result["closing_balance"] = _parse_balance(m)

    m = FIELD_64.search(content)
    if m:
        result["available_balance"] = _parse_balance(m)

    # Parse transactions (:61: ... :86: ...)
    # Find all :61: blocks, each followed by optional :86: block
    transaction_blocks = re.findall(
        r":61:([^\r\n]*)(?:\r?\n)?(?::86:([^\r\n]*(?:\r?\n(?![ ]*:\d{2}[A-Z]?)[^\r\n]*)*))?",
        content
    )

    for line_text, info_text in transaction_blocks:
        tx = _parse_transaction_line(line_text, info_text)
        if tx:
            result["transactions"].append(tx)

    return result


def _parse_balance(match) -> dict:
    """Parse a balance field match into a dict."""
    debit_credit = match.group(1)  # C or D
    date_str = match.group(2)  # YYMMDD
    currency = match.group(3)
    amount_str = match.group(4).replace(",", ".")

    try:
        year = int(date_str[:2])
        # Handle Y2K: 00-50 → 2000-2050, 51-99 → 1951-1999
        year = 2000 + year if year < 50 else 1900 + year
        month = int(date_str[2:4])
        day = int(date_str[4:6])
        date = datetime.date(year, month, day)
    except (ValueError, IndexError):
        date = None

    return {
        "debit_credit": debit_credit,
        "date": date.strftime("%Y-%m-%d") if date else "",
        "currency": currency,
        "amount": float(amount_str),
    }


def _parse_transaction_line(line_text: str, info_text: str) -> dict:
    """Parse a single :61: line (and optional :86: block)."""
    # Format: YYMMDD(DDMM)?C|D...amount
    # Example: 2406150615C5000,00NTRFNONREF//SI0024000001
    line_text = line_text.strip()
    info_text = info_text.strip() if info_text else ""

    # Date (first 6 chars)
    date_str = line_text[:6]
    try:
        year = 2000 + int(date_str[:2])
        month = int(date_str[2:4])
        day = int(date_str[4:6])
        tx_date = datetime.date(year, month, day)
    except (ValueError, IndexError):
        return None

    # Find D or C (after the value date and optional entry date)
    # Match pattern: \d{6}(\d{4})?(C|D|RC|RD)
    dc_match = re.match(r"\d{6}(?:\d{4})?(RC|RD|C|D)", line_text)
    if not dc_match:
        return None
    dc = dc_match.group(1)
    is_debit = "D" in dc

    # Find amount after the D/C indicator and funds code
    rest = line_text[dc_match.end():]
    # Skip single-letter funds code (e.g., "R" in "R5000,00")
    rest = re.sub(r"^[A-Z]", "", rest, count=1) if rest and rest[0].isalpha() and not rest[0].isdigit() else rest

    # Match amount: digits with optional thousand separators (.) and decimal (,)
    amount_match = re.match(r"([\d\.]+,\d{2})", rest)
    if not amount_match:
        # Try without comma (integer amount)
        amount_match = re.match(r"(\d+)", rest)
        if not amount_match:
            return None

    amount_str = amount_match.group(1).replace(".", "").replace(",", ".")
    try:
        amount = float(amount_str)
    except ValueError:
        return None

    # If debit, amount is negative
    if is_debit:
        amount = -amount

    # Extract reference (after //)
    ref_match = re.search(r"//([^\s\r\n]+)", line_text)
    reference = ref_match.group(1) if ref_match else ""

    # The :86: info text typically contains structured SI reference and description
    # Format example: "021?00DODPL?20SI002024000012345?30Kovinar d.o.o.?31SI...?32..."
    # We extract payment purpose (021?00...), SI ref (?20...), party name (?30...)
    description = ""
    si_ref = ""
    party_name = ""
    party_iban = ""
    payment_code = ""

    if info_text:
        # Strip the leading "021?00" if present
        info_clean = re.sub(r"^\d+\?", "", info_text)
        # Split by ?NN markers
        parts = re.split(r"\?(\d{2})", info_clean)
        # parts will be: [text, "00", "purpose", "20", "ref", "30", "name", ...]
        for i in range(1, len(parts) - 1, 2):
            code = parts[i]
            value = parts[i + 1].strip() if i + 1 < len(parts) else ""
            if code == "00":
                if not description:
                    description = value
            elif code == "20":
                si_ref = value
            elif code == "21":
                payment_code = value
            elif code == "30":
                party_name = value
            elif code == "31":
                party_iban = value
            elif code == "32":
                if not party_name:
                    party_name = value
            elif code == "22":
                description = value

    if not description:
        # Use the reference from line as description fallback
        description = info_text[:200] if info_text else reference

    return {
        "date": tx_date.strftime("%Y-%m-%d"),
        "amount": amount,
        "debit_credit": "D" if is_debit else "C",
        "reference": reference,
        "si_reference": si_ref,
        "description": description[:300],
        "party_name": party_name,
        "party_iban": party_iban,
        "payment_code": payment_code,
    }


@frappe.whitelist()
def import_mt940(content: str = None, file_url: str = None,
                 company: str = None, bank_account: str = None) -> dict:
    """RPC: Import MT940 bank statement into Bank Transaction records.

    Args:
        content: Raw MT940 text (mutually exclusive with file_url)
        file_url: Path to uploaded MT940 file
        company: Target Company
        bank_account: Target Bank Account

    Returns:
        Dict with import result (count, errors, total_amount)
    """
    if not content and not file_url:
        return {"success": False, "error": _("Manjka MT940 vsebina ali datoteka.")}

    if file_url and not content:
        # Read file from /private/files/ or /files/
        try:
            file_path = frappe.get_site_path("public", file_url.lstrip("/"))
            if not frappe.os.path.exists(file_path):
                file_path = frappe.get_site_path("private", file_url.lstrip("/private/"))
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception as e:
            return {"success": False, "error": f"Cannot read file: {e}"}

    # Parse MT940
    parsed = parse_mt940(content)

    if not parsed["transactions"]:
        return {"success": False, "error": _("Ni transakcij v MT940 datoteki.")}

    # If bank_account not provided, try to determine from IBAN
    if not bank_account and parsed["account_iban"]:
        iban_clean = parsed["account_iban"].replace(" ", "").upper()
        bank_account = frappe.db.get_value("Bank Account",
            {"iban": ["like", f"%{iban_clean[:8]}%"]}, "name")

    if not company:
        if bank_account:
            company = frappe.db.get_value("Bank Account", bank_account, "company")

    if not (company and bank_account):
        return {
            "success": False,
            "error": _("Manjka podjetje ali bančni račun."),
        }

    # Create Bank Transaction records
    created = 0
    skipped = 0
    errors = []

    for tx in parsed["transactions"]:
        try:
            # Check for duplicate (same date + amount + reference)
            amount_field = "deposit" if tx["amount"] > 0 else "withdrawal"
            existing = frappe.db.get_value("Bank Transaction",
                {
                    "company": company,
                    "bank_account": bank_account,
                    "date": tx["date"],
                    amount_field: abs(tx["amount"]),
                },
                "name")

            if existing:
                skipped += 1
                continue

            bt = frappe.get_doc({
                "doctype": "Bank Transaction",
                "company": company,
                "bank_account": bank_account,
                "date": tx["date"],
                "deposit": abs(tx["amount"]) if tx["amount"] > 0 else 0,
                "withdrawal": abs(tx["amount"]) if tx["amount"] < 0 else 0,
                "currency": parsed["opening_balance"]["currency"] if parsed["opening_balance"] else "EUR",
                "description": tx["description"],
                "reference_number": tx["si_reference"] or tx["reference"],
                "transaction_id": tx["reference"],
            })
            bt.flags.ignore_permissions = True
            bt.insert()
            created += 1
        except Exception as e:
            errors.append({"transaction": tx, "error": str(e)})
            frappe.db.rollback()

    frappe.db.commit()

    total_amount = sum(t["amount"] for t in parsed["transactions"])

    return {
        "success": True,
        "created": created,
        "skipped": skipped,
        "errors": errors[:10],
        "total_amount": total_amount,
        "opening_balance": parsed["opening_balance"],
        "closing_balance": parsed["closing_balance"],
        "statement_reference": parsed["transaction_reference"],
        "account_iban": parsed["account_iban"],
    }


def demo_mt940() -> str:
    """Generate a sample MT940 statement for testing."""
    return """:20:NLB20240615001
:25:SI40290000001234567
:28C:1/1
:60F:C240614EUR10000,00
:61:2406150615C5000,00NTRFNONREF//SI002024000012345
:86:021?00DODPL?20SI002024000012345?21OTHR?30Kovinar d.o.o.?31SI56191000001234567?32Plačilo računa RAC-001
:61:2406150615D1500,00NTRFNONREF//SI002024000012346
:86:021?00NAKUP?20SI002024000012346?21GDSV?30Tehnika d.o.o.?31SI5612345678?32Nakup materiala
:61:2406160616C3500,00NTRFNONREF//SI002024000012347
:86:021?00PROD?20SI002024000012347?21OTHR?30Trgovina d.o.o.?31SI5698765432?32Plačilo za blago
:62F:C240616EUR17000,00
:64:C240616EUR17000,00
"""


@frappe.whitelist()
def import_demo_mt940() -> dict:
    """RPC: import the demo MT940 statement for testing."""
    return import_mt940(content=demo_mt940(),
                       company="Moje Podjetje d.o.o.",
                       bank_account=frappe.db.get_value("Bank Account",
                           {"company": "Moje Podjetje d.o.o."}, "name"))
