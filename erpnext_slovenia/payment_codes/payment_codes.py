"""
Slovenian standard payment purpose codes (Plačilni nameni).

Banka Slovenije in Združenje bank Slovenije (ZBS) določata standardizirane
3-mestne kode plačilnih namenov, ki se uporabljajo v UPN obrazcih in MT940
bančnih izpiskih.

Reference: https://www.bsi.si/standardni-placilni-nameni
"""
import frappe


# Standardni plačilni nameni (ZBS 2024)
# Format: (code, slovenian_name, english_description)
PAYMENT_CODES = [
    # Skupina A: plačila blaga in storitev
    ("ADTG", "Plačilo za drugo blago in storitve", "Other goods and services payment"),
    ("ADVA", "Plačilo avansa", "Advance payment"),
    ("AIPS", "Plačilo za gotove storitve", "Ready services payment"),
    ("AKCP", "Plačilo akontacije", "Acont payment"),
    ("ARTI", "Plačilo za artikle", "Articles payment"),
    ("ASVC", "Plačilo za storitve", "Services payment"),

    # Skupina C: stroški
    ("COST", "Stroški", "Costs"),
    ("CBNK", "Bančni stroški", "Bank costs"),
    ("CINS", "Stroški zavarovanja", "Insurance costs"),
    ("COMM", "Provizija", "Commission"),
    ("CPUR", "Nabavni stroški", "Purchase costs"),

    # Skupina D: dobiček / dividend
    ("DIVD", "Dividenda", "Dividend"),
    ("DBTP", "Druga plačila dobička", "Other profit payments"),

    # Skupina E: izplačila delavcem
    ("SALA", "Plača", "Salary"),
    ("PENS", "Pokojnina", "Pension"),
    ("BONU", "Bonus", "Bonus"),
    ("INTX", "Dohodnina", "Income tax"),
    ("SCVT", "Prispevki za socialno varnost", "Social security contributions"),

    # Skupina F: finančne transakcije
    ("LOAN", "Posojilo", "Loan"),
    ("LREP", "Vračilo posojila", "Loan repayment"),
    ("INTP", "Obresti", "Interest payment"),
    ("FINT", "Finančne obresti", "Financial interest"),
    ("FINC", "Finančne storitve", "Financial services"),

    # Skupina G: blago
    ("GDSV", "Dobava blaga", "Goods delivery"),
    ("GDSR", "Vračilo blaga", "Goods return"),

    # Skupina H: izredni izdatki
    ("DONA", "Donacija", "Donation"),
    ("PENA", "Kazni", "Penalty"),
    ("TAXP", "Plačilo davka", "Tax payment"),
    ("TAXR", "Povračilo davka", "Tax refund"),

    # Skupina I: investicije
    ("INTE", "Investicije", "Investment"),
    ("ASST", "Nakup sredstev", "Asset purchase"),

    # Skupina R: najem
    ("RENT", "Najemnina", "Rent"),
    ("LEAS", "Lizing", "Leasing"),

    # Skupina S: subvencije
    ("SUBS", "Subvencija", "Subsidy"),
    ("SUBV", "Subvencija (varianta)", "Subvention"),

    # Skupina T: povezane transakcije
    ("INTR", "Notranji transfer", "Internal transfer"),
    ("CASH", "Transakcija gotovine", "Cash transaction"),

    # Skupina O: ostalo
    ("OTHR", "Drugo", "Other"),
    ("REFN", "Povračilo", "Refund"),
    ("REIM", "Povračilo stroškov", "Reimbursement"),
    ("BILL", "Plačilo računa", "Bill payment"),

    # Skupina V: državne transakcije
    ("VATP", "Plačilo DDV", "VAT payment"),
    ("CTAX", "Carinski davki", "Customs duties"),
    ("FURS", "Plačilo FURS", "FURS payment"),
]


@frappe.whitelist()
def get_payment_codes() -> list:
    """RPC: return all standard payment codes."""
    return [{"code": c, "name_si": n, "name_en": e} for c, n, e in PAYMENT_CODES]


@frappe.whitelist()
def get_payment_code_name(code: str) -> str:
    """RPC: get Slovenian name for a payment code."""
    for c, n, _ in PAYMENT_CODES:
        if c == code:
            return n
    return ""


def create_payment_code_doctype():
    """Create a 'Placilni Namen' doctype for managing codes in DB.

    This is optional - codes can also be retrieved via get_payment_codes() RPC.
    Note: DocType name can't have non-ASCII chars (Frappe restriction),
    so we use ASCII "Placilni Namen" as DocType name but show "Plačilni Namen" as label.
    """
    name = "Placilni Namen"
    if frappe.db.exists("DocType", name):
        return

    doctype_def = {
        "doctype": "DocType",
        "name": name,
        "module": "Core",
        "custom": 0,
        "autoname": "field:code",
        "naming_rule": "By fieldname",
        "title_field": "code",
        "search_fields": "code,name_si",
        "fields": [
            {"fieldname": "code", "label": "Koda", "fieldtype": "Data", "reqd": 1, "unique": 1, "in_list_view": 1},
            {"fieldname": "name_si", "label": "Slovensko ime", "fieldtype": "Data", "reqd": 1, "in_list_view": 1},
            {"fieldname": "name_en", "label": "Angleško ime", "fieldtype": "Data", "in_list_view": 1},
            {"fieldname": "active", "label": "Aktivna", "fieldtype": "Check", "default": 1},
        ],
        "permissions": [
            {"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "report": 1},
            {"role": "Accounts Manager", "read": 1, "write": 0, "create": 0, "delete": 0, "report": 1},
            {"role": "Accounts User", "read": 1, "write": 0, "create": 0, "delete": 0, "report": 1},
        ],
    }
    try:
        doc = frappe.get_doc(doctype_def)
        doc.flags.ignore_permissions = True
        doc.insert()
        frappe.db.commit()
        print(f">>> Doctype '{name}' created")
    except Exception as e:
        print(f">>> Doctype '{name}' creation failed: {e}")
        frappe.db.rollback()


def seed_payment_codes():
    """Populate Placilni Namen doctype with standard codes."""
    name = "Placilni Namen"
    if not frappe.db.exists("DocType", name):
        return

    inserted = 0
    for code, name_si, name_en in PAYMENT_CODES:
        if frappe.db.exists(name, code):
            continue
        try:
            doc = frappe.get_doc({
                "doctype": name,
                "code": code,
                "name_si": name_si,
                "name_en": name_en,
                "active": 1,
            })
            doc.flags.ignore_permissions = True
            doc.insert()
            inserted += 1
        except Exception as e:
            print(f"  !! Failed {code}: {e}")
            frappe.db.rollback()
    frappe.db.commit()
    print(f">>> Inserted {inserted} payment codes")


def main():
    """Create doctype and seed payment codes."""
    create_payment_code_doctype()
    seed_payment_codes()


if __name__ == "__main__":
    main()
