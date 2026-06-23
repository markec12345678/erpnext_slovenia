"""Add company address for Moje Podjetje d.o.o."""
import frappe


def main():
    company = "Moje Podjetje d.o.o."

    # Check if address already exists via Dynamic Link
    addr_name = frappe.db.get_value("Dynamic Link",
        {"link_doctype": "Company", "link_name": company, "parenttype": "Address"},
        "parent")

    if addr_name:
        print(f">>> Company address already exists: {addr_name}")
        return

    addr = frappe.get_doc({
        "doctype": "Address",
        "address_title": company,
        "address_type": "Billing",
        "address_line1": "Slovenska cesta 1",
        "city": "Ljubljana",
        "pincode": "1000",
        "country": "Slovenia",
        "is_your_company_address": 1,
        "links": [{"link_doctype": "Company", "link_name": company}],
    })
    addr.flags.ignore_permissions = True
    addr.insert()
    print(f">>> Created company address: {addr.name}")
