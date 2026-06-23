"""
FURS eDavki API integration for Slovenian electronic tax submissions.

FURS (Finančna uprava Republike Slovenije) provides eDavki API for:
- Submitting VAT returns (DDV-Obr)
- Submitting corporate income tax (DDPO)
- Submitting other tax forms

The actual production API uses SOAP/WSDL and requires a digital certificate
(.p12 / .pfx) issued by FURS or a qualified CA in Slovenia.

For demo purposes, this module:
1. Generates the proper eDavki XML (already done in edavki/ddv_obracun_xml.py)
2. Prepares the SOAP envelope for submission
3. Provides a stub submit_xml() function that can be replaced with real API call
   when a digital certificate is available.

Production setup:
  - Acquire digital certificate from SI-TRUST, FURS, or other qualified CA
  - Convert .p12 to .pem (cert + key)
  - Set Site Config: furs_cert_path, furs_cert_password
  - Call submit_ddv_obracun() — it will use the cert for mutual TLS auth

References:
  - https://edavki.fu.gov.si/
  - eDavki technical documentation
"""
import os
import datetime
import frappe
from frappe import _


FURS_EDAVKI_TEST_URL = "https://edavki-test.fu.gov.si:9002/DavkovnaBlagajna"
FURS_EDAVKI_PROD_URL = "https://edavki.fu.gov.si:9002/DavkovnaBlagajna"
FURS_EDAVKI_SOAP_ACTION = "http://www.fu.gov.si/eDavki/v1/submitDocument"


def get_furs_config() -> dict:
    """Get FURS configuration from Site Config."""
    return {
        "cert_path": frappe.conf.get("furs_cert_path"),
        "cert_password": frappe.conf.get("furs_cert_password"),
        "test_mode": frappe.conf.get("furs_test_mode", 1),
        "timeout": frappe.conf.get("furs_timeout", 30),
    }


def is_furs_configured() -> bool:
    """Check if FURS is properly configured (cert path set)."""
    cfg = get_furs_config()
    return bool(cfg["cert_path"] and os.path.exists(cfg["cert_path"]))


def wrap_in_soap_envelope(xml_content: str, document_id: str = None) -> str:
    """Wrap an eDavki XML document in a SOAP envelope for submission.

    Args:
        xml_content: The eDavki XML document body (returned by generate_ddv_obracun_xml)
        document_id: Optional unique ID for tracking (auto-generated if missing)

    Returns:
        A string with the SOAP envelope containing the XML document.
    """
    if not document_id:
        document_id = f"DOC-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"

    # The SOAP envelope must be properly namespaced
    soap = f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
               xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <soap:Body>
    <submitDocument xmlns="http://www.fu.gov.si/eDavki/v1">
      <documentId>{document_id}</documentId>
      <document>{_escape_xml(xml_content)}</document>
    </submitDocument>
  </soap:Body>
