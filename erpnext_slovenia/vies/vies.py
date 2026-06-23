"""
VIES (VAT Information Exchange System) validation for EU VAT numbers.

Uses the official EU VIES SOAP API to validate VAT numbers in real-time.
Reference: https://ec.europa.eu/taxation_customs/vies/

The VIES service is free and publicly available. It returns whether a given
VAT number is valid (registered) in the corresponding EU member state.

For Slovenia, the country code is "SI" and the VAT number is 8 digits.
"""
import datetime
import frappe
from frappe import _


VIES_SOAP_URL = "http://ec.europa.eu/taxation_customs/vies/services/checkVatService"
VIES_SOAP_NS = "urn:ec.europa.eu:taxud:vies:services:checkVat:types"


VIES_SOAP_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:ns="{ns}">
  <soap:Body>
    <ns:checkVat>
      <ns:countryCode>{country}</ns:countryCode>
      <ns:vatNumber>{vat_number}</ns:vatNumber>
    </ns:checkVat>
  </soap:Body>
</soap:Envelope>"""


def validate_vat_number(country_code: str, vat_number: str) -> dict:
    """Validate an EU VAT number via VIES.

    Args:
        country_code: 2-letter ISO country code (e.g., "SI", "DE", "AT")
        vat_number: VAT number without the country prefix

    Returns:
        Dict with:
          - valid (bool): True if VAT number is valid
          - name (str): Registered company name (if valid)
          - address (str): Registered address (if valid)
          - request_date (str): Date of the VIES response
          - error (str or None): Error message if validation failed
    """
    country_code = (country_code or "").strip().upper()
    vat_number = (vat_number or "").strip()

    # Strip country prefix from VAT number if present
    if vat_number.upper().startswith(country_code):
        vat_number = vat_number[len(country_code):].strip()

    # Basic format check before calling VIES
    if not country_code or not vat_number:
        return {
            "valid": False,
            "error": _("Manjkajoča država ali davčna številka."),
        }

    # Build SOAP request
    soap = VIES_SOAP_TEMPLATE.format(
        ns=VIES_SOAP_NS,
        country=country_code,
        vat_number=vat_number,
    )

    try:
        import requests  # Lazy import
    except ImportError:
        return {
            "valid": False,
            "error": _("Knjižnica 'requests' ni nameščena."),
        }

    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": "",
    }

    try:
        response = requests.post(
            VIES_SOAP_URL,
            data=soap.encode("utf-8"),
            headers=headers,
            timeout=15,
        )

        if response.status_code != 200:
            return {
                "valid": False,
                "error": f"VIES HTTP {response.status_code}: {response.reason}",
                "raw_response": response.text[:500],
            }

        # Parse SOAP response (simple regex-based; we avoid heavy XML libs)
        return _parse_vies_response(response.text, country_code, vat_number)

    except requests.exceptions.Timeout:
        return {
            "valid": False,
            "error": _("VIES servis ni odgovoril v roku (timeout)."),
        }
    except requests.exceptions.ConnectionError as e:
        return {
            "valid": False,
            "error": _("Napaka povezave z VIES: {0}").format(str(e)),
        }
    except Exception as e:
        return {
            "valid": False,
            "error": f"VIES error: {e}",
        }


def _parse_vies_response(soap_text: str, country: str, vat_number: str) -> dict:
    """Parse VIES SOAP response using regex (avoid heavy XML deps)."""
    import re

    # Extract <valid>true|false</valid>
    valid_match = re.search(r"<valid[^>]*>(true|false)</valid>", soap_text, re.IGNORECASE)
    valid = bool(valid_match and valid_match.group(1).lower() == "true")

    # Extract <name>...</name>
    name_match = re.search(r"<name[^>]*>([^<]*)</name>", soap_text, re.IGNORECASE)
    name = name_match.group(1) if name_match else ""

    # Extract <address>...</address>
    addr_match = re.search(r"<address[^>]*>([^<]*)</address>", soap_text, re.IGNORECASE)
    address = addr_match.group(1) if addr_match else ""

    # Extract <requestDate>...</requestDate>
    date_match = re.search(r"<requestDate[^>]*>([^<]*)</requestDate>", soap_text, re.IGNORECASE)
    request_date = date_match.group(1) if date_match else ""

    # Check for fault (error in VIES service)
    fault_match = re.search(r"<faultstring[^>]*>([^<]*)</faultstring>", soap_text, re.IGNORECASE)
    if fault_match:
        return {
            "valid": False,
            "error": _("VIES napaka: {0}").format(fault_match.group(1)),
            "country": country,
            "vat_number": vat_number,
        }

    return {
        "valid": valid,
        "name": name,
        "address": address,
        "request_date": request_date,
        "country": country,
        "vat_number": vat_number,
        "error": None if valid else _("Davčna številka ni veljavna (VIES)."),
    }


@frappe.whitelist()
def validate_customer_vat(customer_name: str) -> dict:
    """RPC: validate a Customer's VAT number via VIES.

    Returns validation result + registered name + address (if valid).
    """
    cust = frappe.get_doc("Customer", customer_name)
    tax_id = cust.tax_id or cust.get("custom_si_tax_id") or ""

    # Determine country
    country = "SI"  # default
    addr_name = frappe.db.get_value("Customer", customer_name, "customer_primary_address")
    if addr_name:
        country_full = frappe.db.get_value("Address", addr_name, "country")
        # Map common country names to ISO codes
        country_map = {
            "Slovenia": "SI", "Italy": "IT", "Austria": "AT", "Germany": "DE",
            "Croatia": "HR", "France": "FR", "Spain": "ES", "Poland": "PL",
            "Hungary": "HU", "Czech Republic": "CZ", "Slovakia": "SK",
            "Belgium": "BE", "Netherlands": "NL", "Luxembourg": "LU",
            "Greece": "EL",  # VIES uses EL for Greece
            "Portugal": "PT", "Ireland": "IE", "Denmark": "DK",
            "Sweden": "SE", "Finland": "FI", "Estonia": "EE",
            "Latvia": "LV", "Lithuania": "LT", "Bulgaria": "BG",
            "Romania": "RO", "Cyprus": "CY", "Malta": "MT",
        }
        country = country_map.get(country_full, "SI")

    if not tax_id:
        return {
            "valid": False,
            "error": _("Stranka nima nastavljene davčne številke."),
        }

    result = validate_vat_number(country, tax_id)

    # Store validation result on Customer (optional, for audit)
    try:
        cust.db_set("custom_si_vies_validated", 1 if result.get("valid") else 0)
        cust.db_set("custom_si_vies_validated_at", datetime.datetime.now())
        cust.db_set("custom_si_vies_name", result.get("name", "")[:140])
        frappe.db.commit()
    except Exception:
        # Custom fields might not exist; ignore
        pass

    return result


@frappe.whitelist()
def validate_supplier_vat(supplier_name: str) -> dict:
    """RPC: validate a Supplier's VAT number via VIES."""
    sup = frappe.get_doc("Supplier", supplier_name)
    tax_id = sup.tax_id or sup.get("custom_si_tax_id") or ""
    country = "SI"
    if hasattr(sup, "country") and sup.country:
        country_map = {"Slovenia": "SI", "Italy": "IT", "Austria": "AT", "Germany": "DE"}
        country = country_map.get(sup.country, "SI")

    if not tax_id:
        return {"valid": False, "error": _("Dobavitelj nima nastavljene davčne številke.")}

    return validate_vat_number(country, tax_id)


@frappe.whitelist()
def validate_any_vat(country_code: str, vat_number: str) -> dict:
    """RPC: validate any EU VAT number via VIES.

    Useful for ad-hoc validation in UI.
    """
    return validate_vat_number(country_code, vat_number)
