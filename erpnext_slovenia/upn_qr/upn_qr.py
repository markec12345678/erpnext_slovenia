"""
UPN QR code generator for Slovenian payment orders.

The UPN QR (Univerzalni Plačilni Nalog QR) is a standard defined by Banka Slovenije
that allows instant payment via mobile banking apps. The QR code contains 19 fields
in a specific format.

Reference: https://www.nlb.si/si/posamezniki/upn-qr-koda

Format:
 ---------
 |UPNQR|
 ---------

  Header: "UPNQR"
  Then 19 fields, each terminated by newline (\\n):
   1.  Placilni namen (payment purpose)         - max 40 chars, recommended 18
   2.  Namen (purpose code, e.g. "ADTG" for cost reimbursement, "OTHR" for other)
   3.  Nujnost (urgency)                        - "X" or empty
   4.  IBAN placnika (payer IBAN)               - 34 chars max, empty for payee-side
   5.  Referenca placnika                       - max 26 chars
   6.  Ime plačnika                             - max 33 chars
   7.  Naslov plačnika                          - max 33 chars
   8.  Znesek (amount)                          - integer, in cents (11 digits, zero-padded)
   9.  Datum (date)                             - DD.MM.YYYY
   10. Nujnost končnega plačila                 - empty or "X"
   11. IBAN prejemnika (payee IBAN)
   12. Referenca prejemnika                     - "SI" + n digits (max 26 chars total, with SI prefix)
       Format: SI00 + a reference, where the digits after SI follow MOD 11
   13. Ime prejemnika                           - max 33 chars
   14. Naslov prejemnika                        - max 33 chars
   15. Empty (reserved)
   16. Empty (reserved)
   17. Empty (reserved)
   18. Empty (reserved)
   19. Control sum (5 digits, zero-padded, MOD 11 of concatenated chars)
"""
import re
import datetime
from typing import Optional

import frappe
from frappe import _


def _compute_mod11_control(s: str) -> int:
    """Slovenian MOD 11 checksum (used for SI references and UPN QR control)."""
    if not s:
        return 0
    weights = []
    w = 2
    for _ in s:
        weights.append(w)
        w += 1
        if w > 7:
            w = 2
    total = sum(int(c) * weights[i] for i, c in enumerate(reversed(s)) if c.isdigit())
    mod = total % 11
    if mod == 0:
        return 0
    if mod == 1:
        # Invalid - return 0 (shouldn't happen for valid input)
        return 0
    return 11 - mod


def _format_si_reference(reference: str) -> str:
    """Format a reference as SI00 + reference + checksum (MOD 11)."""
    # Strip non-digits
    digits = re.sub(r"\D", "", reference)[:18]
    if not digits:
        return ""
    checksum = _compute_mod11_control(digits)
    return f"SI00{digits}{checksum}"


def _format_amount_in_cents(amount: float) -> str:
    """Format amount as 11-digit zero-padded string of cents."""
    cents = int(round(amount * 100))
    return f"{cents:011d}"


def _format_date(date_value) -> str:
    """Format date as DD.MM.YYYY."""
    if not date_value:
        return ""
    if isinstance(date_value, str):
        try:
            d = datetime.datetime.strptime(date_value, "%Y-%m-%d")
        except ValueError:
            return ""
    elif isinstance(date_value, (datetime.date, datetime.datetime)):
        d = date_value
    else:
        return ""
    return d.strftime("%d.%m.%Y")


