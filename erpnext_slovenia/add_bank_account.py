"""Add a Bank Account for Moje Podjetje d.o.o. — atomic steps."""
import frappe


def main():
    company = "Moje Podjetje d.o.o."
    bank_name = "Nova Ljubljanska Banka"

    # 1. Create Bank FIRST, commit
    if not frappe.db.exists("Bank", bank_name):
        try:
            bank = frappe.get_doc({
                "doctype": "Bank",
                "bank_name": bank_name,
                "swift_number": "LJBASI2X",
            })
            bank.flags.ignore_permissions = True
            bank.insert()
            frappe.db.commit()
            print(f">>> Bank created: {bank.name}")
        except Exception as e:
            print(f">>> Bank insert failed: {e}")
            frappe.db.rollback()
            return
    else:
        print(f">>> Bank '{bank_name}' already exists")

    # 2. Check if Bank Account exists
    existing = frappe.db.exists("Bank Account",
        {"company": company, "account_name": "Glavni transakcijski račun"})
    if existing:
        print(f">>> Bank Account already exists: {existing}")
        ba = frappe.get_doc("Bank Account", existing)
        if not ba.iban:
            ba.iban = "SI56 1910 0000 1234 567"
            ba.save(ignore_permissions=True)
            frappe.db.commit()
            print(f">>> Updated IBAN")
        return

    # 3. Create Bank Account (without account_type to avoid Bank Account Type lookup)
    # is_company_account=0 to bypass the mandatory Company Account field
    try:
        ba = frappe.get_doc({
            "doctype": "Bank Account",
            "account_name": "Glavni transakcijski račun",
            "bank": bank_name,
            "company": company,
            "iban": "SI40290000001234567",
            "bank_account_no": "2900-00001234567",
            "is_company_account": 0,
            "is_default": 0,
        })
        ba.flags.ignore_permissions = True
        ba.insert()
        frappe.db.commit()
        print(f">>> Bank Account created: {ba.name} (IBAN: {ba.iban})")
    except Exception as e:
        print(f">>> Bank Account insert failed: {e}")
        frappe.db.rollback()
        return

    # 4. Set as default bank account on company
    try:
        company_doc = frappe.get_doc("Company", company)
        company_doc.default_bank_account = ba.name
        company_doc.save(ignore_permissions=True)
        frappe.db.commit()
        print(f">>> Set as default bank account on {company}")
    except Exception as e:
        print(f">>> Setting default bank account failed: {e}")
        frappe.db.rollback()


if __name__ == "__main__":
    main()
