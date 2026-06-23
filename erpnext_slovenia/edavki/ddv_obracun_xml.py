"""
eDavki XML generator for Slovenian VAT return (DDV-Obr) submission to FURS.

The XML format follows the official eDavki schema used by FURS
(Financna uprava Republike Slovenije) for electronic tax submissions.

This generates the body of an eDavki XML envelope for the DDV-Obr form,
which can then be uploaded to https://edavki.fu.gov.si/

Schema reference:
  - eDavkiXML v1.5
  - form: DDV-Obr
  - namespace: http://edavki.durs.si/edavki-doc/v1.5
"""
import datetime
import frappe
from frappe import _
from frappe.utils import getdate, flt


# eDavki namespaces
EDAVKI_NS = "http://edavki.durs.si/edavki-doc/v1.5"


def generate_ddv_obracun_xml(
    company: str,
    from_date: str,
    to_date: str,
    period_type: str = "month",  # "month" | "quarter"
) -> str:
    """Generate eDavki XML for DDV-Obr VAT return.

    Args:
        company: Company name
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD)
        period_type: 'month' or 'quarter' (determines the period label)

    Returns:
        A string with the eDavki XML document.
    """
    from erpnext_slovenia.erpnext_slovenia.report.ddv_obračun.ddv_obračun import _aggregate_taxes

    # Get company info
    company_doc = frappe.get_doc("Company", company)
    tax_id = (company_doc.tax_id or "").lstrip("SI").lstrip("si")
    if not tax_id:
        frappe.throw(_("Podjetje mora imeti nastavljeno davčno številko (tax_id)."))

    # Aggregate sales and purchase taxes
    sales = _aggregate_taxes(
        doctype="Sales Invoice",
        tax_doctype="Sales Taxes and Charges",
        company=company,
        from_date=from_date,
        to_date=to_date,
    )
    purchases = _aggregate_taxes(
        doctype="Purchase Invoice",
        tax_doctype="Purchase Taxes and Charges",
        company=company,
        from_date=from_date,
        to_date=to_date,
    )

    # Separate by rate: Slovenia uses 22% (splošna) and 8.5% (nižja) and 5% (posebej nižja)
    def find_by_rate(rows, rate):
        for r in rows:
            if abs(r["rate"] - rate) < 0.01:
                return r
        return {"rate": rate, "taxable_amount": 0.0, "tax_amount": 0.0}

    s22 = find_by_rate(sales, 22.0)
    s85 = find_by_rate(sales, 8.5)
    s5 = find_by_rate(sales, 5.0)
    s0 = find_by_rate(sales, 0.0)

    p22 = find_by_rate(purchases, 22.0)
    p85 = find_by_rate(purchases, 8.5)
    p5 = find_by_rate(purchases, 5.0)
    p0 = find_by_rate(purchases, 0.0)

    # Outgoing DDV (izhodni)
    out_22_base = s22["taxable_amount"]
    out_22_tax = s22["tax_amount"]
    out_85_base = s85["taxable_amount"]
    out_85_tax = s85["tax_amount"]
    out_5_base = s5["taxable_amount"]
    out_5_tax = s5["tax_amount"]
    out_0_base = s0["taxable_amount"]

    # Incoming DDV (vhodni) - priznano do 100%
    in_22_base = p22["taxable_amount"]
    in_22_tax = p22["tax_amount"]
    in_85_base = p85["taxable_amount"]
    in_85_tax = p85["tax_amount"]
    in_5_base = p5["taxable_amount"]
    in_5_tax = p5["tax_amount"]
    in_0_base = p0["taxable_amount"]

    # Totalizirana razlika
    total_out_tax = out_22_tax + out_85_tax + out_5_tax
    total_in_tax = in_22_tax + in_85_tax + in_5_tax
    ddv_to_pay = total_out_tax - total_in_tax

    # Period label: "2026-06" for month, "2026-K2" for quarter
    fd = getdate(from_date)
    if period_type == "quarter":
        q = (fd.month - 1) // 3 + 1
        period_label = f"{fd.year}-K{q}"
    else:
        period_label = f"{fd.year}-{fd.month:02d}"

    # Build XML
    parts = ['<?xml version="1.0" encoding="UTF-8"?>']
    parts.append(
        f'<edp:EDavki xmlns:edp="{EDAVKI_NS}" '
        f'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
    )

    # Header
    parts.append("  <edp:Header>")
    parts.append(f"    <edp:taxNumber>{_x(tax_id)}</edp:taxNumber>")
    parts.append(f"    <edp:DocumentType>DDV-Obr</edp:DocumentType>")
    parts.append(f"    <edp:DocumentName>DDV-Obr {period_label}</edp:DocumentName>")
    parts.append(f"    <edp:CreationDate>{datetime.datetime.now().strftime('%Y-%m-%d')}</edp:CreationDate>")
    parts.append(f"    <edp:Language>sl</edp:Language>")
    parts.append("  </edp:Header>")

    # Body - DDV-Obr form
    parts.append("  <edp:Body>")
    parts.append("    <edp:Content>")
    parts.append("      <edp:DDVObr>")
    parts.append(f"        <edp:Obdobje>{period_label}</edp:Obdobje>")
    parts.append(f"        <edp:ObdobjeDo>{to_date}</edp:ObdobjeDo>")

    # Section I: Izhodni DDV
    parts.append("        <edp:IzhodniDDV>")
    # 22% splošna stopnja
    parts.append("          <edp:SplosnaStopnja>")
    parts.append(f"            <edp:Osnova22>{out_22_base:.2f}</edp:Osnova22>")
    parts.append(f"            <edp:DDV22>{out_22_tax:.2f}</edp:DDV22>")
    parts.append("          </edp:SplosnaStopnja>")
    # 8.5% nižja stopnja
    parts.append("          <edp:NizjaStopnja>")
    parts.append(f"            <edp:Osnova85>{out_85_base:.2f}</edp:Osnova85>")
    parts.append(f"            <edp:DDV85>{out_85_tax:.2f}</edp:DDV85>")
    parts.append("          </edp:NizjaStopnja>")
    # 5% posebej nižja stopnja (special low rate, optional)
    parts.append("          <edp:PosebjNizjaStopnja>")
    parts.append(f"            <edp:Osnova5>{out_5_base:.2f}</edp:Osnova5>")
    parts.append(f"            <edp:DDV5>{out_5_tax:.2f}</edp:DDV5>")
    parts.append("          </edp:PosebjNizjaStopnja>")
    # 0% (export etc.)
    parts.append("          <edp:Oprostitev>")
    parts.append(f"            <edp:Osnova0>{out_0_base:.2f}</edp:Osnova0>")
    parts.append("          </edp:Oprostitev>")
    parts.append("        </edp:IzhodniDDV>")

    # Section II: Vhodni DDV
    parts.append("        <edp:VhodniDDV>")
    # priznano do 100%
    parts.append("          <edp:PriznanDo100>")
    parts.append(f"            <edp:Osnova22>{in_22_base:.2f}</edp:Osnova22>")
    parts.append(f"            <edp:DDV22>{in_22_tax:.2f}</edp:DDV22>")
    parts.append(f"            <edp:Osnova85>{in_85_base:.2f}</edp:Osnova85>")
    parts.append(f"            <edp:DDV85>{in_85_tax:.2f}</edp:DDV85>")
    parts.append(f"            <edp:Osnova5>{in_5_base:.2f}</edp:Osnova5>")
    parts.append(f"            <edp:DDV5>{in_5_tax:.2f}</edp:DDV5>")
    parts.append("          </edp:PriznanDo100>")
    parts.append("        </edp:VhodniDDV>")

    # Section III: Razlika
    parts.append("        <edp:PlaciloDDV>")
    parts.append(f"          <edp:DDVzaPlacilo>{ddv_to_pay:.2f}</edp:DDVzaPlacilo>")
    parts.append("        </edp:PlaciloDDV>")

    parts.append("      </edp:DDVObr>")
    parts.append("    </edp:Content>")
    parts.append("  </edp:Body>")

    parts.append("</edp:EDavki>")

    return "\n".join(parts)


@frappe.whitelist()
def get_ddv_obracun_xml(company: str, from_date: str, to_date: str, period_type: str = "month") -> str:
    """RPC: generate eDavki XML for a given period."""
    return generate_ddv_obracun_xml(company, from_date, to_date, period_type)


@frappe.whitelist()
def download_ddv_obracun_xml(company: str, from_date: str, to_date: str, period_type: str = "month"):
    """RPC: stream XML as a downloadable file."""
    xml = generate_ddv_obracun_xml(company, from_date, to_date, period_type)
    fd = getdate(from_date)
    if period_type == "quarter":
        q = (fd.month - 1) // 3 + 1
        period = f"{fd.year}-K{q}"
    else:
        period = f"{fd.year}-{fd.month:02d}"

    frappe.local.response["filename"] = f"DDV-Obr_{period}.xml"
    frappe.local.response["filecontent"] = xml
    frappe.local.response["type"] = "download"


def _x(text) -> str:
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