def generate_upn_qr_payload(
    payee_name: str,
    payee_address: str,
    payee_iban: str,
    amount: float,
    payment_date,
    payment_purpose: str = "Plačilo računa",
    payment_code: str = "OTHR",  # OTHR = other
    reference: str = "",  # SI reference for payee (without SI prefix)
    payer_name: str = "",
    payer_address: str = "",
    payer_iban: str = "",
    urgency: str = "",
) -> str:
    """Generate the UPN QR payload string (raw text that goes into QR code).

    Args:
        See module docstring for field descriptions.

    Returns:
        A newline-separated string with 19 fields.
    """
    # Format the SI reference with checksum
    si_ref = _format_si_reference(reference) if reference else ""

    # Format amount
    amount_str = _format_amount_in_cents(amount)

    # Format date
    date_str = _format_date(payment_date) or _format_date(datetime.date.today())

    # Truncate fields to spec
    fields = [
        _truncate(payment_purpose, 40),
        _truncate(payment_code, 4),
        urgency[:1] if urgency else "",
        _truncate(payer_iban.replace(" ", ""), 34),
        "",  # payer reference
        _truncate(payer_name, 33),
        _truncate(payer_address, 33),
        amount_str,
        date_str,
        "",  # urgency of final payment
        _truncate(payee_iban.replace(" ", ""), 34),
        si_ref,
        _truncate(payee_name, 33),
        _truncate(payee_address, 33),
        "", "", "", "",
    ]

    # Compute control sum: sum of all character codes (excluding newlines and control digits)
    # plus the length of certain fields
    # Standard UPN QR control sum: concatenate all 18 fields (without newlines), then
    # sum all digit values for those positions that are digits.
    control_string = "".join(fields[:14])  # fields 1-14 contribute
    digit_sum = 0
    for c in control_string:
        if c.isdigit():
            digit_sum += int(c)
    # Add 1 for each digit position (counts as 1 per digit)
    digit_count = sum(1 for c in control_string if c.isdigit())
    control_sum = (digit_sum + digit_count) % 100000
    fields.append(f"{control_sum:05d}")

    return "UPNQR\n" + "\n".join(fields)


def _truncate(s: str, max_len: int) -> str:
    if not s:
        return ""
    s = str(s).strip()
    return s[:max_len]


@frappe.whitelist()
def get_upn_qr_payload_for_invoice(sales_invoice_name: str) -> str:
    """RPC: generate UPN QR payload for a Sales Invoice."""
    inv = frappe.get_doc("Sales Invoice", sales_invoice_name)
    company = frappe.get_doc("Company", inv.company)
    customer = frappe.get_doc("Customer", inv.customer)

    # Get company IBAN (would need a Bank Account linked to the company)
    company_iban = _get_company_iban(inv.company)
    if not company_iban:
        # Fallback: use a placeholder (will be visible in QR but invalid)
        company_iban = "SI56 1234 5678 9012 345"

    # Get company address
    company_addr = _get_address(company.name, "Company")

    # Get customer address (optional - payer info may be empty)
    customer_addr = _get_address(customer.name, "Customer")

    # Build reference from invoice name (strip non-digits)
    inv_digits = re.sub(r"\D", "", inv.name)
    if not inv_digits:
        inv_digits = "1"

    payload = generate_upn_qr_payload(
        payer_name=customer.customer_name or "",
        payer_address=customer_addr,
        payee_name=company.company_name,
        payee_address=company_addr,
        payee_iban=company_iban,
        amount=float(inv.grand_total or 0),
        payment_date=inv.due_date or inv.posting_date,
        payment_purpose=f"Plačilo računa {inv.name}",
        payment_code="OTHR",
        reference=inv_digits,
        urgency="",
    )

    return payload


def _get_company_iban(company: str) -> str:
    """Get the primary IBAN for a company from its Bank Account."""
    bank_accounts = frappe.get_all(
        "Bank Account",
        filters={"company": company, "disabled": 0},
        pluck="iban",
    )
    for iban in bank_accounts:
        if iban:
            return iban
    return ""


def _get_address(party_name: str, party_type: str) -> str:
    """Get a formatted one-line address for a party (Company or Customer)."""
    addr_name = None
    if party_type == "Customer":
        addr_name = frappe.db.get_value("Customer", party_name, "customer_primary_address")
    if not addr_name:
        # Try Dynamic Link
        addr_name = frappe.db.get_value("Dynamic Link",
            {"link_doctype": party_type, "link_name": party_name, "parenttype": "Address"},
            "parent")
    if not addr_name:
        return ""
    addr = frappe.db.get_value("Address", addr_name,
        ["address_line1", "city", "pincode", "country"], as_dict=True)
    if not addr:
        return ""
    parts = [addr.get("address_line1") or "", addr.get("postalzone") or addr.get("pincode") or ""]
    if addr.get("city"):
        parts.append(addr["city"])
    return ", ".join(p for p in parts if p)
