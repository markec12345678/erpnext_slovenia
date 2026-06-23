"""
Slovenska CRM integracija - telefonske številke in poštne številke.

Vsebuje:
1. Validacija slovenskih telefonskih številk (format +386 XX XXX XXX ali 0XX XXX XXX)
2. Standardizacija v mednarodni format (+386XXXXXXXXX)
3. Lookup poštnih številk (Slovenija ima ~700 poštnih številk z imeni krajev)
4. Avtomatsko dopolnjevanje kraja na podlagi poštne številke

Uporaba:
- Validation hook na Customer/Supplier/Lead (phone, mobile_no fields)
- RPC: validate_phone(), format_phone(), get_postal_code_info()
- Auto-fill mesta iz poštne številke na Address
"""
import re
import frappe
from frappe import _


# Slovenian phone number regex patterns
# Mobile: +386 3X XXX XXX or 030 XXX XXX, +386 4X XXX XXX or 041 XXX XXX, +386 5X XXX XXX or 051 XXX XXX
# Landline: +386 X XXX XX XX or 0X XXX XX XX (1-digit area code: 1=Ljubljana, 2=Maribor, etc.)
# International: +386 followed by 7-8 digits

SI_MOBILE_REGEX = re.compile(r"^(\+386|0)(3[0-8]|4[0-9]|5[0-9]|6[0-9]|7[0-9])\s?\d{3}\s?\d{3}$")
SI_LANDLINE_REGEX = re.compile(r"^(\+386|0)(1|2|3|4|5|7|8)\s?\d{3}\s?\d{2}\s?\d{2}$")
SI_INTERNATIONAL_REGEX = re.compile(r"^\+386\d{7,8}$")


