"""Create FURS Submission Log doctype."""
import frappe


DOCTYPE_DEF = {
    "doctype": "DocType",
    "name": "FURS Submission Log",
    "module": "Core",
    "custom": 0,
    "is_submittable": 0,
    "istable": 0,
    "issingle": 0,
    "track_changes": 1,
    "track_views": 0,
    "allow_rename": 1,
    "autoname": "FURS-SUB-.YYYY.-.#####",
    "naming_rule": "Expression",
    "title_field": "document_id",
    "search_fields": "company,document_type,from_date,to_date,status",
    "fields": [
        {"fieldname": "company", "label": "Podjetje", "fieldtype": "Link", "options": "Company", "reqd": 1, "in_list_view": 1},
        {"fieldname": "document_type", "label": "Tip dokumenta", "fieldtype": "Select", "options": "DDV-Obr\nDDPO\nDOF", "reqd": 1, "default": "DDV-Obr", "in_list_view": 1},
        {"fieldname": "document_id", "label": "ID dokumenta", "fieldtype": "Data", "reqd": 1, "in_list_view": 1},
        {"fieldname": "from_date", "label": "Od datuma", "fieldtype": "Date", "reqd": 1, "in_list_view": 1},
        {"fieldname": "to_date", "label": "Do datuma", "fieldtype": "Date", "reqd": 1, "in_list_view": 1},
        {"fieldname": "period_type", "label": "Tip obdobja", "fieldtype": "Select", "options": "month\nquarter\nyear", "default": "month"},
        {"fieldname": "submitted_at", "label": "Datum oddaje", "fieldtype": "Datetime", "in_list_view": 1},
        {"fieldname": "status", "label": "Status", "fieldtype": "Select", "options": "Submitted\nFailed\nPending\nAcknowledged", "default": "Pending", "reqd": 1, "in_list_view": 1},
        {"fieldname": "http_status", "label": "HTTP status", "fieldtype": "Int"},
        {"fieldname": "xml_content_section", "label": "XML vsebina", "fieldtype": "Section Break"},
        {"fieldname": "xml_content", "label": "eDavki XML", "fieldtype": "Code", "options": "XML"},
        {"fieldname": "soap_envelope", "label": "SOAP ovojnica", "fieldtype": "Code", "options": "XML"},
        {"fieldname": "response_section", "label": "Odgovor FURS", "fieldtype": "Section Break"},
        {"fieldname": "furs_response", "label": "FURS odgovor", "fieldtype": "Code", "options": "XML"},
        {"fieldname": "error_message", "label": "Napaka", "fieldtype": "Small Text"},
    ],
    "permissions": [
        {"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "report": 1, "export": 1, "print": 1, "email": 1, "share": 1},
        {"role": "Accounts Manager", "read": 1, "write": 1, "create": 1, "delete": 0, "report": 1, "export": 1, "print": 1, "email": 1, "share": 1},
        {"role": "Accounts User", "read": 1, "write": 0, "create": 0, "delete": 0, "report": 1, "export": 0, "print": 1, "email": 1},
    ],
}


def main():
    name = "FURS Submission Log"
    if frappe.db.exists("DocType", name):
        print(f">>> DocType '{name}' already exists")
        return
    try:
        doc = frappe.get_doc(DOCTYPE_DEF)
        doc.flags.ignore_permissions = True
        doc.insert()
        frappe.db.commit()
        print(f">>> DocType created: {name}")
    except Exception as e:
        print(f">>> Failed: {e}")
        frappe.db.rollback()


if __name__ == "__main__":
    main()
