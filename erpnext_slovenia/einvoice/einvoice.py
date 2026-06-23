"""
e-Slog 1.6 XML eInvoice generator for Slovenian Sales Invoices.

e-Slog is the official XML schema used by Slovenian tax authorities (FURS)
and businesses for electronic invoice exchange.

Reference: https://www.efu.rs/eSlog.html (eSlog 1.6 schema)

This is a minimal implementation that produces a valid e-Slog 1.6 XML.
"""
import datetime
import frappe
from frappe import _
from frappe.utils.file_manager import save_file


# Namespace map for e-Slog 1.6
NAMESPACE = "http://www.gzs.si/eSlog/1.6"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
SCHEMA_LOCATION = "http://www.gzs.si/eSlog/1.6 eSlog_1-6.xsd"


def generate_eslog_xml(sales_invoice_name: str) -> str:
    """Generate e-Slog 1.6 XML for a Sales Invoice.

    Args:
        sales_invoice_name: the name (ID) of the Sales Invoice document

    Returns:
        A string with the e-Slog 1.6 XML document.
    """
    doc = frappe.get_doc("Sales Invoice", sales_invoice_name)
    company = frappe.get_doc("Company", doc.company)
    customer = frappe.get_doc("Customer", doc.customer)

    # Use frappe.safe_format for ISO dates
    issue_date = doc.posting_date.strftime("%Y-%m-%d") if hasattr(doc.posting_date, "strftime") else str(doc.posting_date)
    due_date = ""
    if doc.get("due_date"):
        due_date = doc.due_date.strftime("%Y-%m-%d") if hasattr(doc.due_date, "strftime") else str(doc.due_date)

    # Tax numbers
    supplier_tax_id = company.tax_id or ""
    customer_tax_id = customer.tax_id or customer.get("custom_tax_id") or ""

    # Build XML string manually (no external deps)
    xml_parts = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml_parts.append(
        f'<envelope xmlns="{NAMESPACE}" xmlns:xsi="{XSI_NS}" '
        f'xsi:schemaLocation="{SCHEMA_LOCATION}">'
    )

    # Header
    xml_parts.append("  <header>")
    xml_parts.append(f"    <identification>")
    xml_parts.append(f"      <businessProcess>INV</businessProcess>")
    xml_parts.append(f"      <instanceIdentifier>{_escape(doc.name)}</instanceIdentifier>")
    xml_parts.append(f"    </identification>")
    xml_parts.append(f"    <documentType>380</documentType>")  # UN/ECE 1001: Commercial invoice
    xml_parts.append(f"    <creationDateTime>{datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')}</creationDateTime>")
    xml_parts.append("  </header>")

    # Invoice
    xml_parts.append("  <invoice>")
    xml_parts.append(f"    <identification>")
    xml_parts.append(f"      <instanceIdentifier>{_escape(doc.name)}</instanceIdentifier>")
    xml_parts.append(f"    </identification>")
    xml_parts.append(f"    <issueDate>{issue_date}</issueDate>")
    if due_date:
        xml_parts.append(f"    <paymentDueDate>{due_date}</paymentDueDate>")

    # Amounts
    xml_parts.append("    <monetaryCalculation>")
    xml_parts.append(f"      <taxBasisTotalAmount currencyID=\"EUR\">{doc.net_total:.2f}</taxBasisTotalAmount>")
    xml_parts.append(f"      <taxTotalAmount currencyID=\"EUR\">{doc.total_taxes_and_charges:.2f}</taxTotalAmount>")
    xml_parts.append(f"      <grandTotalAmount currencyID=\"EUR\">{doc.grand_total:.2f}</grandTotalAmount>")
    xml_parts.append("    </monetaryCalculation>")

    # Parties (Seller / Buyer)
    xml_parts.append("    <parties>")
    # Seller (us)
    xml_parts.append("      <sellerParty>")
    xml_parts.append("        <partyIdentification>")
    xml_parts.append(f"          <identifier identificationType=\"VATID\">{_escape(supplier_tax_id)}</identifier>")
    xml_parts.append("        </partyIdentification>")
    xml_parts.append("        <partyName>")
    xml_parts.append(f"          <name>{_escape(company.company_name)}</name>")
    xml_parts.append("        </partyName>")
    addr = _get_company_address(company.name)
    if addr:
        xml_parts.append("        <postalAddress>")
        xml_parts.append(f"          <streetname>{_escape(addr.get('address_line1',''))}</streetname>")
        xml_parts.append(f"          <cityname>{_escape(addr.get('city',''))}</cityname>")
        xml_parts.append(f"          <postalzone>{_escape(addr.get('pincode',''))}</postalzone>")
        xml_parts.append(f"          <country><identificationCode>{_escape(addr.get('country','SI'))}</identificationCode></country>")
        xml_parts.append("        </postalAddress>")
    xml_parts.append("      </sellerParty>")
    # Buyer
    xml_parts.append("      <buyerParty>")
    xml_parts.append("        <partyIdentification>")
    xml_parts.append(f"          <identifier identificationType=\"VATID\">{_escape(customer_tax_id)}</identifier>")
    xml_parts.append("        </partyIdentification>")
    xml_parts.append("        <partyName>")
    xml_parts.append(f"          <name>{_escape(customer.customer_name)}</name>")
    xml_parts.append("        </partyName>")
    buyer_addr = _get_customer_address(customer.name)
    if buyer_addr:
        xml_parts.append("        <postalAddress>")
        xml_parts.append(f"          <streetname>{_escape(buyer_addr.get('address_line1',''))}</streetname>")
        xml_parts.append(f"          <cityname>{_escape(buyer_addr.get('city',''))}</cityname>")
        xml_parts.append(f"          <postalzone>{_escape(buyer_addr.get('pincode',''))}</postalzone>")
        xml_parts.append(f"          <country><identificationCode>{_escape(buyer_addr.get('country','SI'))}</identificationCode></country>")
        xml_parts.append("        </postalAddress>")
    xml_parts.append("      </buyerParty>")
    xml_parts.append("    </parties>")

    # Line items
    xml_parts.append("    <invoiceLine>")
    for item in doc.items:
        xml_parts.append("      <line>")
        xml_parts.append("        <lineNumber>" + str(item.idx) + "</lineNumber>")
        xml_parts.append("        <itemDescription>")
        xml_parts.append(f"          <descriptionText>{_escape(item.item_name or item.item_code)}</descriptionText>")
        xml_parts.append("        </itemDescription>")
        xml_parts.append("        <invoicedQuantity unitOfMeasure=\"C62\">" + str(item.qty) + "</invoicedQuantity>")  # C62 = unitless
        xml_parts.append("        <lineExtensionAmount currencyID=\"EUR\">" + f"{item.net_amount:.2f}" + "</lineExtensionAmount>")
        if item.get("base_rate"):
            xml_parts.append("        <grossPrice>")
            xml_parts.append("          <amount currencyID=\"EUR\">" + f"{item.base_rate:.2f}" + "</amount>")
            xml_parts.append("        </grossPrice>")
        xml_parts.append("      </line>")
    xml_parts.append("    </invoiceLine>")

    xml_parts.append("  </invoice>")
    xml_parts.append("</envelope>")

    return "\n".join(xml_parts)


