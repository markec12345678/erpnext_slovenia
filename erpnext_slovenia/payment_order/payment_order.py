"""
Slovenski plačilni nalog (Payment Order) XML generator.

Generira XML plačilni nalog v formatu, ki ga sprejemajo slovenske banke
(NLB, NKBM, SKB, Abanka, Sparkasse, UniCredit).

Format temelji na ISO 20022 pain.001.001.03 (Customer Credit Transfer Initiation),
ki je standard za SEPA plačila in ga uporabljajo vse slovenske banke.

Uporaba:
- Generira se iz Payment Entry (ko je docstatus=1, submitted)
- Datoteka se priloži Payment Entry-ju
- Datoteka se lahko naloži v banko preko e-banking portala

Reference:
- ISO 20022 pain.001.001.03
- NLB Banka: e-NLB poslovni banking
- SKB Banka: SKB Net
"""
import datetime
import uuid
import frappe
from frappe import _
from frappe.utils.file_manager import save_file


PAIN_NS = "urn:iso:std:iso:20022:tech:xsd:pain.001.001.03"


def generate_payment_order_xml(payment_entry_names: list, company: str = None) -> str:
    """Generate pain.001.001.03 XML for one or more Payment Entries.

    Args:
        payment_entry_names: List of Payment Entry names
        company: Optional company filter

    Returns:
        XML string in pain.001.001.03 format
    """
    if isinstance(payment_entry_names, str):
        payment_entry_names = [payment_entry_names]

    if not payment_entry_names:
        frappe.throw(_("Ni izbranih plačil."))

    # Load Payment Entries
    payments = []
    for name in payment_entry_names:
        pe = frappe.get_doc("Payment Entry", name)
        if pe.docstatus != 1:
            frappe.throw(_(f"Payment Entry {name} ni potrjen (docstatus != 1)."))
        if company and pe.company != company:
            frappe.throw(_(f"Payment Entry {name} pripada drugemu podjetju."))
        payments.append(pe)

    if not payments:
        frappe.throw(_("Ni veljavnih plačil."))

    # Group by company (in practice, all should be the same company)
    company = payments[0].company
    company_doc = frappe.get_doc("Company", company)

    # Get company IBAN from Bank Account
    bank_account_name = payments[0].bank_account or frappe.db.get_value(
        "Bank Account", {"company": company, "is_default": 1}, "name")
    bank_account = frappe.get_doc("Bank Account", bank_account_name) if bank_account_name else None
    company_iban = (bank_account.iban if bank_account else "").replace(" ", "")
    bank_bic = frappe.db.get_value("Bank", bank_account.bank, "swift_number") if bank_account else ""

    # Message ID (unique per batch)
    msg_id = f"PMT-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
    creation_time = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    # Build XML
    parts = ['<?xml version="1.0" encoding="UTF-8"?>']
    parts.append(
        f'<Document xmlns="{PAIN_NS}" '
        f'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
    )

    # Customer Credit Transfer Initiation
    parts.append("  <CstmrCdtTrfInitn>")

    # Group Header
    parts.append("    <GrpHdr>")
    parts.append(f"      <MsgId>{_x(msg_id)}</MsgId>")
    parts.append(f"      <CreDtTm>{creation_time}</CreDtTm>")
    parts.append(f"      <NbOfTxs>{len(payments)}</NbOfTxs>")
    # Control sum (total amount in EUR)
    total_amount = sum(float(p.paid_amount or 0) for p in payments if p.payment_type == "Pay")
    if total_amount == 0:
        # For Receive payments, use received_amount
        total_amount = sum(float(p.received_amount or 0) for p in payments)
    parts.append(f"      <CtrlSum>{total_amount:.2f}</CtrlSum>")
    # Initiating party
    parts.append("      <InitgPty>")
    parts.append(f"        <Nm>{_x(company_doc.company_name[:70])}</Nm>")
    parts.append(f"        <Id><OrgId><Othr><Id>{_x(company_doc.tax_id or 'SI00000000')}</Id></Othr></OrgId></Id>")
    parts.append("      </InitgPty>")
    parts.append("    </GrpHdr>")

    # Payment Information (one per batch — all from same company/bank account)
    pmt_inf_id = f"PMTINF-{msg_id}"
    parts.append("    <PmtInf>")
    parts.append(f"      <PmtInfId>{_x(pmt_inf_id)}</PmtInfId>")
    parts.append(f"      <PmtMtd>TRF</PmtMtd>")  # Transfer
    parts.append(f"      <NbOfTxs>{len(payments)}</NbOfTxs>")
    parts.append(f"      <CtrlSum>{total_amount:.2f}</CtrlSum>")

    # Payment type information
    parts.append("      <PmtTpInf>")
    parts.append("        <SvcLvl><Cd>URGP</Cd></SvcLvl>")  # Urgent (SEPA)
    parts.append("      </PmtTpInf>")

    # Debitor (company)
    parts.append("      <ReqdExctnDt>" + datetime.date.today().strftime("%Y-%m-%d") + "</ReqdExctnDt>")
    parts.append("      <Dbtr>")
    parts.append(f"        <Nm>{_x(company_doc.company_name[:70])}</Nm>")
    parts.append(f"        <PstlAdr><Ctry>SI</Ctry></PstlAdr>")
    parts.append("      </Dbtr>")

    # Debitor account (IBAN)
    if company_iban:
        parts.append("      <DbtrAcct>")
        parts.append(f"        <Id><IBAN>{_x(company_iban)}</IBAN></Id>")
        parts.append(f"        <Ccy>EUR</Ccy>")
        parts.append("      </DbtrAcct>")

    # Debitor agent (bank)
    if bank_bic:
        parts.append("      <DbtrAgt>")
        parts.append(f"        <FinInstnId><BIC>{_x(bank_bic)}</BIC></FinInstnId>")
        parts.append("      </DbtrAgt>")

    # Charge bearer: shared (most common in SI)
    parts.append("      <ChrgBr>SHAR</ChrgBr>")

    # Individual credit transfer transactions
    for pe in payments:
        # Determine party (creditor for Pay, debitor for Receive)
        if pe.payment_type == "Pay":
            party_type = pe.party_type
            party_name = pe.party_name
            amount = float(pe.paid_amount or 0)
            direction = "creditor"
        else:
            # Receive: counterparty is the debtor
            party_type = pe.party_type
            party_name = pe.party_name
            amount = float(pe.received_amount or 0)
            direction = "debtor"

        # Get party IBAN (from supplier/customer bank account)
        party_iban = _get_party_iban(pe.party_type, pe.party)
        party_address = _get_party_address(pe.party_type, pe.party)

        # End-to-end ID (unique per transaction)
        e2e_id = f"{pe.name}-{datetime.datetime.now().strftime('%Y%m%d')}"[:35]

        parts.append("      <CdtTrfTxInf>")
        parts.append("        <PmtId>")
        parts.append(f"          <EndToEndId>{_x(e2e_id)}</EndToEndId>")
        parts.append("        </PmtId>")

        # Amount
        parts.append("        <Amt>")
        parts.append(f"          <InstdAmt Ccy=\"EUR\">{amount:.2f}</InstdAmt>")
        parts.append("        </Amt>")

        # Creditor agent (if known)
        party_bank = _get_party_bank(pe.party_type, pe.party)
        if party_bank and party_bank.get("bic"):
            parts.append("        <CdtrAgt>")
            parts.append(f"          <FinInstnId><BIC>{_x(party_bank['bic'])}</BIC></FinInstnId>")
            parts.append("        </CdtrAgt>")

        # Creditor
        parts.append("        <Cdtr>")
        parts.append(f"          <Nm>{_x(party_name[:70]) if party_name else 'Neznan prejemnik'}</Nm>")
        if party_address:
            parts.append(f"          <PstlAdr>")
            if party_address.get("street"):
                parts.append(f"            <StrtNm>{_x(party_address['street'][:70])}</StrtNm>")
            if party_address.get("building"):
                parts.append(f"            <BldgNb>{_x(party_address['building'][:16])}</BldgNb>")
            if party_address.get("city"):
                parts.append(f"            <TwnNm>{_x(party_address['city'][:35])}</TwnNm>")
            if party_address.get("postal"):
                parts.append(f"            <PstCd>{_x(party_address['postal'][:16])}</PstCd>")
            parts.append(f"            <Ctry>{_x(party_address.get('country', 'SI'))}</Ctry>")
            parts.append(f"          </PstlAdr>")
        else:
            parts.append(f"          <PstlAdr><Ctry>SI</Ctry></PstlAdr>")
        parts.append("        </Cdtr>")

        # Creditor account (IBAN)
        if party_iban:
            parts.append("        <CdtrAcct>")
            parts.append(f"          <Id><IBAN>{_x(party_iban)}</IBAN></Id>")
            parts.append(f"          <Ccy>EUR</Ccy>")
            parts.append("        </CdtrAcct>")

        # Remittance information (reference + purpose)
        parts.append("        <RmtInf>")
        # SI reference (structured)
        si_ref = _extract_si_reference(pe)
        if si_ref:
            parts.append("          <Strd>")
            parts.append("            <CdtrRefInf>")
            parts.append("              <Tp><CdOrPrtry><Prtry>SI</Prtry></CdOrPrtry></Tp>")
            parts.append(f"              <Ref>{_x(si_ref)}</Ref>")
            parts.append("            </CdtrRefInf>")
            parts.append("          </Strd>")
        # Unstructured (payment purpose)
        purpose = (pe.remarks or f"Plačilo {pe.name}")[:140]
        parts.append(f"          <Ustrd>{_x(purpose)}</Ustrd>")
        parts.append("        </RmtInf>")

        parts.append("      </CdtTrfTxInf>")

    parts.append("    </PmtInf>")
    parts.append("  </CstmrCdtTrfInitn>")
    parts.append("</Document>")

    return "\n".join(parts)


