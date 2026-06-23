"""Debug tax fields."""
import frappe


def main():
    inv = "ACC-SINV-2026-00001"
    taxes = frappe.get_all("Sales Taxes and Charges",
        filters={"parent": inv},
        fields=["*"])
    print(f">>> Found {len(taxes)} tax rows for {inv}")
    for t in taxes:
        for k, v in t.items():
            print(f"  {k}: {v}")
        print("---")
