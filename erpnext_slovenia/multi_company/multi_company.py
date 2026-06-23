"""
Multi-company helper for Slovenian ERPNext installations.

ERPNext already supports multiple companies in a single site natively.
This module provides helpers for:
1. Creating additional Slovenian companies with proper Chart of Accounts
2. Switching between companies (UI helper)
3. Per-company FURS configuration
4. Cross-company consolidation report
"""
import frappe
from frappe import _
from frappe.utils.nestedset import rebuild_tree


@frappe.whitelist()
def create_slovenian_company(company_name: str, abbr: str, tax_id: str = None,
                            currency: str = "EUR", country: str = "Slovenia",
                            default_warehouse: bool = True) -> dict:
    """RPC: Create a new Slovenian company with default Chart of Accounts.

    Args:
        company_name: Full legal name (e.g., "Kovinar d.o.o.")
        abbr: Short abbreviation (e.g., "KO", max 5 chars)
        tax_id: Optional tax ID (with or without SI prefix)
        currency: Default currency (defaults to EUR)
        country: Country (defaults to Slovenia)
        default_warehouse: Create default warehouses (Stores, WIP, Finished Goods)

    Returns:
        Dict with: success, company_name, accounts_created, errors
    """
    # Validate
    if frappe.db.exists("Company", company_name):
        return {"success": False, "error": _("Podjetje že obstaja.")}

    if not abbr or len(abbr) > 5:
        return {"success": False, "error": _("Okrajšava mora imeti 1-5 znakov.")}

    # Clean tax_id
    if tax_id:
        tax_id = tax_id.strip().upper()
        if not tax_id.startswith("SI"):
            tax_id = "SI" + tax_id

    # Create company
    try:
        company = frappe.get_doc({
            "doctype": "Company",
            "company_name": company_name,
            "abbr": abbr,
            "default_currency": currency,
            "country": country,
            "create_chart_of_accounts_based_on": "Standard Template",
            "chart_of_accounts": "Standard Template",
            "domain": "Manufacturing",
            "enable_perpetual_inventory": 1,
            "tax_id": tax_id,
        })
        company.flags.ignore_permissions = True
        company.insert()
        frappe.db.commit()
    except Exception as e:
        # Even if on_update fails, the doc may be saved
        if not frappe.db.exists("Company", company_name):
            return {"success": False, "error": str(e)}

    # Create default accounts if not created by on_update
    accounts_count = frappe.db.count("Account", {"company": company_name})
    if accounts_count == 0:
        # Build minimal chart
        from erpnext_slovenia.srs.srs_chart import SRS_CHART, make_account
        # Override global COMPANY
        import erpnext_slovenia.srs.srs_chart as srs_module
        original_company = srs_module.COMPANY
        srs_module.COMPANY = company_name
        try:
            created = 0
            for number, name, parent_number, is_group, account_type, root_type in SRS_CHART[:50]:
                try:
                    srs_module.make_account(number, name, parent_number, is_group, account_type, root_type)
                    created += 1
                except Exception:
                    frappe.db.rollback()
            frappe.db.commit()
            rebuild_tree("Account")
            frappe.db.commit()
            accounts_count = created
        finally:
            srs_module.COMPANY = original_company

    # Create default cost center
    if not frappe.db.get_value("Cost Center", {"company": company_name, "is_group": 0}):
        try:
            # Get root cost center for company (created by on_update)
            root_cc = frappe.db.get_value("Cost Center",
                {"company": company_name, "is_group": 1}, "name")
            if root_cc:
                cc = frappe.get_doc({
                    "doctype": "Cost Center",
                    "cost_center_name": "Main",
                    "parent_cost_center": root_cc,
                    "is_group": 0,
                    "company": company_name,
                })
                cc.flags.ignore_permissions = True
                cc.insert()
                frappe.db.commit()
        except Exception as e:
            frappe.db.rollback()

    # Create default warehouses
    if default_warehouse:
        try:
            wh_types = [
                {"name": "Stores", "is_group": 0},
                {"name": "Work In Progress", "is_group": 0},
                {"name": "Finished Goods", "is_group": 0},
            ]
            # Get root warehouse
            root_wh = frappe.db.get_value("Warehouse",
                {"company": company_name, "is_group": 1}, "name")
            for wh in wh_types:
                existing = frappe.db.exists("Warehouse",
                    {"company": company_name, "warehouse_name": wh["name"]})
                if existing:
                    continue
                w = frappe.get_doc({
                    "doctype": "Warehouse",
                    "warehouse_name": wh["name"],
                    "is_group": wh["is_group"],
                    "company": company_name,
                    "parent_warehouse": root_wh,
                })
                w.flags.ignore_permissions = True
                w.insert()
            frappe.db.commit()
        except Exception:
            frappe.db.rollback()

    # Create Bank Account (basic)
    try:
        if not frappe.db.exists("Bank", "Nova Ljubljanska Banka"):
            bank = frappe.get_doc({
                "doctype": "Bank",
                "bank_name": "Nova Ljubljanska Banka",
                "swift_number": "LJBASI2X",
            })
            bank.flags.ignore_permissions = True
            bank.insert()
            frappe.db.commit()

        ba = frappe.get_doc({
            "doctype": "Bank Account",
            "account_name": f"Glavni transakcijski račun - {abbr}",
            "bank": "Nova Ljubljanska Banka",
            "company": company_name,
            "is_company_account": 0,
        })
        ba.flags.ignore_permissions = True
        ba.insert()
        frappe.db.commit()
    except Exception:
        frappe.db.rollback()

    # Get final state
    accounts_count = frappe.db.count("Account", {"company": company_name})
    warehouses_count = frappe.db.count("Warehouse", {"company": company_name})

    return {
        "success": True,
        "company_name": company_name,
        "abbr": abbr,
        "tax_id": tax_id,
        "accounts_created": accounts_count,
        "warehouses_created": warehouses_count,
    }


