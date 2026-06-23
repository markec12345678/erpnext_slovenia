"""Make DDV Obračun report standard (uses module path instead of safe_exec)."""
import frappe


def main():
    name = "DDV Obračun"
    if not frappe.db.exists("Report", name):
        print(f">>> Report {name} does not exist")
        return

    # Update is_standard to Yes and module to a known one
    # Frappe will then use the Python module path: <app>.report.<scrubbed_name>.<scrubbed_name>.execute
    # Our module path is: erpnext_slovenia.report.ddv_obracun.ddv_obracun.execute
    # For this to work, the report's `module` must be `Erpnext Slovenia` (matching the app's title)
    # But that module isn't registered. So we use `Core` and manually set the python module path.
    # Actually, Frappe uses get_report_module_dotted_path(module, name) which returns:
    #   f"{app_name_for_module}.report.{scrub(name)}.{scrub(name)}"
    # For module "Core", app is "frappe", so it would look for frappe.report.ddv_obracun.ddv_obracun
    # That's wrong.
    # Workaround: register the module "Erpnext Slovenia" first, OR move the report into the erpnext_slovenia app properly.

    # Approach: Move the report module path to where Frappe expects it.
    # Frappe's `get_report_module_dotted_path`:
    #   module = self.module  # "Erpnext Slovenia"
    #   app = frappe.get_module_from_path(module)  # returns "erpnext_slovenia"
    #   return f"{app}.report.{scrub(self.name)}.{scrub(self.name)}"
    # So we need: module = "Erpnext Slovenia" → app = "erpnext_slovenia"
    # And our report file is at: erpnext_slovenia/report/ddv_obracun/ddv_obracun.py ✓ (already correct)

    # The issue: Module Def "Erpnext Slovenia" doesn't exist. We need to create it.

    # Step 1: Create Module Def "Erpnext Slovenia"
    if not frappe.db.exists("Module Def", "Erpnext Slovenia"):
        try:
            md = frappe.get_doc({
                "doctype": "Module Def",
                "module_name": "Erpnext Slovenia",
                "app_name": "erpnext_slovenia",
                "custom": 1,
            })
            md.flags.ignore_permissions = True
            md.insert()
            frappe.db.commit()
            print(f">>> Module Def created: Erpnext Slovenia")
        except Exception as e:
            print(f">>> Module Def failed: {e}")
            frappe.db.rollback()
    else:
        print(f">>> Module Def 'Erpnext Slovenia' already exists")

    # Step 2: Update the Report to use this module + is_standard=Yes
    try:
        report = frappe.get_doc("Report", name)
        report.module = "Erpnext Slovenia"
        report.is_standard = "Yes"
        report.save(ignore_permissions=True)
        frappe.db.commit()
        print(f">>> Report updated: module={report.module}, is_standard={report.is_standard}")
    except Exception as e:
        print(f">>> Report update failed: {e}")
        frappe.db.rollback()


if __name__ == "__main__":
    main()