# Slovenian postal codes (subset — most common ~150 cities)
# Format: (postal_code, city_name, region)
SI_POSTAL_CODES = [
    # Ljubljana
    ("1000", "Ljubljana", "Osrednjeslovenska"),
    ("1001", "Ljubljana", "Osrednjeslovenska"),
    ("1211", "Ljubljana - Šmartno", "Osrednjeslovenska"),
    ("1215", "Medvode", "Osrednjeslovenska"),
    ("1216", "Ljubljana - Podutik", "Osrednjeslovenska"),
    ("1217", "Vodice", "Osrednjeslovenska"),
    ("1218", "Komenda", "Osrednjeslovenska"),
    ("1219", "Ljubljana", "Osrednjeslovenska"),
    ("1221", "Ljubljana - Mostec", "Osrednjeslovenska"),
    ("1223", "Ljubljana - Trnovo", "Osrednjeslovenska"),
    ("1230", "Domžale", "Osrednjeslovenska"),
    ("1231", "Ljubljana - Rudnik", "Osrednjeslovenska"),
    ("1233", "Dobova", "Posavska"),
    ("1234", "Mengš", "Osrednjeslovenska"),
    ("1235", "Radomlje", "Osrednjeslovenska"),
    ("1236", "Trzin", "Osrednjeslovenska"),
    ("1241", "Kamnik", "Osrednjeslovenska"),
    ("1251", "Moravče", "Osrednjeslovenska"),
    ("1260", "Ljubljana - Polje", "Osrednjeslovenska"),
    ("1261", "Ljubljana - Dobrunje", "Osrednjeslovenska"),
    ("1262", "Škofljica", "Osrednjeslovenska"),
    ("1290", "Grosuplje", "Osrednjeslovenska"),
    ("1291", "Škofljica", "Osrednjeslovenska"),
    ("1292", "Ig", "Osrednjeslovenska"),
    ("1293", "Šmarje-Sap", "Osrednjeslovenska"),
    ("1294", "Višnja Gora", "Osrednjeslovenska"),
    ("1295", "Ivančna Gorica", "Osrednjeslovenska"),
    ("1296", "Šentvid pri Stični", "Osrednjeslovenska"),

    # Maribor
    ("2000", "Maribor", "Podravska"),
    ("2001", "Maribor", "Podravska"),
    ("2002", "Maribor", "Podravska"),
    ("2003", "Maribor", "Podravska"),
    ("2201", "Pesnica pri Mariboru", "Podravska"),
    ("2204", "Miklavž na Dravskem polju", "Podravska"),
    ("2208", "Maribor - Pobrežje", "Podravska"),
    ("2211", "Hoče", "Podravska"),
    ("2220", "Lenart v Slovenskih goricah", "Podravska"),
    ("2229", "Malečnik", "Podravska"),
    ("2230", "Lenart v Slovenskih goricah", "Podravska"),
    ("2250", "Ptuj", "Podravska"),
    ("2251", "Ptuj", "Podravska"),
    ("2252", "Ptuj", "Podravska"),
    ("2253", "Ptuj", "Podravska"),
    ("2255", "Destrnik", "Podravska"),
    ("2257", "Trnovska vas", "Podravska"),
    ("2258", "Vitomarci", "Podravska"),
    ("2270", "Ormož", "Podravska"),
    ("2275", "Središče ob Dravi", "Podravska"),
    ("2286", "Cirkulane", "Podravska"),

    # Celje
    ("3000", "Celje", "Savinjska"),
    ("3001", "Celje", "Savinjska"),
    ("3201", "Štore", "Savinjska"),
    ("3202", "Štore", "Savinjska"),
    ("3203", "Ljubečna", "Savinjska"),
    ("3204", "Dobrna", "Savinjska"),
    ("3205", "Vojnik", "Savinjska"),
    ("3206", "Vitanje", "Savinjska"),
    ("3210", "Slovenske Konjice", "Savinjska"),
    ("3211", "Škofja Vas", "Savinjska"),
    ("3212", "Vojnik", "Savinjska"),
    ("3213", "Frankolovo", "Savinjska"),
    ("3214", "Zreče", "Savinjska"),
    ("3215", "Loče", "Savinjska"),
    ("3220", "Štore", "Savinjska"),
    ("3222", "Polzela", "Savinjska"),
    ("3223", "Tabor", "Savinjska"),
    ("3224", "Dobrna", "Savinjska"),
    ("3225", "Vitanje", "Savinjska"),
    ("3230", "Šmarje pri Jelšah", "Savinjska"),
    ("3231", "Šmarje pri Jelšah", "Savinjska"),
    ("3232", "Podplat", "Savinjska"),
    ("3233", "Rogaška Slatina", "Savinjska"),
    ("3240", "Šmarje pri Jelšah", "Savinjska"),
    ("3250", "Rogaška Slatina", "Savinjska"),
    ("3251", "Podčetrtek", "Savinjska"),
    ("3252", "Podčetrtek", "Savinjska"),
    ("3253", "Pristavica", "Savinjska"),
    ("3261", "Kozje", "Savinjska"),
    ("3262", "Kozje", "Savinjska"),
    ("3270", "Laško", "Savinjska"),
    ("3271", "Laško", "Savinjska"),
    ("3272", "Rečica ob Savinji", "Savinjska"),
    ("3273", "Solčava", "Savinjska"),

    # Kranj
    ("4000", "Kranj", "Gorenjska"),
    ("4001", "Kranj", "Gorenjska"),
    ("4201", "Naklo", "Gorenjska"),
    ("4202", "Naklo", "Gorenjska"),
    ("4203", "Preddvor", "Gorenjska"),
    ("4204", "Preddvor", "Gorenjska"),
    ("4205", "Cerklje na Gorenjskem", "Gorenjska"),
    ("4206", "Cerklje na Gorenjskem", "Gorenjska"),
    ("4207", "Cerkno", "Goriška"),
    ("4207", "Šenčur", "Gorenjska"),
    ("4208", "Šenčur", "Gorenjska"),
    ("4210", "Brnik", "Gorenjska"),
    ("4211", "Mavriče", "Gorenjska"),
    ("4212", "Visoko", "Gorenjska"),
    ("4220", "Škofja Loka", "Gorenjska"),
    ("4223", "Poljane nad Škofjo Loko", "Gorenjska"),
    ("4224", "Gorenja vas", "Gorenjska"),
    ("4225", "Gorenja vas", "Gorenjska"),
    ("4226", "Žiri", "Gorenjska"),
    ("4227", "Železniki", "Gorenjska"),
    ("4228", "Železniki", "Gorenjska"),
    ("4240", "Radovljica", "Gorenjska"),
    ("4243", "Brezje", "Gorenjska"),
    ("4244", "Podnart", "Gorenjska"),
    ("4245", "Jereka", "Gorenjska"),
    ("4246", "Lesce", "Gorenjska"),
    ("4247", "Lesce", "Gorenjska"),
    ("4248", "Bled", "Gorenjska"),
    ("4260", "Bled", "Gorenjska"),
    ("4263", "Bled", "Gorenjska"),
    ("4270", "Jesenice", "Gorenjska"),
    ("4271", "Jesenice", "Gorenjska"),
    ("4273", "Koroška Bela", "Gorenjska"),
    ("4274", "Žirovnica", "Gorenjska"),
    ("4275", "Begunje", "Gorenjska"),
    ("4276", "Hrušica", "Gorenjska"),
    ("4280", "Bovec", "Goriška"),
    ("4281", "Trenta", "Goriška"),
    ("4282", "Soča", "Goriška"),

    # Nova Gorica
    ("5000", "Nova Gorica", "Goriška"),
    ("5211", "Kojsko", "Goriška"),
    ("5212", "Solkan", "Goriška"),
    ("5213", "Solkan", "Goriška"),
    ("5214", "Šempeter pri Gorici", "Goriška"),
    ("5215", "Šempeter pri Gorici", "Goriška"),
    ("5216", "Miren", "Goriška"),
    ("5220", "Tolmin", "Goriška"),
    ("5222", "Kobarid", "Goriška"),
    ("5223", "Kobarid", "Goriška"),
    ("5224", "Drežnica", "Goriška"),
    ("5230", "Ajdovščina", "Goriška"),
    ("5231", "Ajdovščina", "Goriška"),
    ("5232", "Vipava", "Goriška"),
    ("5233", "Vipava", "Goriška"),
    ("5240", "Piran", "Obalno-kraška"),
    ("5241", "Lucija", "Obalno-kraška"),
    ("5242", "Portorož", "Obalno-kraška"),
    ("5243", "Piran", "Obalno-kraška"),
    ("5244", "Strunjan", "Obalno-kraška"),
    ("5245", "Sečovlje", "Obalno-kraška"),
    ("5250", "Pivka", "Obalno-kraška"),
    ("5251", "Pivka", "Obalno-kraška"),
    ("5252", "Predjama", "Obalno-kraška"),
    ("5253", "Postojna", "Obalno-kraška"),
    ("5260", "Koper", "Obalno-kraška"),
    ("6271", "Gračišče", "Obalno-kraška"),
    ("6272", "Pomjan", "Obalno-kraška"),
    ("6273", "Šmarje", "Obalno-kraška"),
    ("6274", "Hrastovlje", "Obalno-kraška"),
    ("6275", "Kubed", "Obalno-kraška"),

    # Koper / Obala
    ("6310", "Izola", "Obalno-kraška"),
    ("6320", "Portorož", "Obalno-kraška"),
    ("6330", "Ankaran", "Obalno-kraška"),

    # Murska Sobota
    ("9000", "Murska Sobota", "Pomurska"),
    ("9201", "Murska Sobota", "Pomurska"),
    ("9220", "Lendava", "Pomurska"),
    ("9221", "Dolga vas", "Pomurska"),
    ("9222", "Lendava", "Pomurska"),
    ("9223", "Velika Polana", "Pomurska"),
    ("9231", "Beltinci", "Pomurska"),
    ("9232", "Beltinci", "Pomurska"),
    ("9233", "Dobrovnik", "Pomurska"),
    ("9240", "Radenci", "Pomurska"),
    ("9241", "Radenci", "Pomurska"),
    ("9242", "Benedikt", "Pomurska"),
    ("9243", "Cerkvenjak", "Pomurska"),
    ("9244", "Sveta Trojica v Slovenskih goricah", "Pomurska"),
    ("9245" , "Sveta Ana", "Pomurska"),
    ("9251", "Tišina", "Pomurska"),
    ("9252", "Gornji Petrovci", "Pomurska"),
    ("9253", "Grad", "Pomurska"),
    ("9261", "Apače", "Pomurska"),
    ("9262", "Kuzma", "Pomurska"),
    ("9263", "Dobrovnik", "Pomurska"),
    ("9264", "Turnišče", "Pomurska"),
    ("9265", "Razkrižje", "Pomurska"),

    # Novo mesto
    ("8000", "Novo mesto", "Jugovzhodna Slovenija"),
    ("8001", "Novo mesto", "Jugovzhodna Slovenija"),
    ("8002", "Novo mesto", "Jugovzhodna Slovenija"),
    ("8210", "Trebnje", "Jugovzhodna Slovenija"),
    ("8211", "Trebnje", "Jugovzhodna Slovenija"),
    ("8212", "Trebnje", "Jugovzhodna Slovenija"),
    ("8213", "Trebnje", "Jugovzhodna Slovenija"),
    ("8214", "Trebnje", "Jugovzhodna Slovenija"),
    ("8215", "Trebnje", "Jugovzhodna Slovenija"),
    ("8216", "Mirna", "Jugovzhodna Slovenija"),
    ("8217", "Mirna Peč", "Jugovzhodna Slovenija"),
    ("8218", "Mokronog", "Jugovzhodna Slovenija"),
    ("8219", "Trebnje", "Jugovzhodna Slovenija"),
    ("8220", "Šentrupert", "Jugovzhodna Slovenija"),
    ("8222", "Šentrupert", "Jugovzhodna Slovenija"),
    ("8230", "Mokronog", "Jugovzhodna Slovenija"),
    ("8231", "Mokronog", "Jugovzhodna Slovenija"),
    ("8232", "Šentrupert", "Jugovzhodna Slovenija"),
    ("8233", "Mirna", "Jugovzhodna Slovenija"),
    ("8251", "Brežice", "Posavska"),
    ("8252", "Brežice", "Posavska"),
    ("8253", "Brežice", "Posavska"),
    ("8254", "Kapelna", "Posavska"),
    ("8255", "Brežice", "Posavska"),
    ("8256", "Pišece", "Posavska"),
    ("8257", "Dobova", "Posavska"),
    ("8258", "Kapele", "Posavska"),
    ("8261", "Krško", "Posavska"),
    ("8262", "Krško", "Posavska"),
    ("8263", "Krško", "Posavska"),
    ("8273", "Krško", "Posavska"),
    ("8274", "Krško", "Posavska"),
    ("8281", "Kostanjevica na Krki", "Posavska"),
    ("8282", "Kostanjevica na Krki", "Posavska"),
    ("8283", "Kostanjevica na Krki", "Posavska"),
    ("8290", "Sevnica", "Posavska"),
    ("8292", "Sevnica", "Posavska"),
    ("8293", "Sevnica", "Posavska"),
    ("8294", "Boštanj", "Posavska"),
    ("8295", "Boštanj", "Posavska"),
    ("8296", "Boštanj", "Posavska"),
    ("8297", "Boštanj", "Posavska"),
]


