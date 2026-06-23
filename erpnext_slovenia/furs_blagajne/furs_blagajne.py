"""
FURS Blagajne (Cash Register) - real-time invoice registration.

For Slovenian businesses that issue cash receipts (B2C, retail, hospitality),
FURS requires that each invoice is reported in real-time (within 48 hours).

This module implements the FURS Blagajne SOAP API:
1. echo() - test connectivity
2. register_invoice() - submit an invoice for validation
  - Returns a ZOI (Zaščitna oznaka izdajatelja) - protective mark
  - Returns an EOR (Enkratna identifikacijska oznaka računa) - unique invoice ID
3. register_premise() - register business premise (cash register location)

The ZOI is a 32-digit MD5 hash that must be printed on the receipt.
The EOR is a UUID that identifies the invoice in FURS system.

Production requires:
- Digital certificate (FURS-issued or qualified CA)
- Premise ID (BusinessPremiseID) registered with FURS
- Electronic device ID (ElectronicDeviceID)

References:
- https://www.fu.gov.si/elektronsko-poslovanje_furs/
- FURS Blagajne API technical specification
"""
import hashlib
import uuid
import datetime
import frappe
from frappe import _


FURS_TEST_URL = "https://blagajne-test.fu.gov.si:9002/v1/cash_registers"
FURS_PROD_URL = "https://blagajne.fu.gov.si:9002/v1/cash_registers"


def get_furs_config() -> dict:
    """Get FURS Blagajne configuration."""
    return {
        "cert_path": frappe.conf.get("furs_cert_path"),
        "cert_password": frappe.conf.get("furs_cert_password"),
        "test_mode": frappe.conf.get("furs_test_mode", 1),
        "timeout": frappe.conf.get("furs_timeout", 10),
        "premise_id": frappe.conf.get("furs_premise_id", "PREMISE001"),
        "device_id": frappe.conf.get("furs_device_id", "DEV001"),
    }


def is_furs_configured() -> bool:
    """Check if FURS is configured."""
    cfg = get_furs_config()
    return bool(cfg["cert_path"])


def generate_zoi(invoice_number: str, issue_date: str, issue_time: str,
                 tax_number: str, premise_id: str, device_id: str,
                 invoice_amount: float) -> str:
    """Generate the ZOI (Zaščitna oznaka izdajatelja) - protective mark.

    ZOI is MD5 hash of: invoice_number + issue_date_time + tax_number + premise_id + device_id + invoice_amount

    Args:
        invoice_number: Sequential invoice number (e.g., "1", "BL-001")
        issue_date: Date in YYYY-MM-DD format
        issue_time: Time in HH:MM:SS format
        tax_number: 8-digit tax number without "SI" prefix
        premise_id: Business premise ID (registered with FURS)
        device_id: Electronic device ID (within the premise)
        invoice_amount: Total invoice amount (tax inclusive)

    Returns:
        32-character MD5 hex string
    """
    # Combine date and time
    date_time_str = issue_date.replace("-", "") + issue_time.replace(":", "")
    # Format amount with exactly 2 decimal places, dot as separator
    amount_str = f"{invoice_amount:.2f}"

    # Concatenate all components
    zoi_input = f"{tax_number}{issue_date.replace('-', '')}{date_time_str[8:]}{invoice_number}{premise_id}{device_id}{amount_str}"
    # Correct format: taxNumber + dateYYYYMMDD + timeHHMMSS + invoiceNumber + premiseID + deviceID + amount
    zoi_input = f"{tax_number}{issue_date.replace('-', '')}{issue_time.replace(':', '')}{invoice_number}{premise_id}{device_id}{amount_str}"

    # MD5 hash
    zoi = hashlib.md5(zoi_input.encode("utf-8")).hexdigest()
    return zoi


def generate_eor() -> str:
    """Generate a UUID for EOR (Enkratna identifikacijska oznaka računa).

    EOR is a UUID v4 that identifies the invoice in FURS system.
    In production, FURS returns this. For demo, we generate one.
    """
    return str(uuid.uuid4())