@frappe.whitelist()
def generate_and_attach_payment_order(payment_entry_names) -> dict:
    """RPC: Generate payment order XML and attach to Payment Entries.

    Args:
        payment_entry_names: Single name or JSON list of names

    Returns:
        Dict with file URL and metadata.
    """
    import json
    if isinstance(payment_entry_names, str):
        try:
            payment_entry_names = json.loads(payment_entry_names)
        except (json.JSONDecodeError, TypeError):
            payment_entry_names = [payment_entry_names]

    if not payment_entry_names:
        return {"success": False, "error": _("Ni izbranih plačil.")}

    # Generate XML
    xml_content = generate_payment_order_xml(payment_entry_names)

    # File name
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = f"PlacilniNalog_{timestamp}.xml"

    # Attach to first Payment Entry
    first_pe = payment_entry_names[0]

    f = save_file(
        fname=file_name,
        content=xml_content,
        dt="Payment Entry",
        dn=first_pe,
        folder=None,
        is_private=0,
        df=None,
    )
    frappe.db.commit()

    return {
        "success": True,
        "file_url": f.file_url,
        "file_name": f.file_name,
        "file_size": f.file_size,
        "payment_count": len(payment_entry_names),
        "total_amount": sum(
            float(frappe.db.get_value("Payment Entry", n, "paid_amount") or 0)
            for n in payment_entry_names
        ),
    }