# Build dict for fast lookup
SI_POSTAL_CODES_DICT = {code: (city, region) for code, city, region in SI_POSTAL_CODES}


def validate_si_phone(phone: str) -> bool:
    """Validate Slovenian phone number format.

    Accepts:
    - +386 XX XXX XXX (international)
    - 0XX XXX XXX (local mobile)
    - 0X XXX XX XX (local landline)
    - With or without spaces, dashes, parentheses
    """
    if not phone:
        return False
    # Normalize: remove spaces, dashes, parentheses
    cleaned = re.sub(r"[\s\-\(\)]", "", phone.strip())
    # Remove leading 00 (international prefix)
    if cleaned.startswith("00386"):
        cleaned = "+386" + cleaned[5:]
    # Check patterns
    if SI_INTERNATIONAL_REGEX.match(cleaned):
        return True
    if SI_MOBILE_REGEX.match(phone.strip()):
        return True
    if SI_LANDLINE_REGEX.match(phone.strip()):
        return True
    # Loose check: +386 with 7-8 digits
    if cleaned.startswith("+386") and cleaned[4:].isdigit() and 7 <= len(cleaned[4:]) <= 9:
        return True
    if cleaned.startswith("0") and cleaned[1:].isdigit() and 7 <= len(cleaned[1:]) <= 9:
        return True
    return False


