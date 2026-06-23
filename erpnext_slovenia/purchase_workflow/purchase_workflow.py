"""
Slovenian Purchase Order approval workflow.

Implements a multi-step approval process for Purchase Orders:
  Draft → Pending Manager → Pending Finance → Approved → Rejected

This is a common requirement in Slovenian companies where:
1. Department manager approves the request
2. Finance validates budget
3. Purchasing team issues the PO

The workflow is created programmatically (no manual setup needed).
"""
import frappe
from frappe import _


WORKFLOW_NAME = "Slovensko Odobrenje Nakupa"
STATES = [
    # (state, docstatus, allow_edit_role, color)
    # allow_edit_role: which Role can edit a document in this state (empty = no one)
    ("Osnutek",            0, "System Manager",     "gray"),    # Draft
    ("Naknadna Odobritev", 0, "",                   "blue"),    # Pending Manager
    ("Odobritev Finance",  0, "",                   "purple"),  # Pending Finance
    ("Odobreno",           1, "",                   "green"),   # Approved (submitted)
    ("Zavrnjeno",          2, "",                   "red"),     # Rejected (cancelled)
]

TRANSITIONS = [
    # (from_state, to_state, action_name, allowed_roles, allow_self_approve, condition)
    # Using only System Manager + Accounts Manager (which always exist)
    ("Osnutek",            "Naknadna Odobritev", "Pošlji v odobritev", ["System Manager", "Accounts Manager"], 0, None),
    ("Naknadna Odobritev", "Odobritev Finance",  "Odobri (manager)",   ["System Manager", "Accounts Manager"], 0, None),
    ("Naknadna Odobritev", "Osnutek",            "Vrni v osnutek",     ["System Manager"],                       0, None),
    ("Naknadna Odobritev", "Zavrnjeno",          "Zavrni",             ["System Manager", "Accounts Manager"], 0, None),
    ("Odobritev Finance",  "Odobreno",           "Odobri (finance)",   ["System Manager", "Accounts Manager"], 0, None),
    ("Odobritev Finance",  "Naknadna Odobritev", "Vrni managerju",     ["System Manager", "Accounts Manager"], 0, None),
    ("Odobritev Finance",  "Zavrnjeno",          "Zavrni",             ["System Manager", "Accounts Manager"], 0, None),
    ("Odobreno",           "Osnutek",            "Prekliči",           ["System Manager", "Accounts Manager"], 0, None),
]


def create_workflow():
    """Create or update the Slovenian Purchase Order approval workflow."""

    # 1. Create Workflow States
    for state, docstatus, allow_edit_role, color in STATES:
        if not frappe.db.exists("Workflow State", state):
            try:
                ws = frappe.get_doc({
                    "doctype": "Workflow State",
                    "workflow_state_name": state,
                })
                ws.flags.ignore_permissions = True
                ws.insert()
                frappe.db.commit()
                print(f"  -> Workflow State created: {state}")
            except Exception as e:
                print(f"  !! Workflow State {state}: {e}")
                frappe.db.rollback()

    # 2. Create Workflow Actions
    existing_actions = set(frappe.get_all("Workflow Action Master", pluck="name"))
    for _, _, action_name, _, _, _ in TRANSITIONS:
        if action_name not in existing_actions:
            try:
                wa = frappe.get_doc({
                    "doctype": "Workflow Action Master",
                    "workflow_action_name": action_name,
                })
                wa.flags.ignore_permissions = True
                wa.insert()
                frappe.db.commit()
                existing_actions.add(action_name)
                print(f"  -> Workflow Action created: {action_name}")
            except Exception as e:
                print(f"  !! Workflow Action {action_name}: {e}")
                frappe.db.rollback()

    # 3. Delete existing Workflow if any (so we can recreate cleanly)
    if frappe.db.exists("Workflow", WORKFLOW_NAME):
        try:
            frappe.delete_doc("Workflow", WORKFLOW_NAME, force=True)
            frappe.db.commit()
            print(f"  -> Deleted existing workflow '{WORKFLOW_NAME}'")
        except Exception as e:
            print(f"  !! Delete failed: {e}")
            frappe.db.rollback()

    # 4. Create the Workflow document
    wf = frappe.get_doc({
        "doctype": "Workflow",
        "workflow_name": WORKFLOW_NAME,
        "document_type": "Purchase Order",
        "document_state_field": "workflow_state",
        "is_active": 1,
        "send_email_alert": 1,
        "message": "{owner} je poslal Purchase Order {name} v odobritev. Trenutni status: {state}",
    })

    # Add states
    for state, docstatus, allow_edit_role, color in STATES:
        wf.append("states", {
            "state": state,
            "doc_status": str(docstatus),
            "allow_edit": allow_edit_role,  # Role link
            "update_field": "workflow_state",
            "update_value": state,
        })

    # Add transitions
    for from_state, to_state, action_name, allowed_roles, allow_self_approve, condition in TRANSITIONS:
        wf.append("transitions", {
            "state": from_state,
            "action": action_name,
            "next_state": to_state,
            "allowed": ", ".join(allowed_roles),
            "allow_self_approval": allow_self_approve,
            "condition": condition or "",
        })

    try:
        wf.flags.ignore_permissions = True
        wf.insert()
        frappe.db.commit()
        print(f"  -> Workflow created: {WORKFLOW_NAME}")
    except Exception as e:
        print(f"  !! Workflow creation failed: {e}")
        import traceback
        traceback.print_exc()
        frappe.db.rollback()