@frappe.whitelist()
def generate_payment_order_for_invoice(sales_invoice_name: str) -> dict:
    """RPC: Generate a payment order XML for a Sales Invoice (incoming payment).

    Useful when the customer needs to be sent a payment instruction.
    """
    inv = frappe.get_doc("Sales Invoice", sales_invoice_name)
    if inv.docstatus != 1:
        return {"success": False, "error": _("Račun ni potrjen.")}

    # Create a temporary Payment Entry record (without submitting) for XML generation
    company = frappe.get_doc("Company", inv.company)
    customer = frappe.get_doc("Customer", inv.customer)

    # Get customer IBAN (if any)
    customer_iban = _get_party_iban("Customer", inv.customer)

    # Build a minimal XML with company as creditor (we're receiving)
    msg_id = f"INV-{sales_invoice_name}-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
    creation_time = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    # Get company IBAN
    bank_account_name = frappe.db.get_value("Bank Account",
        {"company": inv.company, "is_default": 1}, "name")
    bank_account = frappe.get_doc("Bank Account", bank_account_name) if bank_account_name else None
    company_iban = (bank_account.iban if bank_account else "").replace(" ", "")
    bank_bic = frappe.db.get_value("Bank", bank_account.bank, "swift_number") if bank_account else ""

    # Build payment information as if customer is paying us
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="{PAIN_NS}" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <CstmrCdtTrfInitn>
    <GrpHdr>
      <MsgId>{_x(msg_id)}</MsgId>
      <CreDtTm>{creation_time}</CreDtTm>
      <NbOfTxs>1</NbOfTxs>
      <CtrlSum>{inv.grand_total:.2f}</CtrlSum>
      <InitgPty>
        <Nm>{_x(customer.customer_name[:70])}</Nm>
      </InitgPty>
    </GrpHdr>
    <PmtInf>
      <PmtInfId>{_x(msg_id + '-INF')}</PmtInfId>
      <PmtMtd>TRF</PmtMtd>
      <NbOfTxs>1</NbOfTxs>
      <CtrlSum>{inv.grand_total:.2f}</CtrlSum>
      <PmtTpInf><SvcLvl><Cd>URGP</Cd></SvcLvl></PmtTpInf>
      <ReqdExctnDt>{datetime.date.today().strftime('%Y-%m-%d')}</ReqdExctnDt>
      <Dbtr>
        <Nm>{_x(customer.customer_name[:70])}</Nm>
        <PstlAdr><Ctry>SI</Ctry></PstlAdr>
      </Dbtr>
      {f'<DbtrAcct><Id><IBAN>{_x(customer_iban)}</IBAN></Id><Ccy>EUR</Ccy></DbtrAcct>' if customer_iban else ''}
      <Cdtr>
        <Nm>{_x(company.company_name[:70])}</Nm>
        <PstlAdr><Ctry>SI</Ctry></PstlAdr>
      </Cdtr>
      <CdtrAcct>
        <Id><IBAN>{_x(company_iban)}</IBAN></Id>
        <Ccy>EUR</Ccy>
      </CdtrAcct>
      {f'<CdtrAgt><FinInstnId><BIC>{_x(bank_bic)}</BIC></FinInstnId></CdtrAgt>' if bank_bic else ''}
      <ChrgBr>SHAR</ChrgBr>
      <CdtTrfTxInf>
        <PmtId>
          <EndToEndId>{_x(sales_invoice_name[:35])}</EndToEndId>
        </PmtId>
        <Amt><InstdAmt Ccy="EUR">{inv.grand_total:.2f}</InstdAmt></Amt>
        <Cdtr>
          <Nm>{_x(company.company_name[:70])}</Nm>
        </Cdtr>
        <CdtrAcct>
          <Id><IBAN>{_x(company_iban)}</IBAN></Id>
          <Ccy>EUR</Ccy>
        </CdtrAcct>
        <RmtInf>
          <Strd>
            <CdtrRefInf>
              <Tp><CdOrPrtry><Prtry>SI</Prtry></CdOrPrtry></Tp>
              <Ref>{_x(_extract_si_reference_from_invoice(inv))}</Ref>
            </CdtrRefInf>
          </Strd>
          <Ustrd>{_x(f'Plačilo računa {inv.name}')}</Ustrd>
        </RmtInf>
      </CdtTrfTxInf>
    </PmtInf>
  </CstmrCdtTrfInitn>
