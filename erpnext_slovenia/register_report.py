"""Register DDV Obračun Report manually (bypass sync)."""
import frappe
import os
import json


def main():
    report_name = "DDV Obračun"
    if frappe.db.exists("Report", report_name):
        print(f">>> Report already exists")
        # Update
        doc = frappe.get_doc("Report", report_name)
    else:
        doc = frappe.new_doc("Report")
        doc.name = report_name
        doc.report_name = report_name

    # Load from JSON file
    json_path = "/home/z/frappe-bench/apps/erpnext_slovenia/erpnext_slovenia/report/ddv_obracun/ddv_obracun.json"
    with open(json_path, "r") as f:
        data = json.load(f)

    doc.report_name = "DDV Obračun"
    doc.ref_doctype = "Sales Invoice"
    doc.report_type = "Script Report"
    doc.is_standard = "No"
    doc.disabled = 0
    doc.add_total_row = 1
    # Module - skip if not registered
    try:
        doc.module = "Core"
    except Exception:
        pass

    # Roles
    doc.roles = []
    for role in ["Accounts Manager", "Accounts User", "Auditor"]:
        if frappe.db.exists("Role", role):
            doc.append("roles", {"role": role})

    # Columns and filters - we'll just store the report and let the .py file be picked up
    # Frappe uses the .py file in report/ folder for the script
    try:
        doc.insert(ignore_permissions=True)
        print(f">>> Report created: {doc.name}")
    except Exception as e:
        print(f">>> Insert failed: {e}")
        frappe.db.rollback()
        # Try with save instead
        try:
            doc.save(ignore_permissions=True)
            print(f">>> Report saved: {doc.name}")
        except Exception as e2:
            print(f">>> Save also failed: {e2}")
            frappe.db.rollback()
            return

    frappe.db.commit()
    print(f">>> Done. Report: {frappe.db.get_value('Report', report_name, 'name')}")


if __name__ == "__main__":
    main()
