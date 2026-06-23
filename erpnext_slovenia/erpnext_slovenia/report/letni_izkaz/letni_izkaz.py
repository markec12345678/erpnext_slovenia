"""
RAČ: Letni računovodski izkaz (Annual Financial Statements).

Generira dve poročili v enem:
1. BILANCA STANJA (Balance Sheet) - prikaz sredstev in obveznosti do virov sredstev
2. POSLOVNI IZID (Income Statement / P&L) - prikaz prihodkov in odhodkov

Po SRS (Slovenski računovodski standardi) struktura:

BILANCA STANJA:
  A. DOLGOROČNA SREDSTVA
    I. Nematerialna sredstva
    II. Materialna sredstva (nepremičnine)
    III. Dolgoročne finančne naložbe
  B. KRATKOROČNA SREDSTVA
    I. Zaloge
    II. Kratkoročne terjatve
    III. Kratkoročne finančne naložbe
    IV. Denarna sredstva
    V. Aktivne časovne razmejitve
  C. SKUPAJ SREDSTVA (A + B)

  A. KAPITAL
    I. Osnovni kapital
    II. Kapitalske rezerve
    III. Statutarne in druge rezerve
    IV. Nerazporejeni dobiček
  B. DOLGOROČNE OBVEZNOSTI
  C. KRATKOROČNE OBVEZNOSTI
  D. SKUPAJ OBVEZNOSTI (B + C)
  E. PASIVNE ČASOVNE RAZMEJITVE

POSLOVNI IZID:
  I. Poslovni prihodki
  II. Znižanje vrednosti zalog (prodnih)
  III. Stroški materiala
  IV. Stroški storitev
  V. Dodana vrednost (I - II - III - IV)
  VI. Stroški dela
  VII. Amortizacija
  VIII. Drugi poslovni prihodki
  IX. Drugi poslovni stroški
  X. Poslovni izid iz rednega poslovanja
  XI. Finančni prihodki
  XII. Finančni stroški
  XIII. Dobiček iz rednega poslovanja
"""
import frappe
from frappe import _
from frappe.utils import flt


