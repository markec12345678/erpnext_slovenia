"""
DDV-VP: Letno poročilo o transakcijah z zavezanci za DDV.

To poročilo je obvezno letno poročilo, ki se oddaja na FURS in vsebuje:
- Seznam strank (kupec) z davčnimi številkami
- Skupni znesek dobav (računov) na leto
- Znesek DDV-ja po stopnjah (22%, 8.5%, 5%)

DDV-VP je predpisan s strani FURS za zagotavljanje preglednosti transakcij
med zavezanci za DDV (cross-checking davčnih prijav).
"""
import frappe
from frappe import _
from frappe.utils import flt


def execute(filters: dict | None = None):
    if not filters:
        filters = {}

    company = filters.get("company")
    year = filters.get("year")
    if not year:
        year = "2026"

    if not company:
        return [], [], _("Prosimo, izberite podjetje.")

    # Determine date range
    from_date = f"{year}-01-01"
    to_date = f"{year}-12-31"

    columns = [
        {"fieldname": "customer", "label": _("Stranka"), "fieldtype": "Link",
         "options": "Customer", "width": 200},
        {"fieldname": "customer_name", "label": _("Ime stranke"), "fieldtype": "Data", "width": 200},
        {"fieldname": "tax_id", "label": _("Davčna št."), "fieldtype": "Data", "width": 120},
        {"fieldname": "country", "label": _("Država"), "fieldtype": "Data", "width": 100},
        {"fieldname": "invoice_count", "label": _("Št. računov"), "fieldtype": "Int", "width": 90},
        {"fieldname": "base_22", "label": _("Osnova 22% (EUR)"), "fieldtype": "Currency",
         "options": "EUR", "width": 130},
        {"fieldname": "tax_22", "label": _("DDV 22% (EUR)"), "fieldtype": "Currency",
         "options": "EUR", "width": 120},
        {"fieldname": "base_85", "label": _("Osnova 8.5% (EUR)"), "fieldtype": "Currency",
         "options": "EUR", "width": 130},
        {"fieldname": "tax_85", "label": _("DDV 8.5% (EUR)"), "fieldtype": "Currency",
         "options": "EUR", "width": 120},
        {"fieldname": "base_5", "label": _("Osnova 5% (EUR)"), "fieldtype": "Currency",
         "options": "EUR", "width": 130},
        {"fieldname": "tax_5", "label": _("DDV 5% (EUR)"), "fieldtype": "Currency",
         "options": "EUR", "width": 120},
        {"fieldname": "base_0", "label": _("Osnova 0% (EUR)"), "fieldtype": "Currency",
         "options": "EUR", "width": 120},
        {"fieldname": "total", "label": _("Skupaj z DDV (EUR)"), "fieldtype": "Currency",
         "options": "EUR", "width": 140},
    ]

    # Get all submitted Sales Invoices in the year
    invoices = frappe.db.get_all("Sales Invoice",
        filters={
            "company": company,
            "docstatus": 1,
            "posting_date": ["between", [from_date, to_date]],
        },
        fields=["name", "customer", "customer_name", "grand_total", "net_total"])

    if not invoices:
        return columns, [], _("Ni najdenih prodajnih faktur v izbranem obdobju.")

    # Aggregate by customer
    customer_data: dict[str, dict] = {}

    # Get taxes for each invoice in chunks
    chunk_size = 500
    invoice_names = [inv["name"] for inv in invoices]

    # Build customer info dict first
    customer_info = {}
    for inv in invoices:
        cust = inv["customer"]
        if cust not in customer_info:
            # Fetch customer tax_id and country
            ci = frappe.db.get_value("Customer", cust,
                ["tax_id", "custom_si_tax_id", "customer_name", "territory"], as_dict=True) or {}
            customer_info[cust] = {
                "tax_id": ci.get("tax_id") or ci.get("custom_si_tax_id") or "",
                "customer_name": ci.get("customer_name") or cust,
                "country": "Slovenia",  # Default; could fetch from address
            }
            # Try to get country from address
            addr_name = frappe.db.get_value("Customer", cust, "customer_primary_address")
            if addr_name:
                country = frappe.db.get_value("Address", addr_name, "country")
                if country:
                    customer_info[cust]["country"] = country

        if cust not in customer_data:
            customer_data[cust] = {
                "customer": cust,
                "customer_name": customer_info[cust]["customer_name"],
                "tax_id": customer_info[cust]["tax_id"],
                "country": customer_info[cust]["country"],
                "invoice_count": 0,
                "base_22": 0.0, "tax_22": 0.0,
                "base_85": 0.0, "tax_85": 0.0,
                "base_5": 0.0, "tax_5": 0.0,
                "base_0": 0.0,
                "total": 0.0,
            }

    # Count invoices per customer
    for inv in invoices:
        customer_data[inv["customer"]]["invoice_count"] += 1
        customer_data[inv["customer"]]["total"] += flt(inv["grand_total"])

    # Get taxes per invoice
    for i in range(0, len(invoice_names), chunk_size):
        chunk = invoice_names[i:i + chunk_size]
        taxes = frappe.db.get_all("Sales Taxes and Charges",
            filters={
                "parent": ["in", chunk],
                "parenttype": "Sales Invoice",
                "docstatus": 1,
                "charge_type": "On Net Total",
            },
            fields=["parent", "rate", "tax_amount", "net_amount", "included_in_print_rate"])

        # Map invoice → customer
        inv_to_cust = {inv["name"]: inv["customer"] for inv in invoices}

        for t in taxes:
            cust = inv_to_cust.get(t["parent"])
            if not cust:
                continue
            rate = flt(t["rate"], 3)
            tax_amount = flt(t["tax_amount"])
            net_amount = flt(t.get("net_amount") or 0)

            if abs(rate - 22.0) < 0.01:
                customer_data[cust]["base_22"] += net_amount
                customer_data[cust]["tax_22"] += tax_amount
            elif abs(rate - 8.5) < 0.01:
                customer_data[cust]["base_85"] += net_amount
                customer_data[cust]["tax_85"] += tax_amount
            elif abs(rate - 5.0) < 0.01:
                customer_data[cust]["base_5"] += net_amount
                customer_data[cust]["tax_5"] += tax_amount
            elif rate == 0:
                # 0% rate - add to base_0 only if there's net_amount
                customer_data[cust]["base_0"] += net_amount

    # Convert to list, sorted by total descending
    data = sorted(customer_data.values(), key=lambda r: r["total"], reverse=True)

    # Build summary cards
    total_invoices = sum(d["invoice_count"] for d in data)
    total_value = sum(d["total"] for d in data)
    total_customers = len(data)

    report_summary = [
        {"value": str(total_customers), "indicator": "Blue", "label": _("Število strank"), "datatype": "Int"},
        {"value": str(total_invoices), "indicator": "Green", "label": _("Skupno št. računov"), "datatype": "Int"},
        {"value": f"€ {total_value:,.2f}", "indicator": "Gray", "label": _("Skupna vrednost"), "datatype": "Data"},
    ]

    chart = {
        "data": {
            "labels": [d["customer_name"][:20] for d in data[:10]],
            "datasets": [{"name": _("Znesek z DDV"), "values": [d["total"] for d in data[:10]]}],
        },
        "type": "bar",
        "colors": ["#5e64ff"],
    }

    return columns, data, None, chart, report_summary