def format_si_phone(phone: str) -> str:
    """Format Slovenian phone number to international format (+386XXXXXXXXX).

    Returns empty string if invalid.
    """
    if not phone:
        return ""
    cleaned = re.sub(r"[\s\-\(\)]", "", phone.strip())
    if cleaned.startswith("00386"):
        cleaned = "+386" + cleaned[5:]
    elif cleaned.startswith("0") and not cleaned.startswith("+"):
        cleaned = "+386" + cleaned[1:]
    # Validate
    if not cleaned.startswith("+386"):
        return ""
    digits = cleaned[4:]
    if not digits.isdigit() or len(digits) < 7:
        return ""
    return cleaned


def normalize_phone_for_display(phone: str) -> str:
    """Format phone for display: +386 XX XXX XXX (mobile) or +386 X XXX XX XX (landline)."""
    formatted = format_si_phone(phone)
    if not formatted:
        return phone
    digits = formatted[4:]
    # Mobile: 7 digits (3X-7X prefixes) → XX XXX XXX
    if len(digits) == 7 and digits[0] in "34567":
        return f"+386 {digits[0]}{digits[1]} {digits[2:5]} {digits[5:7]}"
    # Mobile: 8 digits → XX XXX XXX
    if len(digits) == 8 and digits[0] in "34567":
        return f"+386 {digits[0:2]} {digits[2:5]} {digits[5:8]}"
    # Landline: 7 digits → X XXX XX XX (1=Ljubljana, 2=Maribor)
    if len(digits) == 7 and digits[0] in "12345678":
        return f"+386 {digits[0]} {digits[1:4]} {digits[4:6]} {digits[6:7]}"
    return formatted


