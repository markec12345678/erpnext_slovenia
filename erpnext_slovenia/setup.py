"""Setup steps run after the app is installed on a site."""
import frappe


def after_install():
    """Install custom fields, print formats, reports, doctypes needed by erpnext_slovenia."""
    _add_custom_fields()
    _create_print_format()
    _ensure_ddv_report()
    _create_furs_log_doctype()
    _create_payment_code_doctype_and_seed()


def _add_custom_fields():
    """Add tax_id Custom Field to Customer and Supplier."""
    custom_fields = [
        {
            "dt": "Customer",
            "fieldname": "custom_si_tax_id",
            "label": "Davčna številka (SI)",
            "fieldtype": "Data",
            "insert_after": "tax_id",
            "description": "8-mestna slovenska davčna številka (brez SI predpone)",
        },
        {
            "dt": "Supplier",
            "fieldname": "custom_si_tax_id",
            "label": "Davčna številka (SI)",
            "fieldtype": "Data",
            "insert_after": "tax_id",
            "description": "8-mestna slovenska davčna številka (brez SI predpone)",
        },
        # VIES validation status
        {
            "dt": "Customer",
            "fieldname": "custom_si_vies_validated",
            "label": "VIES validirana",
            "fieldtype": "Check",
            "insert_after": "tax_id",
            "default": 0,
            "read_only": 1,
        },
        {
            "dt": "Customer",
            "fieldname": "custom_si_vies_validated_at",
            "label": "VIES datum validacije",
            "fieldtype": "Datetime",
            "insert_after": "custom_si_vies_validated",
            "read_only": 1,
        },
        {
            "dt": "Customer",
            "fieldname": "custom_si_vies_name",
            "label": "VIES registrirano ime",
            "fieldtype": "Data",
            "insert_after": "custom_si_vies_validated_at",
            "read_only": 1,
        },
    ]

    for cf in custom_fields:
        name = f"{cf['dt']}-{cf['fieldname']}"
        if frappe.db.exists("Custom Field", name):
            continue
        try:
            doc = frappe.get_doc({"doctype": "Custom Field", **cf})
            doc.insert(ignore_permissions=True)
            print(f"  -> Custom Field created: {name}")
        except Exception as e:
            print(f"  !! Custom Field failed {name}: {e}")
            frappe.db.rollback()
    frappe.db.commit()