@frappe.whitelist()
def list_slovenian_companies() -> list:
    """RPC: list all companies with Slovenian country."""
    companies = frappe.get_all("Company",
        filters={"country": "Slovenia"},
        fields=["name", "abbr", "tax_id", "default_currency", "country"])
    return companies


@frappe.whitelist()
def get_company_furs_config(company: str) -> dict:
    """RPC: get FURS configuration for a specific company.

    Per-company FURS config is stored in Site Config with company-prefixed keys.
    """
    abbr = frappe.db.get_value("Company", company, "abbr")
    return {
        "cert_path": frappe.conf.get(f"furs_cert_path_{abbr}"),
        "cert_password": frappe.conf.get(f"furs_cert_password_{abbr}"),
        "test_mode": frappe.conf.get(f"furs_test_mode_{abbr}", 1),
        "premise_id": frappe.conf.get(f"furs_premise_id_{abbr}", "PREMISE001"),
        "device_id": frappe.conf.get(f"furs_device_id_{abbr}", "DEV001"),
    }


@frappe.whitelist()
def get_consolidated_balance_sheet(from_date: str, to_date: str) -> dict:
    """RPC: get consolidated balance sheet across all Slovenian companies.

    Useful for groups of companies that need consolidated reporting.
    """
    companies = list_slovenian_companies()
    if not companies:
        return {"success": False, "error": _("Ni najdenih slovenskih podjetij.")}

    consolidated = {
        "assets": 0.0,
        "liabilities": 0.0,
        "equity": 0.0,
        "income": 0.0,
        "expenses": 0.0,
        "profit_loss": 0.0,
    }

    per_company = []
    for c in companies:
        # Get GL balances
        gl_entries = frappe.db.get_all("GL Entry",
            filters={
                "company": c["name"],
                "is_cancelled": 0,
                "posting_date": ["between", [from_date, to_date]],
            },
            fields=["account", "debit", "credit"])

        balances: dict[str, float] = {}
        for gl in gl_entries:
            acc = gl["account"]
            balances[acc] = balances.get(acc, 0) + flt(gl["debit"]) - flt(gl["credit"])

        # Get root types
        company_totals = {"assets": 0, "liabilities": 0, "equity": 0, "income": 0, "expenses": 0}
        for acc, bal in balances.items():
            root_type = frappe.db.get_value("Account", acc, "root_type")
            is_group = frappe.db.get_value("Account", acc, "is_group")
            if is_group:
                continue
            if root_type == "Asset":
                company_totals["assets"] += bal
            elif root_type == "Liability":
                company_totals["liabilities"] += bal
            elif root_type == "Equity":
                company_totals["equity"] += bal
            elif root_type == "Income":
                company_totals["income"] += bal
            elif root_type == "Expense":
                company_totals["expenses"] += bal

        company_totals["profit_loss"] = company_totals["income"] - company_totals["expenses"]
        company_totals["company"] = c["name"]
        per_company.append(company_totals)

        # Add to consolidated
        for k in ["assets", "liabilities", "equity", "income", "expenses", "profit_loss"]:
            consolidated[k] += company_totals[k]

    return {
        "success": True,
        "companies": per_company,
        "consolidated": consolidated,
        "from_date": from_date,
        "to_date": to_date,
    }


def flt(value):
    """Float conversion."""
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0
