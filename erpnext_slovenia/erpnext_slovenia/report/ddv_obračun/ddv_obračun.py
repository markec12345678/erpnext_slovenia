# Copyright (c) 2026, Z.ai
# License: MIT

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import getdate, flt


def execute(filters: dict | None = None):
    """Main entry point for the DDV Obračun script report.

    Returns a tuple of (columns, data, message, chart, report_summary).
    """
    if not filters:
        filters = {}

    company = filters.get("company")
    from_date = filters.get("from_date")
    to_date = filters.get("to_date")

    if not (company and from_date and to_date):
        return [], [], _("Prosimo, izberite podjetje in datumsko obdobje.")

    columns = [
        {"fieldname": "section", "label": _("Sekcija"), "fieldtype": "Data", "width": 220},
        {"fieldname": "rate", "label": _("Stopnja DDV (%)"), "fieldtype": "Float", "width": 110},
        {"fieldname": "taxable_amount", "label": _("Osnova (EUR)"), "fieldtype": "Currency",
         "options": "EUR", "width": 140},
        {"fieldname": "tax_amount", "label": _("DDV (EUR)"), "fieldtype": "Currency",
         "options": "EUR", "width": 140},
        {"fieldname": "total_amount", "label": _("Skupaj (EUR)"), "fieldtype": "Currency",
         "options": "EUR", "width": 140},
    ]

    data = []

    # === Izhodni DDV (Sales) ===
    sales_data = _aggregate_taxes(
        doctype="Sales Invoice",
        tax_doctype="Sales Taxes and Charges",
        company=company,
        from_date=from_date,
        to_date=to_date,
    )

    if sales_data:
        # Section header row
        data.append({
            "section": "IZHODNI DDV (Prodaja)",
            "rate": None,
            "taxable_amount": None,
            "tax_amount": None,
            "total_amount": None,
        })
        out_base_total = 0.0
        out_tax_total = 0.0
        for row in sales_data:
            data.append({
                "section": f"  Prodaja {row['rate']:.1f}%",
                "rate": row["rate"],
                "taxable_amount": row["taxable_amount"],
                "tax_amount": row["tax_amount"],
                "total_amount": row["taxable_amount"] + row["tax_amount"],
            })
            out_base_total += row["taxable_amount"]
            out_tax_total += row["tax_amount"]
        # Subtotal
        data.append({
            "section": "  SKUPAJ IZHODNI DDV",
            "rate": None,
            "taxable_amount": out_base_total,
            "tax_amount": out_tax_total,
            "total_amount": out_base_total + out_tax_total,
        })

    # === Vhodni DDV (Purchase) ===
    purchase_data = _aggregate_taxes(
        doctype="Purchase Invoice",
        tax_doctype="Purchase Taxes and Charges",
        company=company,
        from_date=from_date,
        to_date=to_date,
    )

    if purchase_data:
        data.append({
            "section": "VHODNI DDV (Nakup)",
            "rate": None,
            "taxable_amount": None,
            "tax_amount": None,
            "total_amount": None,
        })
        in_base_total = 0.0
        in_tax_total = 0.0
        for row in purchase_data:
            data.append({
                "section": f"  Nakup {row['rate']:.1f}%",
                "rate": row["rate"],
                "taxable_amount": row["taxable_amount"],
                "tax_amount": row["tax_amount"],
                "total_amount": row["taxable_amount"] + row["tax_amount"],
            })
            in_base_total += row["taxable_amount"]
            in_tax_total += row["tax_amount"]
        data.append({
            "section": "  SKUPAJ VHODNI DDV",
            "rate": None,
            "taxable_amount": in_base_total,
            "tax_amount": in_tax_total,
            "total_amount": in_base_total + in_tax_total,
        })

    # === Razlika (DDV za plačilo / dobropis) ===
    if sales_data or purchase_data:
        out_tax_total = out_tax_total if sales_data else 0.0
        in_tax_total = in_tax_total if purchase_data else 0.0
        diff = out_tax_total - in_tax_total
        data.append({
            "section": "DDV ZA PLAČILO / DOBROPIS",
            "rate": None,
            "taxable_amount": None,
            "tax_amount": diff,
            "total_amount": None,
        })

    # Report summary cards at top of report
    report_summary = []
    if sales_data:
        report_summary.append({
            "value": f"€ {out_tax_total:,.2f}",
            "indicator": "Blue",
            "label": _("Izhodni DDV"),
            "datatype": "Data",
        })
    if purchase_data:
        report_summary.append({
            "value": f"€ {in_tax_total:,.2f}",
            "indicator": "Green",
            "label": _("Vhodni DDV"),
            "datatype": "Data",
        })
    if sales_data or purchase_data:
        diff_label = _("DDV za plačilo") if diff >= 0 else _("DDV dobropis")
        diff_color = "Red" if diff >= 0 else "Green"
        report_summary.append({
            "value": f"€ {diff:,.2f}",
            "indicator": diff_color,
            "label": diff_label,
            "datatype": "Data",
        })

    chart = {
        "data": {
            "labels": [r["rate"] for r in (sales_data + purchase_data)],
            "datasets": [
                {"name": _("Izhodni"), "values": [r["tax_amount"] for r in sales_data]},
                {"name": _("Vhodni"), "values": [r["tax_amount"] for r in purchase_data]},
            ],
        },
        "type": "bar",
        "barOptions": {"stacked": False},
        "colors": ["#5e64ff", "#28a745"],
    }

    return columns, data, None, chart, report_summary