def execute(filters: dict | None = None):
    if not filters:
        filters = {}

    company = filters.get("company")
    from_date = filters.get("from_date")
    to_date = filters.get("to_date")

    if not (company and from_date and to_date):
        return [], [], _("Prosimo, izberite podjetje in datumsko obdobje.")

    # Get all GL entries for the company in the period
    gl_entries = frappe.db.get_all("GL Entry",
        filters={
            "company": company,
            "is_cancelled": 0,
            "posting_date": ["between", [from_date, to_date]],
        },
        fields=["account", "debit", "credit", "account_type"])

    # Aggregate by account
    account_balances: dict[str, dict] = {}
    for gl in gl_entries:
        acc = gl["account"]
        if acc not in account_balances:
            account_balances[acc] = {
                "debit": 0.0,
                "credit": 0.0,
                "balance": 0.0,
            }
        account_balances[acc]["debit"] += flt(gl["debit"])
        account_balances[acc]["credit"] += flt(gl["credit"])
        account_balances[acc]["balance"] += flt(gl["debit"]) - flt(gl["credit"])

    # Get account metadata (root_type, account_number)
    accounts_meta = {}
    for acc_name in account_balances.keys():
        meta = frappe.db.get_value("Account", acc_name,
            ["account_number", "root_type", "account_type", "is_group"], as_dict=True)
        if meta:
            accounts_meta[acc_name] = meta

    # Build report rows
    columns = [
        {"fieldname": "section", "label": _("Sekcija"), "fieldtype": "Data", "width": 250},
        {"fieldname": "amount", "label": _("Znesek (EUR)"), "fieldtype": "Currency",
         "options": "EUR", "width": 150},
    ]

    data = []

    # ===== BILANCA STANJA (Balance Sheet) =====
    data.append({"section": "===== BILANCA STANJA =====", "amount": None})

    # A. DOLGOROČNA SREDSTVA
    long_term_assets = _aggregate_by_account_prefix(account_balances, accounts_meta, ["0"])
    long_term_assets_total = sum(b for b in long_term_assets.values())
    data.append({"section": "A. DOLGOROČNA SREDSTVA", "amount": None})
    for acc_name, bal in sorted(long_term_assets.items()):
        meta = accounts_meta.get(acc_name, {})
        num = meta.get("account_number", "")
        data.append({"section": f"  {num} {acc_name}", "amount": bal})
    data.append({"section": "  SKUPAJ A", "amount": long_term_assets_total})

    # C. SKUPAJ SREDSTVA
    total_assets = sum(b["balance"] for b in account_balances.values()
                       if accounts_meta.get(account_balances and list(account_balances.keys())[0], {}).get("root_type") == "Asset")
    # Better: re-compute properly
    total_assets = sum(b for n, b in _aggregate_by_root_type(account_balances, accounts_meta, "Asset").items())
    data.append({"section": "SKUPAJ SREDSTVA (A + B)", "amount": total_assets})
    data.append({"section": "", "amount": None})

    # A. KAPITAL (Equity)
    equity_total = sum(b for n, b in _aggregate_by_root_type(account_balances, accounts_meta, "Equity").items())
    data.append({"section": "A. KAPITAL", "amount": equity_total})

    # B. DOLGOROČNE OBVEZNOSTI
    liab_total = sum(b for n, b in _aggregate_by_root_type(account_balances, accounts_meta, "Liability").items())
    data.append({"section": "B. OBVEZNOSTI", "amount": liab_total})

    data.append({"section": "SKUPAJ OBVEZNOSTI + KAPITAL", "amount": equity_total + liab_total})
    data.append({"section": "", "amount": None})

    # ===== POSLOVNI IZID (Income Statement) =====
    data.append({"section": "===== POSLOVNI IZID =====", "amount": None})

    # Prihodki (Income)
    income_total = sum(b for n, b in _aggregate_by_root_type(account_balances, accounts_meta, "Income").items())
    data.append({"section": "I. POSLOVNI PRIHODKI", "amount": income_total})

    # Stroški (Expenses)
    expense_total = sum(b for n, b in _aggregate_by_root_type(account_balances, accounts_meta, "Expense").items())
    data.append({"section": "II. POSLOVNI STROŠKI", "amount": expense_total})

    # Poslovni izid
    profit_loss = income_total - expense_total
    data.append({"section": "", "amount": None})
    if profit_loss >= 0:
        data.append({"section": "DOBIČEK", "amount": profit_loss})
    else:
        data.append({"section": "IZGUBA", "amount": abs(profit_loss)})

    # Summary cards
    report_summary = [
        {"value": f"€ {total_assets:,.2f}", "indicator": "Blue", "label": _("Skupaj sredstva"), "datatype": "Data"},
        {"value": f"€ {equity_total:,.2f}", "indicator": "Green", "label": _("Kapital"), "datatype": "Data"},
        {"value": f"€ {liab_total:,.2f}", "indicator": "Orange", "label": _("Obveznosti"), "datatype": "Data"},
        {"value": f"€ {profit_loss:,.2f}", "indicator": "Green" if profit_loss >= 0 else "Red",
         "label": _("Poslovni izid"), "datatype": "Data"},
    ]

    chart = {
        "data": {
            "labels": ["Sredstva", "Kapital", "Obveznosti", "Prihodki", "Stroški", "Izid"],
            "datasets": [{
                "name": _("Zneski (EUR)"),
                "values": [total_assets, equity_total, liab_total, income_total, expense_total, profit_loss],
            }],
        },
        "type": "bar",
        "colors": ["#5e64ff", "#28a745", "#ffc107", "#17a2b8", "#dc3545", "#6f42c1"],
    }

    return columns, data, None, chart, report_summary


def _aggregate_by_account_prefix(balances: dict, meta: dict, prefixes: list) -> dict:
    """Aggregate balances by account_number prefix."""
    result = {}
    for acc_name, bal in balances.items():
        m = meta.get(acc_name)
        if not m or not m.get("account_number"):
            continue
        num = m["account_number"]
        for p in prefixes:
            if num.startswith(p):
                # Skip group accounts
                if m.get("is_group"):
                    continue
                result[acc_name] = bal["balance"]
                break
    return result


def _aggregate_by_root_type(balances: dict, meta: dict, root_type: str) -> dict:
    """Aggregate balances where root_type matches."""
    result = {}
    for acc_name, bal in balances.items():
        m = meta.get(acc_name)
        if not m:
            continue
        if m.get("root_type") == root_type:
            # Skip group accounts (which already sum children)
            if m.get("is_group"):
                continue
            result[acc_name] = bal["balance"]
    return result
