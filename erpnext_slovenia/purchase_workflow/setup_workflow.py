"""Direct creation of workflow states (bypassing the complex setup)."""
import frappe


def main():
    states = [
        ("Osnutek", 0),
        ("Naknadna Odobritev", 0),
        ("Odobritev Finance", 0),
        ("Odobreno", 1),
        ("Zavrnjeno", 2),
    ]
    for state, docstatus in states:
        if not frappe.db.exists("Workflow State", state):
            try:
                ws = frappe.get_doc({
                    "doctype": "Workflow State",
                    "workflow_state_name": state,
                })
                ws.flags.ignore_permissions = True
                ws.insert()
                frappe.db.commit()
                print(f"  -> Created: {state}")
            except Exception as e:
                print(f"  !! Failed {state}: {e}")
                frappe.db.rollback()
        else:
            print(f"  -> Exists: {state}")

    # Now create the workflow
    from erpnext_slovenia.purchase_workflow.purchase_workflow import create_workflow
    create_workflow()


if __name__ == "__main__":
    main()
