# Changelog

Vse pomembne spremembe tega projekta bodo dokumentirane v tej datoteki.

Format temelji na [Keep a Changelog](https://keepachangelog.com/si/1.0.0/),
in projekt sledi [Semantic Versioning](https://semver.org/lang/si/).

## [Unreleased]

### Načrtovano
- FURS REST API (za novejše blagajne)
- e-Račun SI portal avtomatski upload
- Slovenski plačilni koledar (prazniki)
- DDV-Obr scheduler (avtomatska priprava mesečno)
- Webhook za FURS potrditve

## [0.2.0] - 2026-06-23

### Dodano
- **SRS Kontni Plan** — 203 kontov po slovenskih računovodskih standardih
- **FURS eDavki API** — SOAP integracija za oddajo DDV na FURS
- **FURS Submission Log** — avditska sled vseh oddaj
- **QR koda kot slika** — PNG generacija z qrcode + Pillow
- **DDV-VP Letno Poročilo** — letno poročilo o transakcijah z zavezanci
- **VIES Validacija** — EU VIES SOAP API za validacijo VAT številk
- **MT940 Parser** — uvoz bančnih izpiskov (SWIFT format)
- **Plačilni Nameni** — 44 standardnih kod (ZBS 2024) v bazi
- **RAČ Letni Izkaz** — bilanca stanja + poslovni izid
- **FURS Blagajne** — real-time registracija računov (ZOI/EOR)
- **Multi-Company** — ustvarjanje novih slovenskih podjetij z avto CoA
- **Plačilni Nalog XML** — ISO 20022 pain.001 za slovenske banke
- **CRM Integracija** — validacija telefonskih številk + poštne številke
- **Računovodske Integracije** — Pantheon, MiniMAX, Sigma Controlling export
- **Purchase Order Workflow** — večstopenjsko odobrenje nakupov
- Custom Fields za VIES validacijo na Customer
- Module Def "Erpnext Slovenia"

### Spremenjeno
- `hooks.py` dodan `qr_image.attach_upn_qr_png` v Sales Invoice on_submit
- `setup.py` razširjen z FURS log doctype in payment codes setup
- README.md popolnoma prenovljen z API referenco

## [0.1.0] - 2026-06-22

### Dodano
- **e-Slog 1.6 XML** — samodejna generacija ob submitu Sales Invoice
- **UPN QR Payload** — Banka Slovenije standard (19 polj)
- **DDV Obračun Report** — mesečni DDV report (Script Report)
- **eDavki XML** — DDV-Obr XML generator za FURS
- **Slovenski Print Format** — "Slovenski Račun" Jinja template
- **Slovenski Kontni Plan** — 51 kontov (osnovni)
- **DDV Predloge** — 4 predloge (22%, 8.5% za prodajo in nakup)
- **Bank Account** — NLB d.o.o. z veljavnim SI IBAN
- **Vzorčni podatki** — kupec, dobavitelj, 3 artikli, 1 račun
- Custom Field `custom_si_tax_id` na Customer in Supplier
- Validacija davčne številke (MOD 11 checksum)
- Slovenia setup (EUR, Europe/Ljubljana, slovenščina UI)

### Infrastruktura
- `pyproject.toml` s Frappe/ERPNext odvisnostmi
- `hooks.py` z doc_events za Sales Invoice, Customer, Supplier
- `setup.py` z after_install (Custom Fields, Print Format)
- `modules.txt` z Module Def "Erpnext Slovenia"

---

## Tipi sprememb

- `Dodano` — nove funkcionalnosti
- `Spremenjeno` — spremembe obstoječih funkcij
- `Zastarelo` — kmalu odstranjene funkcije
- `Odstranjeno` — odstranjene funkcije
- `Popravljeno` — popravki hroščev
- `Varnost` — varnostni popravki