def _aggregate_taxes(doctype: str, tax_doctype: str, company: str, from_date: str, to_date: str) -> list[dict]:
    """Aggregate tax rows (rate, base, tax amount) from submitted invoices in the date range.

    Note: For included_in_print_rate taxes, the taxable amount is computed as
          (grand_total - tax_amount), which matches how Slovenian invoices report
          VAT (DDV is included in the unit price).
    """
    # Get all submitted invoices in the period
    invoice_names = frappe.db.get_all(
        doctype,
        filters={
            "company": company,
            "docstatus": 1,
            "posting_date": ["between", [from_date, to_date]],
        },
        pluck="name",
    )

    if not invoice_names:
        return []

    # Aggregate taxes by rate
    by_rate: dict[float, dict] = {}

    # Use a chunked IN clause to avoid SQLite parameter limits (999)
    chunk_size = 500
    for i in range(0, len(invoice_names), chunk_size):
        chunk = invoice_names[i:i + chunk_size]
        taxes = frappe.db.get_all(
            tax_doctype,
            filters={
                "parent": ["in", chunk],
                "parenttype": doctype,
                "docstatus": 1,
                "charge_type": "On Net Total",
            },
            fields=["rate", "tax_amount", "base_tax_amount", "total", "base_total",
                    "net_amount", "base_net_amount", "included_in_print_rate"],
        )

        for t in taxes:
            rate = flt(t.rate, 3)
            if rate <= 0:
                continue
            key = round(rate, 3)
            if key not in by_rate:
                by_rate[key] = {
                    "rate": rate,
                    "taxable_amount": 0.0,
                    "tax_amount": 0.0,
                }
            tax_amount = flt(t.tax_amount)
            base_tax_amount = flt(t.base_tax_amount)
            net_amount = flt(t.get("net_amount") or t.get("base_net_amount") or 0)
            total = flt(t.get("total") or t.get("base_total") or 0)

            # Taxable base (osnova za DDV):
            # - Prefer `net_amount` (the net total before tax, set by Frappe when tax is "On Net Total")
            # - Fallback for included_in_print_rate: total - tax_amount
            # - Fallback otherwise: base_tax_amount (= tax_amount, NOT the base) → recompute
            if net_amount > 0:
                taxable = net_amount
            elif t.included_in_print_rate and total > 0:
                taxable = total - tax_amount
            elif rate > 0:
                taxable = tax_amount / (rate / 100.0)
            else:
                taxable = 0

            by_rate[key]["taxable_amount"] += taxable
            by_rate[key]["tax_amount"] += tax_amount

    return sorted(by_rate.values(), key=lambda r: r["rate"])