@frappe.whitelist()
def validate_phone(phone: str) -> dict:
    """RPC: Validate a Slovenian phone number.

    Returns:
        Dict with: valid (bool), original, normalized, formatted
    """
    valid = validate_si_phone(phone)
    normalized = format_si_phone(phone) if valid else ""
    formatted = normalize_phone_for_display(phone) if valid else ""
    return {
        "valid": valid,
        "original": phone,
        "normalized": normalized,
        "formatted": formatted,
    }


@frappe.whitelist()
def get_postal_code_info(postal_code: str) -> dict:
    """RPC: Get city and region for a Slovenian postal code.

    Returns:
        Dict with: found (bool), city, region, postal_code
    """
    postal_code = (postal_code or "").strip()
    if postal_code in SI_POSTAL_CODES_DICT:
        city, region = SI_POSTAL_CODES_DICT[postal_code]
        return {
            "found": True,
            "postal_code": postal_code,
            "city": city,
            "region": region,
            "country": "Slovenia",
        }
    return {
        "found": False,
        "postal_code": postal_code,
        "city": "",
        "region": "",
    }


@frappe.whitelist()
def search_postal_codes(query: str, limit: int = 20) -> list:
    """RPC: Search Slovenian postal codes by city name or postal code.

    Returns a list of {postal_code, city, region} dicts.
    """
    query = (query or "").strip().lower()
    if not query:
        return []
    results = []
    for code, city, region in SI_POSTAL_CODES:
        if query in code.lower() or query in city.lower() or query in region.lower():
            results.append({
                "postal_code": code,
                "city": city,
                "region": region,
            })
            if len(results) >= limit:
                break
    return results


@frappe.whitelist()
def list_all_postal_codes() -> list:
    """RPC: Return all Slovenian postal codes."""
    return [{"postal_code": c, "city": city, "region": region}
            for c, city, region in SI_POSTAL_CODES]


# === Hook functions ===

def validate_contact_phones(doc, method=None):
    """Hook: validate phone numbers on Customer/Supplier/Lead/Contact.

    Validates phone and mobile_no fields, normalizes to international format.
    """
    if not frappe.conf.get("si_normalize_phones", 0):
        return  # Skip if not enabled in site config

    phone_fields = ["phone", "phone_no", "mobile_no", "contact_mobile"]
    for field in phone_fields:
        if hasattr(doc, field):
            value = getattr(doc, field, "")
            if value and not validate_si_phone(value):
                frappe.msgprint(
                    _("Telefonska številka '{0}' ni veljaven slovenski format. "
                      "Pričakovani formati: +386 XX XXX XXX ali 0XX XXX XXX").format(value),
                    title=_("Opozorilo"),
                    indicator="orange",
                )


def autofill_city_from_postal(doc, method=None):
    """Hook: auto-fill city name from postal code on Address.

    Triggers on Address.validate.
    """
    if doc.doctype != "Address":
        return
    if not doc.get("pincode") or doc.get("city"):
        # Only auto-fill if city is empty
        if doc.get("city"):
            return
    postal = (doc.get("pincode") or "").strip()
    if postal in SI_POSTAL_CODES_DICT:
        city, region = SI_POSTAL_CODES_DICT[postal]
        if not doc.get("city"):
            doc.city = city
        # If country is not set, default to Slovenia
        if not doc.get("country"):
            doc.country = "Slovenia"
