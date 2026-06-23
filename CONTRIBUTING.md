# Prispevanje k ERPNext Slovenia

Hvala za zanimanje v prispevanje k ERPNext Slovenia! 🇸🇮

## 🚀 Kako začeti

### 1. Fork & Clone

```bash
# Fork repozitorij na GitHub
# Nato kloniraj svoj fork
git clone https://github.com/your-username/erpnext_slovenia.git
cd erpnext_slovenia
```

### 2. Nastavi razvojno okolje

```bash
# Predpostavka: Frappe bench je že nameščen
cd ~/frappe-bench

# Dodaj app v bench (develop mode)
bench get-app /path/to/erpnext_slovenia

# Namesti na site
bench --site your-site install-app erpnext_slovenia

# Omogoči developer mode
bench --site your-site set-config developer_mode 1
bench --site your-site set-config server_script_enabled 1
```

### 3. Ustvari feature branch

```bash
git checkout -b feature/your-feature-name
```

## 📝 Spremembe kode

### Coding standards

- **Python**: PEP 8, ruff formatiranje (line-length 110)
- **Type hints**: uporabljaj Python type hints kjer je mogoče
- **Docstrings**: vsaka javna funkcija mora imeti docstring
- **Jezik**: sporočila uporabnikom v slovenščini, komentarji v angleščini

### Struktura modula

Vsak modul naj ima:
```
module_name/
├── __init__.py
├── module_name.py       # Glavna logika
└── test_module_name.py  # Testi (ko bodo dodani)
```

### Hooks

Dodajanje novih hooks v `hooks.py`:
```python
doc_events = {
    "Sales Invoice": {
        "on_submit": "erpnext_slovenia.your_module.your_function",
    },
}
```

### Novi Report

1. Ustvari mapo v `erpnext_slovenia/erpnext_slovenia/report/<report_name>/`
2. Dodaj `<report_name>.py` z `execute(filters)` funkcijo
3. Dodaj `<report_name>.json` z definicijo (filters, columns, roles)
4. Registriraj z `bench --site your-site migrate`

### Novi DocType

1. Ustvari definicijo v Python (glej `furs/create_log_doctype.py` za primer)
2. Ali uporabi Frappe UI: `app/doctype/New DocType`
3. Sinhroniziraj z `bench --site your-site migrate`

## 🧪 Testiranje

### Pred pošiljanjem PR

```bash
# 1. Lint
ruff check erpnext_slovenia/

# 2. Testiranje funkcij
bench --site your-site execute erpnext_slovenia.your_module.test

# 3. Preveri delovanje v browserju
# - Login kot Administrator
# - Preveri nov report/format/feature
```

### Test primeri

```python
# erpnext_slovenia/your_module/test_your_module.py
import frappe
import unittest

class TestYourModule(unittest.TestCase):
    def setUp(self):
        self.test_data = {...}

    def test_your_function(self):
        result = your_function(self.test_data)
        self.assertTrue(result["success"])

    def tearDown(self):
        frappe.db.rollback()
```

## 📋 Commit guidelines

### Commit message format

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat`: nova funkcionalnost
- `fix`: popravek hrošča
- `docs`: dokumentacija
- `style`: formatiranje
- `refactor`: prestrukturiranje
- `test`: testi
- `chore`: vzdrževanje

**Primeri:**
```
feat(einvoice): dodaj podporo za e-Slog 2.0

fix(ddv): popravi izračun osnove pri vključenem DDV

docs(readme): dodaj API referenco za VIES

refactor(qr): poenostavi UPN QR payload generacijo
```

## 🔀 Pull Request proces

1. **Posodobi svoj fork** z najnovejšimi spremembami iz main
2. **Poženi teste** in preveri da vse deluje
3. **Ustvari PR** z jasnim opisom:
   - Kaj dodaja/ popravlja
   - Zakaj je potrebno
   - Kako testirati
   - Screenshot (če je UI sprememba)

### PR template

```markdown
## Opis
[Brief description of changes]

## Tip spremembe
- [ ] Bug fix (ne-breaking sprememba)
- [ ] Nova funkcionalnost (ne-breaking sprememba)
- [ ] Breaking sprememba (fix ali feature ki bi lahko vplival na obstoječo funkcionalnost)

## Kako testirati
1. ...
2. ...

## Checklist
- [ ] Koda sledi style guidelines
- [ ] Self-review opravljen
- [ ] Komentarji dodani za kompleksno logiko
- [ ] Dokumentacija posodobljena
- [ ] Ni novih warningov
```

## 🐛 Prijavljanje hroščev

Uporabi [GitHub Issues](https://github.com/markec12345678/erpnext_slovenia/issues) z:

1. **Jasnim naslovom**
2. **Koraki za reprodukcijo**
3. **Pričakovanem obnašanju**
4. **Dejanskem obnašanju**
5. **Screenshot/ih** (če relevantno)
6. **Okolje**: Frappe/ERPNext version, Python version, OS

## 💡 Predlogi funkcij

Odprite [GitHub Discussion](https://github.com/markec12345678/erpnext_slovenia/discussions) z:

1. **Problem**: kaj rešuje
2. **Predlagana rešitev**: kako
3. **Alternativne rešitve**: kaj še
4. **Dodatne informacije**: reference, primeri

## 🌍 Prevodi

Slovenščina je primarni jezik. Če želiš dodati druge jezike:

1. Ustvari prevod v `erpnext_slovenia/locale/`
2. Uporabi `_("text")` za vse uporabniške sporočila
3. Zaženi `bench --site your-site update-translations`

## 📞 Vprašanja

- **GitHub Discussions**: za splošna vprašanja
- **GitHub Issues**: za hrošče in feature requeste
- **Email**: za privatne poizvedbe

---

Hvala za tvoje prispevanje! 🎉
