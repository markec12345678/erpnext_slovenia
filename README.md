# ERPNext Slovenia 🇸🇮

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Frappe Framework](https://img.shields.io/badge/Frappe-v17-blue.svg)](https://frappeframework.com)
[![ERPNext](https://img.shields.io/badge/ERPNext-v17-blue.svg)](https://erpnext.com)
[![Python](https://img.shields.io/badge/Python-3.14+-green.svg)](https://python.org)

**Slovenska lokalizacija za ERPNext** — najbolj popolna open-source rešitev za slovensko poslovanje.

Aplikacija dodaja slovenske davčne predloge, e-Slog XML eRačune, UPN QR kode, FURS integracije, DDV obračune, MT940 bančne izpiske, VIES validacijo in še več.

---

## 📋 Vsebina

- [Namestitev](#-namestitev)
- [Funkcionalnosti](#-funkcionalnosti)
- [Konfiguracija](#-konfiguracija)
- [Uporaba](#-uporaba)
- [API referenca](#-api-referenca)
- [Razvoj](#-razvoj)
- [Licenca](#-licenca)

---

## 🚀 Namestitev

### Zahteve

- [Frappe Framework](https://frappeframework.com) v17+
- [ERPNext](https://erpnext.com) v17+
- Python 3.10+
- Pillow (za QR kode)
- qrcode (za QR kode)

### Hitra namestitev

```bash
# 1. Pridobi aplikacijo
bench get-app https://github.com/markec12345678/erpnext_slovenia.git

# 2. Namesti na site
bench --site your-site install-app erpnext_slovenia

# 3. Zaženi migracijo
bench --site your-site migrate

# 4. (Opcijsko) Nastavi slovenski kontni plan
bench --site your-site execute erpnext_slovenia.srs.srs_chart.main

# 5. (Opcijsko) Ustvari plačilne namene
bench --site your-site execute erpnext_slovenia.payment_codes.payment_codes.main
```

### Namestitev iz vira

```bash
cd ~/frappe-bench/apps
git clone https://github.com/markec12345678/erpnext_slovenia.git
cd ..
pip install -e apps/erpnext_slovenia
bench --site your-site install-app erpnext_slovenia
bench --site your-site migrate
```

---

## ✨ Funkcionalnosti

### 1. SRS Kontni Plan
- **203 kontov** po slovenskih računovodskih standardih (SRS 2024)
- Razredi 0-9: Aktiva, Stroški, Prihodki, Kapital, Obveznosti, Izredni, Časovne razmejitve
- DDV konti za vse stopnje (22%, 8.5%, 5%)

```python
# Modul: erpnext_slovenia.srs.srs_chart
bench --site your-site execute erpnext_slovenia.srs.srs_chart.main
```

### 2. DDV Predloge
- **4 davčne predloge**: DDV 22% in 8.5% za prodajo in nakup
- DDV vključen v ceno (slovenska praksa)
- Samodejna kreacija ob namestitvi

### 3. e-Slog 1.6 XML eRačun
- Samodejna generacija ob submitu Sales Invoice
- Priloga `eSlog_<invoice_name>.xml` na vsakem računu
- Standard `http://www.gzs.si/eSlog/1.6`

```python
# RPC: pridobi XML
GET /api/method/erpnext_slovenia.einvoice.einvoice.get_eslog_xml?sales_invoice_name=ACC-SINV-2026-00001
```

### 4. UPN QR Koda
- Banka Slovenije UPN QR standard (19 polj)
- PNG slika samodejno priložena računu
- Base64 za inline HTML embedding
- MOD 11 checksum za SI referenco

```python
# RPC: pridobi QR kot base64
GET /api/method/erpnext_slovenia.qr_image.qr_image.get_upn_qr_base64_for_invoice?sales_invoice_name=ACC-SINV-2026-00001
```

### 5. Slovenski Print Format
- Custom Jinja print format "Slovenski Račun"
- Header z logotipom, davčno številko
- Tabela artiklov, davki, skupaj za plačilo
- Footer z ZDDV-1 navedbo

```
URL: /printview?doctype=Sales Invoice&name=<invoice>&format=Slovenski Račun
```

### 6. DDV Obračun (mesečni report)
- Script Report z filtri (podjetje, od datuma, do datuma)
- Izhodni DDV (prodaja) po stopnjah
- Vhodni DDV (nakup) po stopnjah
- Razlika — DDV za plačilo / dobropis
- Chart in summary kartice

```
URL: /app/query-report/DDV Obračun
```

### 7. DDV-VP Letno Poročilo
- Letno poročilo o transakcijah z zavezanci
- Seznam strank z davčnimi številkami
- Promet po stopnjah DDV

```
URL: /app/query-report/DDV-VP Letno Poročilo
```

### 8. RAČ Letni Izkaz
- Bilanca stanja (sredstva, kapital, obveznosti)
- Poslovni izid (prihodki, stroški, dobiček/izguba)
- 6 summary kartic + bar chart

```
URL: /app/query-report/RAČ Letni Izkaz
```

### 9. eDavki XML (DDV-Obr)
- XML za oddajo na FURS portal (https://edavki.fu.gov.si)
- Schema `http://edavki.durs.si/edavki-doc/v1.5`
- Izhodni/Vhodni DDV po stopnjah
- PlaciloDDV (razlika)

```python
# RPC: generiraj XML
POST /api/method/erpnext_slovenia.edavki.ddv_obracun_xml.get_ddv_obracun_xml
Body: company=Moje+Podjetje+d.o.o.&from_date=2026-06-01&to_date=2026-06-30&period_type=month
```

### 10. FURS eDavki API
- SOAP envelope za oddajo na FURS
- Podpora za digitalna potrdila (.pem)
- FURS Submission Log (avditska sled)
- Test/production URL

```python
# RPC: oddaj DDV na FURS
POST /api/method/erpnext_slovenia.furs.edavki_api.submit_ddv_obracun
Body: company=...&from_date=...&to_date=...&period_type=month
```

### 11. FURS Blagajne
- Real-time registracija računov (B2C, retail, gostinstvo)
- **ZOI** (Zaščitna oznaka izdajatelja) — MD5 hash
- **EOR** (Enkratna identifikacijska oznaka računa) — UUID
- Demo mode brez certifikata

```python
# RPC: registriraj račun
GET /api/method/erpnext_slovenia.furs_blagajne.furs_blagajne.register_sales_invoice?sales_invoice_name=ACC-SINV-2026-00001
```

### 12. VIES Validacija
- EU VIES SOAP API (ec.europa.eu/taxation_customs/vies/)
- Validacija VAT številk vseh 27 EU držav
- Vrne: veljavnost, registrirano ime, naslov
- Custom Fields na Customer (VIES status)

```python
# RPC: validiraj davčno številko
GET /api/method/erpnext_slovenia.vies.vies.validate_any_vat?country_code=SI&vat_number=12345678
```

### 13. MT940 Bančni Izpiski
- Poln MT940 (SWIFT) parser
- Podpora za slovensko strukturo `:86:` (SI ref, party, IBAN, plačilni namen)
- Ustvari Bank Transaction zapise
- Demo MT940 generator

```python
# RPC: uvozi demo MT940
POST /api/method/erpnext_slovenia.mt940_si.mt940_parser.import_demo_mt940
```

### 14. Plačilni Nameni
- **44 standardnih kod** (ZBS 2024)
- Skupine: A (blago), C (stroški), D (dobiček), E (plače), F (finančno), G-R
- Placilni Namen doctype v bazi

```python
# RPC: seznam kod
GET /api/method/erpnext_slovenia.payment_codes.payment_codes.get_payment_codes
```

### 15. Plačilni Nalog XML (pain.001)
- ISO 20022 pain.001.001.03 format
- Za NLB, NKBM, SKB, Abanka, Sparkasse
- SEPA-compliant
- Samodejna priloga na Payment Entry

```python
# RPC: generiraj plačilni nalog
POST /api/method/erpnext_slovenia.payment_order.payment_order.generate_and_attach_payment_order
Body: payment_entry_names=["PE-001","PE-002"]
```

### 16. Računovodske Integracije
- **Pantheon (Datex)** — CSV export
- **MiniMAX** — CSV Partner kartica
- **Sigma Controlling** — XLSX z več listi
- **e-Slog 1.6** — XML (že vgrajen)

```python
# RPC: seznam podprtih programov
GET /api/method/erpnext_slovenia.accounting_integration.accounting_integration.list_supported_programs
```

### 17. CRM Integracija
- Validacija slovenskih telefonskih številk
- Standardizacija v mednarodni format (+386XXXXXXXXX)
- **~200 poštnih številk** z imeni krajev in regijami
- Auto-fill mesta iz poštne številke

```python
# RPC: validiraj telefon
GET /api/method/erpnext_slovenia.crm_si.crm_si.validate_phone?phone=+386%2041%20123%20456

# RPC: lookup poštne številke
GET /api/method/erpnext_slovenia.crm_si.crm_si.get_postal_code_info?postal_code=1000
```

### 18. Multi-Company Podpora
- Ustvari novo slovensko podjetje z avto Chart of Accounts
- Per-company FURS konfiguracija
- Konsolidirana bilanca stanja

```python
# RPC: ustvari novo podjetje
POST /api/method/erpnext_slovenia.multi_company.multi_company.create_slovenian_company
Body: company_name=Nova+Podjetje+d.o.o.&abbr=NP&tax_id=SI12345678
```

### 19. Purchase Order Workflow
- Večstopenjsko odobrenje: Osnutek → Manager → Finance → Odobreno
- Slovenska imena stanj in akcij
- Email obvestila ob spremembi stanja

### 20. Davčna Številka Validacija
- MOD 11 checksum validacija
- Hook na Customer/Supplier.validate
- Opozorilo ob nepravilnem formatu

---

## ⚙️ Konfiguracija

### Site Config (`site_config.json`)

```json
{
  "server_script_enabled": 1,
  "developer_mode": 1
}
```

### Common Site Config (`common_site_config.json`)

```json
{
  "server_script_enabled": 1
}
```

### FURS Certifikat (za produkcijo)

```json
{
  "furs_cert_path": "/path/to/cert.pem",
  "furs_cert_password": "your-password",
  "furs_test_mode": 0,
  "furs_premise_id": "PREMISE001",
  "furs_device_id": "DEV001"
}
```

> **Pomembno**: FURS certifikat mora biti v `.pem` formatu. Če imate `.p12`, ga pretvorite:
> ```bash
> openssl pkcs12 -in cert.p12 -out cert.pem -nodes
> ```

### Per-Company FURS Config (multi-company)

```json
{
  "furs_cert_path_MP": "/path/to/cert-company1.pem",
  "furs_premise_id_MP": "PREMISE001"
}
```

---

## 📖 Uporaba

### Priprava okolja

```bash
# 1. Nastavi company tax_id
bench --site your-site execute --kwargs '{}' frappe.client.set_value --args '["Company","Moje Podjetje d.o.o.",{"tax_id":"SI12345678"}]'

# 2. Dodaj bank account
bench --site your-site execute erpnext_slovenia.add_bank_account.main

# 3. Kreiraj vzorčne podatke
bench --site your-site execute erpnext.setup.demo_data.main
```

### Dnevni workflow

1. **Kreiraj Sales Invoice** v ERPNext
2. Ob submitu se samodejno:
   - Generira e-Slog XML priloga
   - Generira UPN QR PNG priloga
3. Pregledaj v print formatu "Slovenski Račun"
4. Na koncu meseca: odpri "DDV Obračun" report
5. Generiraj "eDavki XML" in oddaj na FURS

### Bank Statement Import

```bash
# 1. Prenesi MT940 iz e-banking
# 2. Uvozi v ERPNext
POST /api/method/erpnext_slovenia.mt940_si.mt940_parser.import_mt940
Body: content=<MT940 text>&company=...&bank_account=...
```

---

## 🔌 API Referenca

### Vsi RPC endpointi

| Modul | Metoda | HTTP | Opis |
|-------|--------|------|------|
| e-Slog | `erpnext_slovenia.einvoice.einvoice.get_eslog_xml` | GET | Pridobi XML |
| e-Slog | `erpnext_slovenia.einvoice.einvoice.attach_eslog_xml` | POST | Priloži XML |
| QR | `erpnext_slovenia.qr_image.qr_image.get_upn_qr_base64_for_invoice` | GET | Base64 QR |
| QR | `erpnext_slovenia.qr_image.qr_image.attach_upn_qr_png` | POST | Priloži PNG |
| DDV | `erpnext_slovenia.edavki.ddv_obracun_xml.get_ddv_obracun_xml` | POST | eDavki XML |
| FURS | `erpnext_slovenia.furs.edavki_api.submit_ddv_obracun` | POST | Oddaj na FURS |
| FURS | `erpnext_slovenia.furs_blagajne.furs_blagajne.register_sales_invoice` | GET | ZOI/EOR |
| VIES | `erpnext_slovenia.vies.vies.validate_any_vat` | GET | Validiraj VAT |
| MT940 | `erpnext_slovenia.mt940_si.mt940_parser.import_mt940` | POST | Uvozi izpisek |
| MT940 | `erpnext_slovenia.mt940_si.mt940_parser.import_demo_mt940` | POST | Demo uvoz |
| Kode | `erpnext_slovenia.payment_codes.payment_codes.get_payment_codes` | GET | Plačilni nameni |
| Plačilo | `erpnext_slovenia.payment_order.payment_order.generate_and_attach_payment_order` | POST | Plačilni nalog |
| CRM | `erpnext_slovenia.crm_si.crm_si.validate_phone` | GET | Validiraj telefon |
| CRM | `erpnext_slovenia.crm_si.crm_si.get_postal_code_info` | GET | Poštna številka |
| Multi | `erpnext_slovenia.multi_company.multi_company.create_slovenian_company` | POST | Novo podjetje |
| Multi | `erpnext_slovenia.multi_company.multi_company.list_slovenian_companies` | GET | Seznam |
| Multi | `erpnext_slovenia.multi_company.multi_company.get_consolidated_balance_sheet` | GET | Konsolidacija |
| Accounting | `erpnext_slovenia.accounting_integration.accounting_integration.list_supported_programs` | GET | Seznam programov |
| Workflow | `erpnext_slovenia.purchase_workflow.purchase_workflow.approve_purchase_order` | POST | Odobri PO |
| Workflow | `erpnext_slovenia.purchase_workflow.purchase_workflow.get_workflow_status` | GET | Status PO |

### Reporti

| Report | URL |
|--------|-----|
| DDV Obračun | `/app/query-report/DDV Obračun` |
| DDV-VP Letno Poročilo | `/app/query-report/DDV-VP Letno Poročilo` |
| RAČ Letni Izkaz | `/app/query-report/RAČ Letni Izkaz` |

### Print Format

| Format | URL |
|--------|-----|
| Slovenski Račun | `/printview?doctype=Sales Invoice&name=<name>&format=Slovenski Račun` |

---

## 🛠️ Razvoj

### Struktura projekta

```
erpnext_slovenia/
├── erpnext_slovenia/
│   ├── __init__.py
│   ├── hooks.py                    # Frappe hooks
│   ├── setup.py                    # After install
│   ├── utils.py                    # Davčna št. validacija
│   ├── modules.txt                 # Frappe moduli
│   │
│   ├── einvoice/                   # e-Slog 1.6 XML
│   │   └── einvoice.py
│   │
│   ├── qr_image/                   # UPN QR PNG
│   │   └── qr_image.py
│   │
│   ├── upn_qr/                     # UPN QR payload
│   │   └── upn_qr.py
│   │
│   ├── edavki/                     # eDavki XML
│   │   └── ddv_obracun_xml.py
│   │
│   ├── furs/                       # FURS eDavki API
│   │   ├── edavki_api.py
│   │   └── create_log_doctype.py
│   │
│   ├── furs_blagajne/              # FURS Blagajne (ZOI/EOR)
│   │   └── furs_blagajne.py
│   │
│   ├── srs/                        # SRS kontni plan
│   │   └── srs_chart.py
│   │
│   ├── vies/                       # VIES validacija
│   │   └── vies.py
│   │
│   ├── mt940_si/                   # MT940 parser
│   │   └── mt940_parser.py
│   │
│   ├── payment_codes/              # Plačilni nameni
│   │   └── payment_codes.py
│   │
│   ├── payment_order/              # Plačilni nalog XML
│   │   └── payment_order.py
│   │
│   ├── crm_si/                     # CRM integracija
│   │   └── crm_si.py
│   │
│   ├── accounting_integration/     # Pantheon/MiniMAX/Sigma
│   │   └── accounting_integration.py
│   │
│   ├── purchase_workflow/          # PO approval workflow
│   │   └── purchase_workflow.py
│   │
│   ├── multi_company/              # Multi-company helpers
│   │   └── multi_company.py
│   │
│   ├── print_format/               # Slovenski Račun
│   │   └── slovenian_invoice.py
│   │
│   └── report/                     # Script Reports
│       ├── ddv_obračun/
│       ├── ddv_vp_letno_poročilo/
│       └── rač_letni_izkaz/
│
├── pyproject.toml
├── README.md
├── LICENSE
├── CHANGELOG.md
├── CONTRIBUTING.md
└── .gitignore
```

### Lokalni razvoj

```bash
# Kloniraj
git clone https://github.com/markec12345678/erpnext_slovenia.git
cd erpnext_slovenia

# Namesti v bench (develop mode)
cd ~/frappe-bench
bench get-app /path/to/erpnext_slovenia
bench --site your-site install-app erpnext_slovenia

# Spreminjanje kode → bench samodejno osveži (developer_mode=1)
```

### Testiranje

```bash
# Test e-Slog XML
bench --site your-site execute erpnext_slovenia.test_eslog.main

# Test DDV report
bench --site your-site execute erpnext_slovenia.report.ddv_obračun.ddv_obračun.execute --args '[{"company":"Moje Podjetje d.o.o.","from_date":"2026-01-01","to_date":"2026-12-31"}]'
```

---

## 📦 Odvisnosti

- **Frappe Framework** >=17.0.0-dev
- **ERPNext** >=17.0.0-dev
- **qrcode** >=8.0 (za QR kode)
- **Pillow** (za QR slike)
- **openpyxl** (za Sigma Controlling export — opcijsko)

```bash
pip install qrcode[pil] openpyxl
```

---

## 🗺️ Roadmap

- [ ] FURS REST API (za novejše blagajne)
- [ ] e-Račun SI portal upload
- [ ] Slovenski plačilni promet (XML batch za banke)
- [ ] AJP (Agencija za javna naročila) integracija
- [ ] Slovenski plačilni koledar (prazniki)
- [ ] DDV-Obr avtomatska priprava (scheduler)
- [ ] Webhook za FURS potrditve

---

## 🤝 Prispevanje

Glej [CONTRIBUTING.md](CONTRIBUTING.md) za navodila o prispevanju.

---

## 📄 Licenca

Ta projekt je licenciran pod **MIT licenco** — glej [LICENSE](LICENSE).

---

## 👥 Avtorji

- **Z.ai** — začetni razvoj

## 🙏 Zahvale

- [Frappe Technologies](https://frappe.io) za Frampe Framework in ERPNext
- [GZS](https://www.gzs.si) za e-Slog standard
- [FURS](https://www.fu.gov.si) za eDavki specifikacijo
- [Banka Slovenije](https://www.bsi.si) za UPN QR standard

---

## 📞 Podpora

- **Issues**: [GitHub Issues](https://github.com/markec12345678/erpnext_slovenia/issues)
- **Diskusije**: [GitHub Discussions](https://github.com/markec12345678/erpnext_slovenia/discussions)
- **Dokumentacija**: ta README + Frappe docs

---

**Narejeno z ❤️ za slovensko poslovno skupnost**