def attach_eslog_xml(doc, method=None):
    """Hook: Sales Invoice.on_submit — generate e-Slog XML and attach to invoice.
    Also works standalone (called with sales_invoice_name as a string)."""
    # Allow being called both as a doc_events hook (doc=Document) and standalone
    if isinstance(doc, str):
        invoice_name = doc
    elif hasattr(doc, "doctype") and doc.doctype == "Sales Invoice":
        invoice_name = doc.name
    else:
        return

    try:
        xml_content = generate_eslog_xml(invoice_name)
    except Exception as e:
        frappe.log_error(
            title=f"e-Slog XML generation failed for {invoice_name}",
            message=str(e),
        )
        return

    # Save as file attachment
    file_name = f"eSlog_{invoice_name}.xml"
    # Remove old attachment if exists
    existing = frappe.db.exists("File", {
        "attached_to_doctype": "Sales Invoice",
        "attached_to_name": invoice_name,
        "file_name": file_name,
    })
    if existing:
        frappe.delete_doc("File", existing, force=True)

    save_file(
        fname=file_name,
        content=xml_content,
        dt="Sales Invoice",
        dn=invoice_name,
        folder=None,
        is_private=0,
        df=None,
    )
    frappe.db.commit()
    print(f"  -> e-Slog XML attached: {file_name}")


def remove_eslog_xml(doc, method=None):
    """Hook: Sales Invoice.on_trash — remove e-Slog XML attachment."""
    if isinstance(doc, str):
        invoice_name = doc
    elif hasattr(doc, "name"):
        invoice_name = doc.name
    else:
        return
    file_name = f"eSlog_{invoice_name}.xml"
    existing = frappe.db.exists("File", {
        "attached_to_doctype": "Sales Invoice",
        "attached_to_name": invoice_name,
        "file_name": file_name,
    })
    if existing:
        frappe.delete_doc("File", existing, force=True)


@frappe.whitelist()
def get_eslog_xml(sales_invoice_name: str) -> str:
    """RPC: return e-Slog XML for a given Sales Invoice (regenerate on demand)."""
    return generate_eslog_xml(sales_invoice_name)


# ----- helpers -----

def _escape(text) -> str:
    """Escape XML special characters."""
    if text is None:
        return ""
    s = str(text)
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _get_company_address(company_name: str) -> dict:
    """Get primary address dict for a company (via Dynamic Link)."""
    addr_name = frappe.db.get_value("Dynamic Link",
        {"link_doctype": "Company", "link_name": company_name, "parenttype": "Address"},
        "parent")
    if addr_name:
        return frappe.db.get_value("Address", addr_name,
            ["address_line1", "city", "pincode", "country"], as_dict=True) or {}
    return {}


def _get_customer_address(customer_name: str) -> dict:
    """Get primary address dict for a customer (via Dynamic Link)."""
    # Try primary address first
    addr_name = frappe.db.get_value("Customer", customer_name, "customer_primary_address")
    if not addr_name:
        addr_name = frappe.db.get_value("Dynamic Link",
            {"link_doctype": "Customer", "link_name": customer_name, "parenttype": "Address"},
            "parent")
    if addr_name:
        return frappe.db.get_value("Address", addr_name,
            ["address_line1", "city", "pincode", "country"], as_dict=True) or {}
    return {}