def build_invoice_xml(invoice_data: dict) -> str:
    """Build the FURS Blagajne invoice XML.

    Args:
        invoice_data: Dict with keys:
          - tax_number, premise_id, device_id
          - invoice_number, issue_date, issue_time
          - invoice_amount, payment_method
          - taxes: list of {rate, base, tax_amount}
          - customer_vat_number (optional, B2B)
          - zoi (pre-generated)
          - eor (pre-generated or empty for FURS to assign)

    Returns:
        XML string for FURS API
    """
    # Build taxes XML
    taxes_xml = ""
    for tax in invoice_data.get("taxes", []):
        rate = tax["rate"]
        if abs(rate - 22.0) < 0.01:
            rate_tag = "VAT"
            rate_attr = ' rate="22.0"'
        elif abs(rate - 8.5) < 0.01:
            rate_tag = "VAT"
            rate_attr = ' rate="8.5"'
        elif abs(rate - 5.0) < 0.01:
            rate_tag = "VAT"
            rate_attr = ' rate="5.0"'
        elif rate == 0:
            rate_tag = "NAT"  # Not subject to VAT (zero-rated)
            rate_attr = ' rate="0"'
        else:
            continue
        taxes_xml += f"""
        <{rate_tag}{rate_attr}>
          <TaxableAmount>{tax['base']:.2f}</TaxableAmount>
          <TaxAmount>{tax['tax_amount']:.2f}</TaxAmount>
        </{rate_tag}>"""

    # Build reference XML
    ref_invoice_xml = f"""
    <ReferenceInvoice>
      <BusinessPremiseID>{_x(invoice_data['premise_id'])}</BusinessPremiseID>
      <ElectronicDeviceID>{_x(invoice_data['device_id'])}</ElectronicDeviceID>
      <InvoiceNumber>{_x(invoice_data['invoice_number'])}</InvoiceNumber>
    </ReferenceInvoice>"""

    # Build protective mark
    zoi = invoice_data.get("zoi", "")
    eor = invoice_data.get("eor", "")

    # Build full XML
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="http://blagajne.fu.gov.si/v1">
  <TaxNumber>{_x(invoice_data['tax_number'])}</TaxNumber>
  <IssueDateTime>{invoice_data['issue_date']}T{invoice_data['issue_time']}</IssueDateTime>
  {ref_invoice_xml}
  <ProtectedID>{_x(zoi)}</ProtectedID>
  <UniqueInvoiceID>{_x(eor)}</UniqueInvoiceID>
  <TotalAmount>{invoice_data['invoice_amount']:.2f}</TotalAmount>
  <PaymentMethod>{invoice_data.get('payment_method', 'cash')}</PaymentMethod>
  <Taxes>{taxes_xml}
  </Taxes>