@frappe.whitelist()
def approve_purchase_order(po_name: str, action: str, comment: str = None) -> dict:
    """RPC: Apply a workflow action to a Purchase Order.

    Args:
        po_name: Purchase Order name
        action: One of: 'Pošlji v odobritev', 'Odobri (manager)', 'Odobri (finance)', 'Zavrni'
        comment: Optional comment for audit trail

    Returns:
        Dict with success, new_state, message
    """
    if not frappe.db.exists("Purchase Order", po_name):
        return {"success": False, "error": _("Naročilo nakupa ne obstaja.")}

    po = frappe.get_doc("Purchase Order", po_name)
    current_state = po.workflow_state or "Osnutek"

    # Find the transition
    transition = None
    for from_state, to_state, action_name, allowed_roles, allow_self_approve, condition in TRANSITIONS:
        if from_state == current_state and action_name == action:
            transition = (from_state, to_state, action_name, allowed_roles)
            break

    if not transition:
        return {
            "success": False,
            "error": _("Akcija '{0}' ni dovoljena iz stanja '{1}'.").format(action, current_state),
            "current_state": current_state,
        }

    # Check permissions
    user_roles = set(frappe.get_roles(frappe.session.user))
    allowed_roles = set(transition[3])
    if not user_roles & allowed_roles and "System Manager" not in user_roles:
        return {
            "success": False,
            "error": _("Nimate dovoljenja za to akcijo. Potrebne vloge: {0}").format(", ".join(allowed_roles)),
        }

    # Apply transition using Frappe's apply_workflow
    try:
        from frappe.model.workflow import apply_workflow
        new_doc = apply_workflow(po, action)

        # Add comment if provided
        if comment:
            from frappe.desk.form.utils import add_comment
            add_comment("Purchase Order", po_name, comment, frappe.session.user)

        frappe.db.commit()

        return {
            "success": True,
            "previous_state": current_state,
            "new_state": new_doc.workflow_state,
            "action": action,
            "message": _("Akcija uspešno izvedena: {0}").format(action),
        }
    except Exception as e:
        frappe.db.rollback()
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def get_workflow_status(po_name: str) -> dict:
    """RPC: Get current workflow state and available actions for a Purchase Order."""
    if not frappe.db.exists("Purchase Order", po_name):
        return {"success": False, "error": _("Naročilo nakupa ne obstaja.")}

    po = frappe.get_doc("Purchase Order", po_name)
    current_state = po.workflow_state or "Osnutek"

    # Get available actions
    available_actions = []
    user_roles = set(frappe.get_roles(frappe.session.user))
    for from_state, to_state, action_name, allowed_roles, _, _ in TRANSITIONS:
        if from_state == current_state:
            can_perform = bool(user_roles & set(allowed_roles)) or "System Manager" in user_roles
            available_actions.append({
                "action": action_name,
                "next_state": to_state,
                "allowed_roles": allowed_roles,
                "can_perform": can_perform,
            })

    return {
        "success": True,
        "po_name": po_name,
        "current_state": current_state,
        "docstatus": po.docstatus,
        "available_actions": available_actions,
    }


def main():
    """Create the Slovenian Purchase Order approval workflow."""
    print(f">>> Creating Slovenian Purchase Order approval workflow...")
    create_workflow()
    print(f">>> Done")


if __name__ == "__main__":
    main()