</soap:Envelope>"""
    return soap


def submit_xml_to_furs(soap_envelope: str, config: dict = None) -> dict:
    """Submit SOAP envelope to FURS eDavki API.

    Args:
        soap_envelope: The SOAP-wrapped XML to submit
        config: Optional config override (uses get_furs_config() if not provided)

    Returns:
        Dict with: success (bool), response (str), error (str or None)
    """
    if config is None:
        config = get_furs_config()

    if not is_furs_configured():
        return {
            "success": False,
            "response": None,
            "error": _("FURS ni konfiguriran. Manjka pot do digitalnega potrdila "
                      "(nastavi furs_cert_path v site_config.json)."),
            "soap_envelope": soap_envelope,
        }

    # Production submission requires HTTP POST with mutual TLS auth
    # using the digital certificate. We use requests with cert= argument.
    try:
        import requests  # Lazy import
    except ImportError:
        return {
            "success": False,
            "response": None,
            "error": _("Knjižnica 'requests' ni nameščena."),
            "soap_envelope": soap_envelope,
        }

    url = FURS_EDAVKI_TEST_URL if config["test_mode"] else FURS_EDAVKI_PROD_URL
    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": FURS_EDAVKI_SOAP_ACTION,
    }

    try:
        # Note: requests supports cert= as a tuple (certfile, keyfile) or a single .pem path
        # For .p12 files, conversion to .pem is required first
        cert_path = config["cert_path"]
        if cert_path.endswith(".p12") or cert_path.endswith(".pfx"):
            return {
                "success": False,
                "response": None,
                "error": _("Digitalno potrdilo .p12/.pfx mora biti pretvorjeno v .pem "
                          "format za uporabo z requests knjižnico. Uporabi:\n"
                          "openssl pkcs12 -in cert.p12 -out cert.pem -nodes"),
                "soap_envelope": soap_envelope,
            }

        response = requests.post(
            url,
            data=soap_envelope.encode("utf-8"),
            headers=headers,
            cert=cert_path,
            verify=True,
            timeout=config["timeout"],
        )

        if response.status_code == 200:
            return {
                "success": True,
                "response": response.text,
                "error": None,
                "status_code": response.status_code,
            }
        else:
            return {
                "success": False,
                "response": response.text,
                "error": f"HTTP {response.status_code}: {response.reason}",
                "status_code": response.status_code,
            }
    except Exception as e:
        return {
            "success": False,
            "response": None,
            "error": str(e),
            "soap_envelope": soap_envelope,
        }


@frappe.whitelist()
def submit_ddv_obracun(company: str, from_date: str, to_date: str, period_type: str = "month") -> dict:
    """RPC: Generate and submit DDV-Obr to FURS.

    Returns the submission result including the SOAP envelope (for debugging)
    and the FURS response (if submission was attempted).
    """
    from erpnext_slovenia.edavki.ddv_obracun_xml import generate_ddv_obracun_xml

    # 1. Generate the eDavki XML
    xml_content = generate_ddv_obracun_xml(company, from_date, to_date, period_type)

    # 2. Wrap in SOAP envelope
    document_id = f"DDV-OBR-{from_date.replace('-', '')}-{to_date.replace('-', '')}"
    soap_envelope = wrap_in_soap_envelope(xml_content, document_id)

    # 3. Submit (will return error if not configured)
    result = submit_xml_to_furs(soap_envelope)

    # 4. Log submission attempt
    log_submission(company, from_date, to_date, period_type, xml_content, soap_envelope, result)

    return {
        "document_id": document_id,
        "xml_content": xml_content,
        "soap_envelope": soap_envelope,
        "submission": result,
        "furs_configured": is_furs_configured(),
    }


@frappe.whitelist()
def get_submission_status(submission_id: str) -> dict:
    """RPC: Get the status of a previous submission."""
    if not frappe.db.exists("FURS Submission Log", submission_id):
        return {"success": False, "error": _("Submission not found")}

    doc = frappe.get_doc("FURS Submission Log", submission_id)
    return {
        "success": True,
        "status": doc.status,
        "document_id": doc.document_id,
        "submitted_at": doc.submitted_at,
        "response": doc.furs_response,
        "error": doc.error_message,
    }


def log_submission(company, from_date, to_date, period_type, xml, soap, result):
    """Create a FURS Submission Log record."""
    try:
        log = frappe.get_doc({
            "doctype": "FURS Submission Log",
            "company": company,
            "from_date": from_date,
            "to_date": to_date,
            "period_type": period_type,
            "document_type": "DDV-Obr",
            "document_id": f"DDV-OBR-{from_date.replace('-', '')}-{to_date.replace('-', '')}",
            "xml_content": xml[:65000] if len(xml) > 65000 else xml,  # truncate for storage
            "soap_envelope": soap[:65000] if len(soap) > 65000 else soap,
            "status": "Submitted" if result.get("success") else "Failed",
            "submitted_at": datetime.datetime.now(),
            "furs_response": result.get("response", "")[:65000] if result.get("response") else "",
            "error_message": result.get("error", ""),
            "http_status": result.get("status_code"),
        })
        log.flags.ignore_permissions = True
        log.insert()
        frappe.db.commit()
        return log.name
    except Exception as e:
        # If FURS Submission Log doctype doesn't exist, just skip
        frappe.log_error(f"Failed to log FURS submission: {e}")
        return None


def _escape_xml(text: str) -> str:
    """Escape XML special characters for embedding inside an XML element."""
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
