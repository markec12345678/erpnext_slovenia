"""
Slovenian tax number (davčna številka) validation.

Slovenian davčna številka (tax ID) is 8 digits with a checksum.
Format: DDXXXXXX where first two digits identify the tax office.
The checksum uses MOD 11 algorithm.
"""
import re
import frappe


SI_TAX_ID_REGEX = re.compile(r"^SI?\d{8}$")


def compute_checksum(digits: str) -> int:
    """Slovenian MOD 11 checksum algorithm for davčna številka."""
    if len(digits) != 7:
        return -1
    weights = [2, 3, 4, 5, 6, 7, 8]
    s = sum(int(d) * w for d, w in zip(digits, weights))
    mod = s % 11
    if mod == 0:
        # 11-0=11, but checksum digit is 0 in this case
        return 0
    if mod == 1:
        return -1  # invalid
    return 11 - mod


def is_valid_si_tax_id(value: str) -> bool:
    """Validate Slovenian davčna številka (with optional 'SI' prefix)."""
    if not value:
        return False
    cleaned = value.strip().upper()
    if cleaned.startswith("SI"):
        cleaned = cleaned[2:]
    if not cleaned.isdigit() or len(cleaned) != 8:
        return False
    expected = compute_checksum(cleaned[:7])
    return expected != -1 and expected == int(cleaned[7])


def validate_tax_id(doc, method=None):
    """Hook for Customer/Supplier.validate — validate custom tax_id field."""
    tax_id = doc.get("tax_id") or doc.get("custom_tax_id")
    if not tax_id:
        return

    country = None
    if hasattr(doc, "country"):
        country = doc.country
    elif doc.get("customer_primary_address") and doc.customer_primary_address:
        # try to fetch from address
        country = frappe.db.get_value("Address", doc.customer_primary_address, "country")

    # Only validate SI format if country is Slovenia or prefix is SI
    if (country and country.lower() == "slovenia") or tax_id.upper().startswith("SI"):
        if not is_valid_si_tax_id(tax_id):
            frappe.msgprint(
                f"Davčna številka '{tax_id}' ni veljavna slovenska davčna številka. "
                f"Preverite obliko (8 številk z ustreznim kontrolnim znakom, opcijski 'SI' predponi).",
                title="Opozorilo",
                indicator="orange",
            )
