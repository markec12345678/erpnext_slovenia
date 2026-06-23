"""
QR code image generator for Slovenian payment orders (UPN QR).

Uses the qrcode Python library to render an actual PNG image that can be:
1. Saved as a File attachment on the Sales Invoice
2. Returned as base64-encoded data URL for inline embedding in Print Formats
3. Streamed as a downloadable PNG

The QR code follows Banka Slovenije UPN QR standard:
  - 19 fields, terminated by newlines
  - Header "UPNQR"
  - Control sum (5 digits) at the end
"""
import base64
import io
import frappe

import qrcode
from qrcode.constants import ERROR_CORRECT_M

from erpnext_slovenia.upn_qr.upn_qr import (
    generate_upn_qr_payload,
    get_upn_qr_payload_for_invoice,
)
from frappe.utils.file_manager import save_file


def render_upn_qr_png(payload: str, size_px: int = 300, border: int = 1) -> bytes:
    """Render a UPN QR payload as a PNG image.

    Args:
        payload: The UPN QR payload string (from generate_upn_qr_payload)
        size_px: Target image size in pixels (square)
        border: QR quiet zone (in modules, typically 1-4)

    Returns:
        PNG image bytes
    """
    qr = qrcode.QRCode(
        version=None,  # auto-detect smallest version that fits
        error_correction=ERROR_CORRECT_M,  # ~15% error correction
        box_size=10,
        border=border,
    )
    qr.add_data(payload)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    # Resize to exact target size
    if img.size != (size_px, size_px):
        # Use Pillow's Image.LANCZOS for high quality resampling (NEAREST is removed in newer Pillow)
        from PIL import Image
        try:
            resample = Image.Resampling.LANCZOS
        except AttributeError:
            resample = Image.LANCZOS  # Pillow < 9.1
        img = img.resize((size_px, size_px), resample)

    # Convert to PNG bytes
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()


def render_upn_qr_base64(payload: str, size_px: int = 300) -> str:
    """Render UPN QR as base64-encoded data URL (for inline HTML embedding)."""
    png_bytes = render_upn_qr_png(payload, size_px=size_px)
    b64 = base64.b64encode(png_bytes).decode("ascii")
    return f"data:image/png;base64,{b64}"


@frappe.whitelist()
def get_upn_qr_base64_for_invoice(sales_invoice_name: str, size_px: int = 300) -> str:
    """RPC: return UPN QR as base64 data URL for a Sales Invoice."""
    payload = get_upn_qr_payload_for_invoice(sales_invoice_name)
    return render_upn_qr_base64(payload, size_px=size_px)


@frappe.whitelist()
def attach_upn_qr_png(sales_invoice_name: str, size_px: int = 300) -> dict:
    """RPC: generate UPN QR PNG and attach it to the Sales Invoice.

    Returns dict with file URL and metadata.
    """
    payload = get_upn_qr_payload_for_invoice(sales_invoice_name)
    png_bytes = render_upn_qr_png(payload, size_px=size_px)

    file_name = f"UPN_QR_{sales_invoice_name}.png"

    # Remove old attachment if exists
    existing = frappe.db.exists("File", {
        "attached_to_doctype": "Sales Invoice",
        "attached_to_name": sales_invoice_name,
        "file_name": file_name,
    })
    if existing:
        frappe.delete_doc("File", existing, force=True)

    f = save_file(
        fname=file_name,
        content=png_bytes,
        dt="Sales Invoice",
        dn=sales_invoice_name,
        folder=None,
        is_private=0,
        df=None,
    )
    frappe.db.commit()

    return {
        "file_url": f.file_url,
        "file_name": f.file_name,
        "file_size": f.file_size,
        "payload": payload,
    }


def generate_qr_for_print_format(sales_invoice_name: str, size_px: int = 200) -> str:
    """Helper used by Jinja Print Format to embed QR as base64 data URL.

    Usage in Print Format HTML:
        <img src="{{ frappe.utils.get_attr("erpnext_slovenia.qr_image.qr_image.generate_qr_for_print_format")(doc.name) }}"
             alt="UPN QR" />
    """
    try:
        payload = get_upn_qr_payload_for_invoice(sales_invoice_name)
        return render_upn_qr_base64(payload, size_px=size_px)
    except Exception as e:
        frappe.log_error(f"QR generation failed for {sales_invoice_name}: {e}")
        return ""
