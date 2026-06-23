"""Make DDV-VP and RAČ reports standard."""
import frappe


REPORTS = [
    {
        "name": "DDV-VP Letno Poročilo",
        "ref_doctype": "Sales Invoice",
        "module": "Erpnext Slovenia",
    },
    {
        "name": "RAČ Letni Izkaz",
        "ref_doctype": "GL Entry",
        "module": "Erpnext Slovenia",
    },
]


def main():
    for r in REPORTS:
        name = r["name"]
        if not frappe.db.exists("Report", name):
            print(f">>> Creating Report {name}")
            doc = frappe.new_doc("Report")
            doc.name = name
            doc.report_name = name
            doc.ref_doctype = r["ref_doctype"]
            doc.report_type = "Script Report"
            doc.is_standard = "Yes"
            doc.module = r["module"]
            doc.add_total_row = 1 if "RAČ" not in name else 0
            try:
                doc.insert(ignore_permissions=True)
                frappe.db.commit()
                print(f">>> Created: {name}")
            except Exception as e:
                print(f">>> Failed: {e}")
                frappe.db.rollback()
        else:
            # Update existing
            try:
                doc = frappe.get_doc("Report", name)
                doc.is_standard = "Yes"
                doc.module = r["module"]
                doc.save(ignore_permissions=True)
                frappe.db.commit()
                print(f">>> Updated: {name} (module={doc.module}, is_standard={doc.is_standard})")
            except Exception as e:
                print(f">>> Update failed: {e}")
                frappe.db.rollback()


if __name__ == "__main__":
    main()
