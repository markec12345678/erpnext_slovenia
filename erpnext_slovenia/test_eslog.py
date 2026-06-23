"""Manually trigger e-Slog XML attachment."""
import frappe
from erpnext_slovenia.einvoice.einvoice import generate_eslog_xml, attach_eslog_xml
from frappe.utils.file_manager import save_file


def main():
    inv = "ACC-SINV-2026-00001"
    print(f">>> Generating e-Slog XML for {inv}")

    try:
        xml = generate_eslog_xml(inv)
        print(f">>> Generated {len(xml)} bytes of XML")
        print(">>> Preview (first 1500 chars):")
        print(xml[:1500])
        print("...")

        # Save directly
        file_name = f"eSlog_{inv}.xml"
        # Remove old
        existing = frappe.db.exists("File", {
            "attached_to_doctype": "Sales Invoice",
            "attached_to_name": inv,
            "file_name": file_name,
        })
        if existing:
            frappe.delete_doc("File", existing, force=True)

        f = save_file(
            fname=file_name,
            content=xml,
            dt="Sales Invoice",
            dn=inv,
            folder=None,
            is_private=0,
            df=None,
        )
        frappe.db.commit()
        print(f">>> File saved: {f.name}, URL: {f.file_url}, size: {f.file_size}")
    except Exception as e:
        import traceback
        print(f">>> ERROR: {e}")
        traceback.print_exc()

    # List files
    print("\n>>> All files attached to invoice:")
    files = frappe.get_all("File",
        filters={
            "attached_to_doctype": "Sales Invoice",
            "attached_to_name": inv,
        },
        fields=["name", "file_name", "file_size", "file_url"])
    for f in files:
        print(f"  -> {f}")