def _create_print_format():
    """Create the Slovenian Sales Invoice Print Format."""
    name = "Slovenski Račun"
    if frappe.db.exists("Print Format", name):
        print(f"  -> Print Format '{name}' already exists")
        return
    try:
        pf = frappe.get_doc({
            "doctype": "Print Format",
            "name": name,
            "doc_type": "Sales Invoice",
            "print_format_type": "Jinja",
            "default_print_language": "sl",
            "custom_format": 1,
            "raw_printing": 0,
            "html": """
{%- set company = frappe.get_doc("Company", doc.company) -%}
{%- set customer = frappe.get_doc("Customer", doc.customer) -%}
<!DOCTYPE html>
<html lang="sl"><head><meta charset="UTF-8">
<style>
  body { font-family: 'Helvetica', sans-serif; font-size: 10pt; color: #222; margin: 0; padding: 15mm; }
  .header { display: flex; justify-content: space-between; border-bottom: 2px solid #2c5282; padding-bottom: 12px; margin-bottom: 20px; }
  .company .name { font-size: 13pt; font-weight: bold; color: #2c5282; }
  .doc-title { text-align: right; }
  .doc-title h1 { font-size: 20pt; color: #2c5282; margin: 0; }
  .parties { margin-bottom: 20px; }
  .party-label { font-size: 8pt; color: #666; text-transform: uppercase; }
  .party-name { font-weight: bold; font-size: 11pt; }
  table.items { width: 100%; border-collapse: collapse; margin-bottom: 20px; }
  table.items th { background: #2c5282; color: white; padding: 8px; text-align: left; font-size: 9pt; }
  table.items th.num, table.items td.num { text-align: right; }
  table.items td { padding: 6px 8px; border-bottom: 1px solid #e2e8f0; }
  table.totals { margin-left: auto; width: 50%; }
  table.totals td { padding: 4px 8px; }
  table.totals td.num { text-align: right; font-weight: 600; }
  table.totals .grand-total { border-top: 2px solid #2c5282; padding-top: 8px; font-size: 12pt; color: #2c5282; font-weight: bold; }
  .footer { margin-top: 30px; padding-top: 10px; border-top: 1px solid #e2e8f0; font-size: 8pt; color: #666; text-align: center; }
</style></head>
<body>
<div class="header">
  <div class="company">
    <div class="name">{{ company.company_name }}</div>
    <div>Davčna št.: {{ company.tax_id or '' }}</div>
  </div>
  <div class="doc-title">
    <h1>RAČUN</h1>
    <div>Št.: {{ doc.name }}</div>
    <div>Datum: {{ frappe.utils.formatdate(doc.posting_date, 'dd. MM. yyyy') }}</div>
    {% if doc.due_date %}<div>Rok plačila: {{ frappe.utils.formatdate(doc.due_date, 'dd. MM. yyyy') }}</div>{% endif %}
  </div>
</div>
<div class="parties">
  <div class="party-label">Kupec</div>
  <div class="party-name">{{ customer.customer_name }}</div>
  {% if customer.tax_id %}<div>Davčna št.: {{ customer.tax_id }}</div>{% endif %}
</div>
<table class="items">
  <thead><tr>
    <th class="num">#</th><th>Artikel</th><th class="num">Količina</th><th class="num">Cena</th><th class="num">Znesek</th>
  </tr></thead>
  <tbody>
  {% for item in doc.items %}
    <tr>
      <td class="num">{{ item.idx }}</td>
      <td>{{ item.item_name or item.item_code }}</td>
      <td class="num">{{ "%.2f"|format(item.qty) }}</td>
      <td class="num">{{ "%.2f"|format(item.rate) }} €</td>
      <td class="num">{{ "%.2f"|format(item.net_amount) }} €</td>
    </tr>
  {% endfor %}
  </tbody>
</table>
<table class="totals">
  <tr><td>Neto skupaj:</td><td class="num">{{ "%.2f"|format(doc.net_total) }} €</td></tr>
  {% for tax in doc.taxes %}
    <tr><td>{{ tax.description }}</td><td class="num">{{ "%.2f"|format(tax.tax_amount) }} €</td></tr>
  {% endfor %}
  <tr class="grand-total"><td>SKUPAJ ZA PLAČILO:</td><td class="num">{{ "%.2f"|format(doc.grand_total) }} €</td></tr>
</table>
<div class="footer">
  Ta račun je izdan v skladu z zakonom o DDV (ZDDV-1).<br>
  Račun je arhiviran v e-Slog 1.6 formatu in priložen dokumentu.
</div>
</body></html>
""",
        })
        pf.insert(ignore_permissions=True)
        print(f"  -> Print Format created: {name}")
    except Exception as e:
        print(f"  !! Print Format failed: {e}")
        frappe.db.rollback()
    frappe.db.commit()


def _ensure_ddv_report():
    """Make sure the DDV Obračun report is registered."""
    name = "DDV Obračun"
    if frappe.db.exists("Report", name):
        print(f"  -> Report '{name}' already exists")
        return
    print(f"  -> Report '{name}' will be synced on bench migrate")


def _create_furs_log_doctype():
    """Create FURS Submission Log doctype."""
    try:
        from erpnext_slovenia.furs.create_log_doctype import main
        main()
    except Exception as e:
        print(f"  !! FURS log doctype failed: {e}")


def _create_payment_code_doctype_and_seed():
    """Create Plačilni Namen doctype and populate with standard codes."""
    try:
        from erpnext_slovenia.payment_codes.payment_codes import main
        main()
    except Exception as e:
        print(f"  !! Payment codes doctype failed: {e}")
