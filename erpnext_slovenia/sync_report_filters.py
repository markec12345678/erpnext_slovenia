"""Force-sync the DDV Obračun report filters and columns."""
import frappe
import json


def main():
    report_name = "DDV Obračun"
    report = frappe.get_doc("Report", report_name)

    # Set filters and columns directly
    report.set("filters", [
        {"fieldname": "company", "label": "Podjetje", "fieldtype": "Link", "options": "Company", "reqd": 1, "default": "Moje Podjetje d.o.o."},
        {"fieldname": "from_date", "label": "Od datuma", "fieldtype": "Date", "reqd": 1, "default": "2026-01-01"},
        {"fieldname": "to_date", "label": "Do datuma", "fieldtype": "Date", "reqd": 1, "default": "2026-12-31"},
    ])
    report.set("columns", [
        {"fieldname": "section", "label": "Sekcija", "fieldtype": "Data", "width": 200},
        {"fieldname": "rate", "label": "Stopnja DDV (%)", "fieldtype": "Float", "width": 100},
        {"fieldname": "taxable_amount", "label": "Osnova (EUR)", "fieldtype": "Currency", "width": 130, "options": "EUR"},
        {"fieldname": "tax_amount", "label": "DDV (EUR)", "fieldtype": "Currency", "width": 130, "options": "EUR"},
        {"fieldname": "total_amount", "label": "Skupaj (EUR)", "fieldtype": "Currency", "width": 130, "options": "EUR"},
    ])

    report.save(ignore_permissions=True)
    frappe.db.commit()
    print(f">>> Report filters and columns saved")

    # Verify
    rpt = frappe.get_doc("Report", report_name)
    print(f">>> Filters: {len(rpt.filters)}")
    for f in rpt.filters:
        print(f"  - {f.fieldname}: {f.label} ({f.fieldtype})")
    print(f">>> Columns: {len(rpt.columns)}")
    for c in rpt.columns:
        print(f"  - {c.fieldname}: {c.label} ({c.fieldtype})")


if __name__ == "__main__":
    main()
