"""
Slovenian Sales Invoice print format.

This is registered as a Frappe "Print Format" doctype, with raw HTML + Jinja
template that includes the UPN QR code (rendered client-side via JavaScript
QR library, or via inline SVG).

Because we can't easily render the QR server-side without external deps,
we use the Google Charts API to generate a QR image on-the-fly from the payload.
The payload is computed server-side and embedded as URL parameter.
"""
import frappe


def render(sales_invoice_name: str) -> str:
    """Render the Slovenian invoice HTML."""
    from erpnext_slovenia.upn_qr.upn_qr import get_upn_qr_payload_for_invoice
    from urllib.parse import quote

    inv = frappe.get_doc("Sales Invoice", sales_invoice_name)
    company = frappe.get_doc("Company", inv.company)
    customer = frappe.get_doc("Customer", inv.customer)

    # Generate UPN QR payload
    try:
        upn_payload = get_upn_qr_payload_for_invoice(sales_invoice_name)
        # URL-encode the payload for Google Charts API
        qr_url = f"https://chart.googleapis.com/chart?cht=qr&chs=300x300&chl={quote(upn_payload)}"
    except Exception as e:
        upn_payload = ""
        qr_url = ""
        frappe.log_error(f"UPN QR failed for {sales_invoice_name}: {e}")

    # Get company address
    company_addr_name = frappe.db.get_value("Dynamic Link",
        {"link_doctype": "Company", "link_name": company.name, "parenttype": "Address"},
        "parent")
    company_addr = frappe.db.get_value("Address", company_addr_name,
        ["address_line1", "city", "pincode", "country", "phone", "email_id"], as_dict=True) if company_addr_name else None

    # Get customer address
    customer_addr_name = inv.customer_address or frappe.db.get_value("Customer", inv.customer, "customer_primary_address")
    customer_addr = frappe.db.get_value("Address", customer_addr_name,
        ["address_line1", "city", "pincode", "country"], as_dict=True) if customer_addr_name else None

    # Get bank account
    bank_account_name = frappe.db.get_value("Bank Account",
        {"company": inv.company, "is_company_account": 1, "disabled": 0}, "name")
    bank_account = frappe.get_doc("Bank Account", bank_account_name) if bank_account_name else None

    # Items HTML
    items_html = ""
    for item in inv.items:
        items_html += f"""
        <tr>
          <td class="num">{item.idx}</td>
          <td>{frappe.utils.escape_html(item.item_name or item.item_code)}</td>
          <td class="num">{item.qty:.2f}</td>
          <td class="num">{item.rate:.2f} €</td>
          <td class="num">{item.net_amount:.2f} €</td>
        </tr>
        """

    # Taxes HTML
    taxes_html = ""
    for tax in inv.taxes:
        taxes_html += f"""
        <tr>
          <td>{frappe.utils.escape_html(tax.description)}</td>
          <td class="num">{tax.rate:.1f}%</td>
          <td class="num">{tax.tax_amount:.2f} €</td>
        </tr>
        """

    # Build full HTML
    html = f"""
<!DOCTYPE html>
<html lang="sl">
<head>
<meta charset="UTF-8">
<title>Račun {inv.name}</title>
<style>
  @page {{ size: A4; margin: 15mm; }}
  body {{ font-family: 'Helvetica', 'Arial', sans-serif; font-size: 10pt; color: #222; }}
  .header {{ display: flex; justify-content: space-between; margin-bottom: 25px; border-bottom: 2px solid #2c5282; padding-bottom: 12px; }}
  .company-block {{ font-size: 9pt; line-height: 1.4; }}
  .company-block .name {{ font-size: 13pt; font-weight: bold; color: #2c5282; margin-bottom: 4px; }}
  .doc-title {{ text-align: right; }}
  .doc-title h1 {{ font-size: 20pt; color: #2c5282; margin: 0; }}
  .doc-title .doc-id {{ font-size: 11pt; margin-top: 4px; }}
  .doc-title .doc-date {{ font-size: 9pt; color: #666; margin-top: 4px; }}

  .parties {{ display: flex; justify-content: space-between; margin-bottom: 20px; }}
  .party {{ flex: 1; }}
  .party-label {{ font-size: 8pt; color: #666; text-transform: uppercase; margin-bottom: 4px; }}
  .party-name {{ font-weight: bold; font-size: 11pt; margin-bottom: 4px; }}
  .party-address {{ font-size: 9pt; line-height: 1.4; color: #444; }}
  .party-taxid {{ font-size: 9pt; margin-top: 6px; }}

  table.items {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
  table.items th {{ background: #2c5282; color: white; padding: 8px; text-align: left; font-size: 9pt; }}
  table.items th.num {{ text-align: right; }}
  table.items td {{ padding: 6px 8px; border-bottom: 1px solid #e2e8f0; }}
  table.items td.num {{ text-align: right; }}
  table.items tr:nth-child(even) {{ background: #f7fafc; }}

  .totals-section {{ display: flex; justify-content: flex-end; margin-bottom: 30px; }}
  table.totals {{ width: 50%; }}
  table.totals td {{ padding: 4px 8px; }}
  table.totals td.num {{ text-align: right; font-weight: 600; }}
  table.totals .grand-total {{ border-top: 2px solid #2c5282; padding-top: 8px; font-size: 12pt; color: #2c5282; font-weight: bold; }}

  .payment-section {{ display: flex; gap: 20px; margin-top: 30px; padding: 15px; background: #f7fafc; border: 1px solid #e2e8f0; border-radius: 4px; }}
  .payment-info {{ flex: 2; }}
  .payment-info h3 {{ margin: 0 0 8px 0; color: #2c5282; font-size: 11pt; }}
  .payment-info table {{ font-size: 9pt; }}
  .payment-info td {{ padding: 3px 8px 3px 0; }}
  .payment-info td.label {{ color: #666; width: 130px; }}
  .payment-info td.value {{ font-weight: 600; }}

  .qr-section {{ flex: 1; text-align: center; }}
  .qr-section img {{ width: 200px; height: 200px; }}
  .qr-section .qr-label {{ font-size: 8pt; color: #666; margin-top: 4px; }}

  .footer {{ margin-top: 30px; padding-top: 10px; border-top: 1px solid #e2e8f0; font-size: 8pt; color: #666; text-align: center; }}
</style>
</head>
<body>

<div class="header">
  <div class="company-block">
    <div class="name">{frappe.utils.escape_html(company.company_name)}</div>
    {f'<div>{frappe.utils.escape_html(company_addr.address_line1)}</div>' if company_addr else ''}
    {f'<div>{frappe.utils.escape_html(company_addr.pincode)} {frappe.utils.escape_html(company_addr.city)}</div>' if company_addr else ''}
    {f'<div>{frappe.utils.escape_html(company_addr.country)}</div>' if company_addr else ''}
    {f'<div>Davčna št.: {frappe.utils.escape_html(company.tax_id or "")}</div>' if company.tax_id else ''}
    {f'<div>Tel: {frappe.utils.escape_html(company_addr.phone)}</div>' if company_addr and company_addr.phone else ''}
  </div>
  <div class="doc-title">
    <h1>RAČUN</h1>
    <div class="doc-id">Št.: {frappe.utils.escape_html(inv.name)}</div>
    <div class="doc-date">Datum: {frappe.utils.formatdate(inv.posting_date, 'dd. MM. yyyy')}</div>
    {f'<div class="doc-date">Rok plačila: {frappe.utils.formatdate(inv.due_date, "dd. MM. yyyy")}</div>' if inv.due_date else ''}
  </div>
</div>

<div class="parties">
  <div class="party">
    <div class="party-label">Kupec</div>
    <div class="party-name">{frappe.utils.escape_html(customer.customer_name)}</div>
    {f'<div class="party-address">{frappe.utils.escape_html(customer_addr.address_line1)}<br>{frappe.utils.escape_html(customer_addr.pincode)} {frappe.utils.escape_html(customer_addr.city)}<br>{frappe.utils.escape_html(customer_addr.country)}</div>' if customer_addr else ''}
    {f'<div class="party-taxid">Davčna št.: {frappe.utils.escape_html(customer.tax_id or "")}</div>' if customer.tax_id else ''}
  </div>
</div>

<table class="items">
  <thead>
    <tr>
      <th class="num" style="width:30px;">#</th>
      <th>Artikel</th>
      <th class="num" style="width:60px;">Količina</th>
      <th class="num" style="width:80px;">Cena</th>
      <th class="num" style="width:100px;">Znesek</th>
    </tr>
  </thead>
  <tbody>
    {items_html}
  </tbody>
</table>

<div class="totals-section">
  <table class="totals">
    <tr><td>Neto skupaj:</td><td class="num">{inv.net_total:.2f} €</td></tr>
    {taxes_html}
    <tr class="grand-total"><td>SKUPAJ ZA PLAČILO:</td><td class="num">{inv.grand_total:.2f} €</td></tr>
  </table>
</div>

<div class="payment-section">
  <div class="payment-info">
    <h3>Navodila za plačilo</h3>
    <table>
      <tr><td class="label">Prejemnik:</td><td class="value">{frappe.utils.escape_html(company.company_name)}</td></tr>
      {f'<tr><td class="label">IBAN:</td><td class="value">{frappe.utils.escape_html(bank_account.iban)}</td></tr>' if bank_account else ''}
      {f'<tr><td class="label">Banka:</td><td class="value">{frappe.utils.escape_html(bank_account.bank)}</td></tr>' if bank_account else ''}
      <tr><td class="label">Znesek:</td><td class="value">{inv.grand_total:.2f} €</td></tr>
      <tr><td class="label">Namen:</td><td class="value">Plačilo računa {frappe.utils.escape_html(inv.name)}</td></tr>
      <tr><td class="label">Rok plačila:</td><td class="value">{frappe.utils.formatdate(inv.due_date, 'dd. MM. yyyy') if inv.due_date else frappe.utils.formatdate(inv.posting_date, 'dd. MM. yyyy')}</td></tr>
    </table>
  </div>
  {f'<div class="qr-section"><img src="{qr_url}" alt="UPN QR"/><div class="qr-label">UPN QR koda<br>za plačilo</div></div>' if qr_url else ''}
</div>

<div class="footer">
  Ta račun je izdan v skladu z zakonom o DDV (ZDDV-1).<br>
  Račun je arhiviran v e-Slog 1.6 formatu in priložen dokumentu.
</div>

</body>
</html>
"""
    return html