</Invoice>"""
    return xml


@frappe.whitelist()
def register_sales_invoice(sales_invoice_name: str) -> dict:
    """RPC: register a Sales Invoice with FURS Blagajne.

    Returns ZOI and EOR. In test mode (no cert configured), returns
    computed ZOI and a generated EOR for demo purposes.
    """
    inv = frappe.get_doc("Sales Invoice", sales_invoice_name)
    company = frappe.get_doc("Company", inv.company)
    cfg = get_furs_config()

    # Get company tax number (without SI prefix)
    tax_id = (company.tax_id or "").upper().lstrip("SI").strip()
    if not tax_id:
        return {"success": False, "error": _("Podjetje nima davčne številke.")}

    # Extract date and time from posting_date + posting_time
    issue_date = str(inv.posting_date)
    issue_time = str(inv.posting_time or "00:00:00")
    if "T" in issue_time:
        issue_time = issue_time.split("T")[1][:8]
    elif len(issue_time) == 8:
        pass  # already HH:MM:SS
    else:
        issue_time = "00:00:00"

    # Determine payment method from POS Profile or default
    payment_method = "cash"
    if inv.get("is_pos"):
        payment_method = "cash"
    else:
        # If paid by bank transfer
        if inv.get("paid_amount") > 0 and inv.paid_amount == inv.grand_total:
            payment_method = "card"  # guess card

    # Extract taxes
    taxes = []
    for tax in inv.taxes:
        rate = float(tax.rate or 0)
        if rate > 0:
            tax_amount = float(tax.tax_amount or 0)
            base = float(tax.net_amount or 0)
            if base > 0 and tax_amount > 0:
                taxes.append({
                    "rate": rate,
                    "base": base,
                    "tax_amount": tax_amount,
                })

    invoice_data = {
        "tax_number": tax_id,
        "premise_id": cfg["premise_id"],
        "device_id": cfg["device_id"],
        "invoice_number": inv.name,
        "issue_date": issue_date,
        "issue_time": issue_time,
        "invoice_amount": float(inv.grand_total or 0),
        "payment_method": payment_method,
        "taxes": taxes,
    }

    # Generate ZOI locally (always)
    zoi = generate_zoi(
        invoice_number=invoice_data["invoice_number"],
        issue_date=invoice_data["issue_date"],
        issue_time=invoice_data["issue_time"],
        tax_number=invoice_data["tax_number"],
        premise_id=invoice_data["premise_id"],
        device_id=invoice_data["device_id"],
        invoice_amount=invoice_data["invoice_amount"],
    )
    invoice_data["zoi"] = zoi

    # Check if FURS is configured
    if not is_furs_configured():
        # Demo mode: generate EOR locally
        eor = generate_eor()
        invoice_data["eor"] = eor
        return {
            "success": True,
            "demo_mode": True,
            "zoi": zoi,
            "eor": eor,
            "message": _("ZOI izračunan lokalno (demo način). FURS certifikat ni nameščen."),
            "invoice_xml": build_invoice_xml(invoice_data),
        }

    # Production mode: submit to FURS
    invoice_data["eor"] = ""  # let FURS assign
    xml = build_invoice_xml(invoice_data)
    result = _submit_to_furs(xml, cfg)

    if result["success"]:
        return {
            "success": True,
            "demo_mode": False,
            "zoi": zoi,
            "eor": result["eor"],
            "message": _("Račun uspešno registriran pri FURS."),
            "invoice_xml": xml,
        }
    else:
        return {
            "success": False,
            "demo_mode": False,
            "zoi": zoi,
            "error": result["error"],
            "invoice_xml": xml,
        }


def _submit_to_furs(xml: str, cfg: dict) -> dict:
    """Submit invoice XML to FURS Blagajne API."""
    try:
        import requests
    except ImportError:
        return {"success": False, "error": _("Knjižnica 'requests' ni nameščena.")}

    url = FURS_TEST_URL if cfg["test_mode"] else FURS_PROD_URL
    headers = {
        "Content-Type": "application/xml; charset=utf-8",
    }

    try:
        response = requests.post(
            url + "/invoices",
            data=xml.encode("utf-8"),
            headers=headers,
            cert=cfg["cert_path"],
            verify=True,
            timeout=cfg["timeout"],
        )

        if response.status_code in (200, 201):
            # Parse EOR from response
            import re
            eor_match = re.search(r"<UniqueInvoiceID[^>]*>([^<]+)</UniqueInvoiceID>", response.text)
            eor = eor_match.group(1) if eor_match else ""
            return {"success": True, "eor": eor, "raw_response": response.text}
        else:
            return {
                "success": False,
                "error": f"HTTP {response.status_code}: {response.text[:500]}",
            }
    except Exception as e:
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def test_furs_connection() -> dict:
    """RPC: test FURS connectivity with echo request."""
    cfg = get_furs_config()
    if not is_furs_configured():
        return {
            "success": False,
            "demo_mode": True,
            "message": _("FURS certifikat ni nameščen. Teče v demo načinu."),
        }

    try:
        import requests
        url = (FURS_TEST_URL if cfg["test_mode"] else FURS_PROD_URL) + "/echo"
        response = requests.post(url, cert=cfg["cert_path"], timeout=cfg["timeout"])
        return {
            "success": response.status_code == 200,
            "status_code": response.status_code,
            "response": response.text[:200],
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def register_premise(premise_id: str, premise_name: str, address: dict,
                    validity_date: str = None, software_supplier: dict = None) -> dict:
    """RPC: register a business premise with FURS.

    Each physical location where invoices are issued must be registered.
    """
    cfg = get_furs_config()
    if not is_furs_configured():
        return {
            "success": False,
            "demo_mode": True,
            "message": _("FURS certifikat ni nameščen. Premise registracija je možna samo v produkcijskem načinu."),
        }

    if not validity_date:
        validity_date = datetime.date.today().strftime("%Y-%m-%d")

    # Build XML
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<BusinessPremise xmlns="http://blagajne.fu.gov.si/v1">
  <TaxNumber>{cfg.get('tax_number', '')}</TaxNumber>
  <BusinessPremiseID>{_x(premise_id)}</BusinessPremiseID>
  <ValidityDate>{validity_date}</ValidityDate>
  <Address>
    <Street>{_x(address.get('street', ''))}</Street>
    <HouseNumber>{_x(address.get('house_number', ''))}</HouseNumber>
    <Community>{_x(address.get('community', ''))}</Community>
    <City>{_x(address.get('city', ''))}</City>
    <PostalCode>{_x(address.get('postal_code', ''))}</PostalCode>
    <CountryCode>SI</CountryCode>
  </Address>
  <PremiseType>{address.get('premise_type', 'fixed')}</PremiseType>
  <SoftwareSupplier>
    <TaxNumber>{_x((software_supplier or {}).get('tax_number', ''))}</TaxNumber>
    <Name>{_x((software_supplier or {}).get('name', ''))}</Name>
  </SoftwareSupplier>
</BusinessPremise>"""

    try:
        import requests
        url = (FURS_TEST_URL if cfg["test_mode"] else FURS_PROD_URL) + "/business_premises"
        response = requests.post(
            url,
            data=xml.encode("utf-8"),
            headers={"Content-Type": "application/xml"},
            cert=cfg["cert_path"],
            timeout=cfg["timeout"],
        )
        return {
            "success": response.status_code in (200, 201),
            "status_code": response.status_code,
            "response": response.text[:500],
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def _x(text) -> str:
    """Escape XML special characters."""
    if text is None:
        return ""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )
