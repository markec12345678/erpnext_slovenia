"""
Hooks for erpnext_slovenia app.
"""
from . import __version__ as app_version  # noqa


app_name = "erpnext_slovenia"
app_title = "Erpnext Slovenia"
app_publisher = "Z.ai"
app_description = "Slovenian localization for ERPNext"
app_email = "zai@example.com"
app_license = "MIT"

# CSS / JS includes
app_include_css = "/assets/erpnext_slovenia/css/slovenia.css"
app_include_js = "/assets/erpnext_slovenia/js/slovenia.js"

# DocType events
doc_events = {
    "Sales Invoice": {
        "on_submit": [
            "erpnext_slovenia.einvoice.einvoice.attach_eslog_xml",
            "erpnext_slovenia.qr_image.qr_image.attach_upn_qr_png",  # auto-attach UPN QR PNG
        ],
        "on_trash": "erpnext_slovenia.einvoice.einvoice.remove_eslog_xml",
    },
    "Customer": {
        "validate": [
            "erpnext_slovenia.utils.validate_tax_id",
        ],
    },
    "Supplier": {
        "validate": "erpnext_slovenia.utils.validate_tax_id",
    },
}

# Setup
after_install = "erpnext_slovenia.setup.after_install"

# Fixtures
fixtures = [
    {"dt": "Custom Field", "filters": [["name", "like", "Customer-tax_id_%"]]},
    {"dt": "Custom Field", "filters": [["name", "like", "Supplier-tax_id_%"]]},
    {"dt": "Custom Field", "filters": [["name", "like", "Customer-custom_si_%"]]},
    {"dt": "Print Format", "filters": [["name", "=", "Slovenski Račun"]]},
    {"dt": "Report", "filters": [["name", "in", ["DDV Obračun", "DDV-VP Letno Poročilo", "RAČ Letni Izkaz"]]]},
]