</Document>"""

    # Save as attachment
    file_name = f"PlacilniNalog_{sales_invoice_name}.xml"
    existing = frappe.db.exists("File", {
        "attached_to_doctype": "Sales Invoice",
        "attached_to_name": sales_invoice_name,
        "file_name": file_name,
    })
    if existing:
        frappe.delete_doc("File", existing, force=True)

    f = save_file(
        fname=file_name,
        content=xml,
        dt="Sales Invoice",
        dn=sales_invoice_name,
        folder=None,
        is_private=0,
        df=None,
    )
    frappe.db.commit()

    return {
        "success": True,
        "file_url": f.file_url,
        "file_name": f.file_name,
        "amount": float(inv.grand_total),
        "iban": company_iban,
        "bic": bank_bic,
        "si_reference": _extract_si_reference_from_invoice(inv),
    }


# === Helpers ===

def _get_party_iban(party_type: str, party_name: str) -> str:
    """Get IBAN for a customer/supplier."""
    if not party_name:
        return ""
    # Check Bank Account linked to party
    bank_accounts = frappe.get_all("Bank Account",
        filters={
            "party_type": party_type,
            "party": party_name,
            "disabled": 0,
        },
        pluck="iban")
    for iban in bank_accounts:
        if iban:
            return iban.replace(" ", "")
    return ""


def _get_party_bank(party_type: str, party_name: str) -> dict:
    """Get bank info (BIC) for a customer/supplier."""
    if not party_name:
        return {}
    bank_name = frappe.db.get_value("Bank Account",
        {"party_type": party_type, "party": party_name, "disabled": 0},
        "bank")
    if bank_name:
        bic = frappe.db.get_value("Bank", bank_name, "swift_number")
        return {"bank": bank_name, "bic": bic}
    return {}


def _get_party_address(party_type: str, party_name: str) -> dict:
    """Get address dict for a customer/supplier."""
    if not party_name:
        return None
    addr_name = None
    if party_type == "Customer":
        addr_name = frappe.db.get_value("Customer", party_name, "customer_primary_address")
    if not addr_name:
        addr_name = frappe.db.get_value("Dynamic Link",
            {"link_doctype": party_type, "link_name": party_name, "parenttype": "Address"},
            "parent")
    if not addr_name:
        return None
    addr = frappe.db.get_value("Address", addr_name,
        ["address_line1", "city", "pincode", "country"], as_dict=True)
    if not addr:
        return None

    # Parse street + building number from address_line1
    street = ""
    building = ""
    if addr.get("address_line1"):
        line = addr["address_line1"]
        # Split at last space (assuming number is at the end)
        parts = line.rsplit(" ", 1)
        if len(parts) == 2 and parts[1][:1].isdigit():
            street = parts[0]
            building = parts[1]
        else:
            street = line

    # Country code (2-letter)
    country_code = "SI"
    if addr.get("country"):
        country_full = addr["country"]
        # Map common to ISO
        country_map = {"Slovenia": "SI", "Italy": "IT", "Austria": "AT", "Germany": "DE",
                       "Croatia": "HR", "France": "FR", "Spain": "ES"}
        country_code = country_map.get(country_full, "SI")

    return {
        "street": street,
        "building": building,
        "city": addr.get("city", ""),
        "postal": addr.get("pincode", ""),
        "country": country_code,
    }


def _extract_si_reference(payment_entry) -> str:
    """Extract SI reference from Payment Entry (from reference_number or remarks)."""
    if payment_entry.reference_no:
        ref = payment_entry.reference_no.strip().upper()
        if ref.startswith("SI"):
            return ref
        # Try to find SI ref in remarks
    if payment_entry.remarks:
        import re
        m = re.search(r"SI\d{2}\d+", payment_entry.remarks.upper())
        if m:
            return m.group(0)
    return ""


def _extract_si_reference_from_invoice(invoice) -> str:
    """Generate SI reference from invoice name (MOD 11 checksum)."""
    import re
    digits = re.sub(r"\D", "", invoice.name)
    if not digits:
        return ""
    # Compute MOD 11 checksum
    weights = [2, 3, 4, 5, 6, 7]
    s = 0
    for i, d in enumerate(reversed(digits)):
        s += int(d) * weights[i % 6]
    mod = s % 11
    if mod == 0:
        cs = 0
    elif mod == 1:
        return ""  # invalid
    else:
        cs = 11 - mod
    return f"SI00{digits}{cs}"


def _x(text) -> str:
    """Escape XML special characters."""
    if text is None:
        return ""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )
