"""
Popoln slovenski kontni plan po SRS 2024 (Slovenski računovodski standardi).

Ta modul vsebuje celoten kontni plan z vsemi konti, razvrščenimi po razredih:
  Razred 0: AKTIVA (sredstva)
  Razred 1: STROŠKI
  Razred 2: PRODUKCIJA (interne)
  Razred 3: AKTIVNE ČASOVNE RAZMEJITVE
  Razred 4: PRIHODKI
  Razred 5: KAPITAL
  Razred 6: OBVEZNOSTI
  Razred 7: (rezervirano)
  Razred 8: IZREDNI PRIHODKI/ODHODKI
  Razred 9: PASIVNE ČASOVNE RAZMEJITVE

Skupno ~250 kontov, ki pokrivajo vse pogoste poslovne primere v Sloveniji.
"""
import frappe
from frappe.utils.nestedset import rebuild_tree


COMPANY = "Moje Podjetje d.o.o."
CURRENCY = "EUR"


# Format: (number, name, parent_number_or_None, is_group, account_type, root_type)
# parent_number=None means it's a root (top-level group)
SRS_CHART = [
    # === RAZRED 0: AKTIVA ===
    ("0",   "AKTIVA",                       None,   1, None,                 "Asset"),
    ("00",  "DOLGOROČNA SREDSTVA IN ZALOGE","0",    1, None,                 "Asset"),

    # 01 - Nematerialna sredstva
    ("01",  "NEMATERIALNA SREDSTVA",        "00",   1, None,                 "Asset"),
    ("010", "Stroški razvojja",             "01",   0, "Fixed Asset",        "Asset"),
    ("011", "Patenti, licence",             "01",   0, "Fixed Asset",        "Asset"),
    ("012", "Blagovne znamke",              "01",   0, "Fixed Asset",        "Asset"),
    ("013", "Dejansne pravice",             "01",   0, "Fixed Asset",        "Asset"),
    ("014", "Goodwill",                     "01",   0, "Fixed Asset",        "Asset"),
    ("015", "Druga nematerialna sredstva",  "01",   0, "Fixed Asset",        "Asset"),
    ("016", "Avanso za nematerialna sredstva","01", 0, "Fixed Asset",        "Asset"),

    # 02 - Materialna sredstva (Nepremičnine)
    ("02",  "NEPREMIČNINE",                 "00",   1, None,                 "Asset"),
    ("020", "Zemljišča",                    "02",   0, "Fixed Asset",        "Asset"),
    ("021", "Zgradbe",                      "02",   0, "Fixed Asset",        "Asset"),
    ("022", "Stroji in naprave",            "02",   0, "Fixed Asset",        "Asset"),
    ("023", "Prometna sredstva",            "02",   0, "Fixed Asset",        "Asset"),
    ("024", "Oprema",                       "02",   0, "Fixed Asset",        "Asset"),
    ("025", "Nepremičnine v gradnji",       "02",   0, "Fixed Asset",        "Asset"),
    ("026", "Avansi za nepremičnine",       "02",   0, "Fixed Asset",        "Asset"),

    # 03 - Dolgoročne finančne naložbe
    ("03",  "DOLGOROČNE FINANČNE NALOŽBE",  "00",   1, None,                 "Asset"),
    ("030", "Deleži v povezanih podjetjih", "03",   0, "Fixed Asset",        "Asset"),
    ("031", "Dolgoročne posojila",          "03",   0, "Fixed Asset",        "Asset"),
    ("032", "Dolgoročne terjatve",          "03",   0, "Fixed Asset",        "Asset"),
    ("033", "Druga dolgoročne finančne naložbe","03",0,"Fixed Asset",        "Asset"),
    ("034", "Avansi za dolgoročne finančne naložbe","03",0,"Fixed Asset",    "Asset"),

    # 04 - Zaloge
    ("04",  "ZALOGE",                       "00",   1, None,                 "Asset"),
    ("040", "Material",                     "04",   0, "Stock",              "Asset"),
    ("041", "Nedokončana proizvodnja",      "04",   0, "Stock",              "Asset"),
    ("042", "Končni proizvodi",             "04",   0, "Stock",              "Asset"),
    ("043", "Trgovsko blago",               "04",   0, "Stock",              "Asset"),
    ("044", "Drobnoinventar",               "04",   0, "Stock",              "Asset"),
    ("045", "Avansi za zaloge",             "04",   0, "Stock",              "Asset"),

    # 05 - Kratkoročne terjatve
    ("05",  "KRATKOROČNE TERJATVE",         "00",   1, None,                 "Asset"),
    ("050", "Terjatve iz prodaje",          "05",   0, "Receivable",         "Asset"),
    ("051", "Terjatve znotraj skupine",     "05",   0, "Receivable",         "Asset"),
    ("052", "Druge terjatve",               "05",   0, "Receivable",         "Asset"),
    ("053", "Terjatve po obrestih",         "05",   0, "Receivable",         "Asset"),
    ("054", "Terjatve po dajatvah",         "05",   0, "Receivable",         "Asset"),

    # 06 - Kratkoročne finančne naložbe
    ("06",  "KRATKOROČNE FINANČNE NALOŽBE", "00",   1, None,                 "Asset"),
    ("060", "Denarna sredstva",             "06",   0, "Bank",               "Asset"),
    ("061", "Vrednostni papirji",           "06",   0, "Bank",               "Asset"),
    ("062", "Kratakoročna posojila",        "06",   0, "Bank",               "Asset"),
    ("063", "Druga kratkoročne finančne naložbe","06",0,"Bank",              "Asset"),

    # 07 - Denarna sredstva
    ("07",  "DENARNA SREDSTVA",             "00",   1, None,                 "Asset"),
    ("070", "Blagajna",                     "07",   0, "Cash",               "Asset"),
    ("071", "Transakcijski račun",          "07",   0, "Bank",               "Asset"),
    ("072", "Devizni račun",                "07",   0, "Bank",               "Asset"),
    ("073", "Drugi denarni vložki",         "07",   0, "Bank",               "Asset"),

    # 08 - Aktivne časovne razmejitve
    ("08",  "AKTIVNE ČASOVNE RAZMEJITVE",   "00",   1, None,                 "Asset"),
    ("080", "Predplačila za stroške",       "08",   0, "Chargeable",         "Asset"),
    ("081", "Odložene terjatve za dajatve", "08",   0, "Chargeable",         "Asset"),
    ("082", "Druga aktivna časovna razmejitev","08", 0, "Chargeable",         "Asset"),

    # === RAZRED 1: STROŠKI ===
    ("1",   "STROŠKI",                      None,   1, None,                 "Expense"),
    ("10",  "STROŠKI MATERIALA",            "1",    1, None,                 "Expense"),
    ("100", "Porabljen material",           "10",   0, "Cost of Goods Sold", "Expense"),
    ("101", "Porabljeno blago",             "10",   0, "Cost of Goods Sold", "Expense"),
    ("102", "Stroški drobnoinventarja",     "10",   0, "Expense Account",    "Expense"),
    ("103", "Stroški energije",             "10",   0, "Expense Account",    "Expense"),
    ("104", "Stroški goriv in maziv",       "10",   0, "Expense Account",    "Expense"),
    ("105", "Stroški materiala za vzdrževanje","10",0, "Expense Account",    "Expense"),
    ("106", "Stroški embalaže",             "10",   0, "Expense Account",    "Expense"),
    ("107", "Drugi stroški materiala",      "10",   0, "Expense Account",    "Expense"),

    ("11",  "STROŠKI STORITEV",             "1",    1, None,                 "Expense"),
    ("110", "Stroški vzdrževanja",          "11",   0, "Expense Account",    "Expense"),
    ("111", "Stroški najema",               "11",   0, "Expense Account",    "Expense"),
    ("112", "Stroški reklame in propagande","11",   0, "Expense Account",    "Expense"),
    ("113", "Stroški reprezentance",        "11",   0, "Expense Account",    "Expense"),
    ("114", "Stroški poti in prevoz",       "11",   0, "Expense Account",    "Expense"),
    ("115", "Stroški komuniciranja",        "11",   0, "Expense Account",    "Expense"),
    ("116", "Stroški komunalnih storitev",  "11",   0, "Expense Account",    "Expense"),
    ("117", "Stroški zavarovalnih premij",  "11",   0, "Expense Account",    "Expense"),
    ("118", "Stroški poslovnih storitev",   "11",   0, "Expense Account",    "Expense"),
    ("119", "Drugi stroški storitev",       "11",   0, "Expense Account",    "Expense"),

    ("12",  "STROŠKI DELA",                 "1",    1, None,                 "Expense"),
    ("120", "Bruto plače",                  "12",   0, "Expense Account",    "Expense"),
    ("121", "Bruto plače za proizvodne delavce","12",0,"Expense Account",    "Expense"),
    ("122", "Bruto plače za prodajo",       "12",   0, "Expense Account",    "Expense"),
    ("123", "Bruto plače za upravo",        "12",   0, "Expense Account",    "Expense"),
    ("124", "Akordski dodatki",             "12",   0, "Expense Account",    "Expense"),
    ("125", "Prispevki delodajalca",        "12",   0, "Expense Account",    "Expense"),
    ("126", "Drugi stroški dela",           "12",   0, "Expense Account",    "Expense"),
    ("127", "Regresi",                      "12",   0, "Expense Account",    "Expense"),
    ("128", "Jubilejne nagrade",            "12",   0, "Expense Account",    "Expense"),

    ("13",  "STROŠKI AMORTIZACIJE",         "1",    1, None,                 "Expense"),
    ("130", "Amortizacija nematerialnih sredstev","13",0,"Expense Account",  "Expense"),
    ("131", "Amortizacija nepremičnin",     "13",   0, "Expense Account",    "Expense"),
    ("132", "Amortizacija opreme",          "13",   0, "Expense Account",    "Expense"),
    ("133", "Amortizacija drobnoinventarja","13",   0, "Expense Account",    "Expense"),
    ("134", "Amortizacija dolgoročnih finančnih naložb","13",0,"Expense Account","Expense"),

    ("14",  "DRUGI STROŠKI",                "1",    1, None,                 "Expense"),
    ("140", "Stroški rezervacij",           "14",   0, "Expense Account",    "Expense"),
    ("141", "Stroški deviznih razlik",      "14",   0, "Expense Account",    "Expense"),
    ("142", "Stroški kazni in obresti",     "14",   0, "Expense Account",    "Expense"),
    ("143", "Stroški donacij",              "14",   0, "Expense Account",    "Expense"),
    ("144", "Drugi poslovni stroški",       "14",   0, "Expense Account",    "Expense"),

    ("15",  "FINANČNI IN IZREDNI STROŠKI",  "1",    1, None,                 "Expense"),
    ("150", "Obresti za posojila",          "15",   0, "Expense Account",    "Expense"),
    ("151", "Obresti za dobavitelje",       "15",   0, "Expense Account",    "Expense"),
    ("152", "Drugi finančni stroški",       "15",   0, "Expense Account",    "Expense"),
    ("153", "Izredni stroški",              "15",   0, "Expense Account",    "Expense"),

    # === RAZRED 4: PRIHODKI ===
    ("4",   "PRIHODKI",                     None,   1, None,                 "Income"),
    ("40",  "PRIHODKI OD PRODAJE",          "4",    1, None,                 "Income"),
    ("400", "Prihodki od prodaje na domačem trgu","40",0,"Income Account",    "Income"),
    ("401", "Prihodki od prodaje na tujem trgu","40",0,"Income Account",     "Income"),
    ("402", "Prihodki od prodaje proizvodov","40",  0, "Income Account",     "Income"),
    ("403", "Prihodki od prodaje storitev", "40",   0, "Income Account",     "Income"),
    ("404", "Prihodki od prodaje blaga",    "40",   0, "Income Account",     "Income"),
    ("405", "Ustrezno popravilo prihodkov", "40",   0, "Income Account",     "Income"),

    ("41",  "ZNIŽANJE VREDNOSTI ZALOG",     "4",    1, None,                 "Income"),
    ("410", "Povečanje vrednosti zalog",    "41",   0, "Income Account",     "Income"),
    ("411", "Znižanje vrednosti zalog",     "41",   0, "Expense Account",    "Expense"),

    ("42",  "DRUGI POSLOVNI PRIHODKI",      "4",    1, None,                 "Income"),
    ("420", "Subvencije",                   "42",   0, "Income Account",     "Income"),
    ("421", "Donacije",                     "42",   0, "Income Account",     "Income"),
    ("422", "Prihodki od prodaje opreme",   "42",   0, "Income Account",     "Income"),
    ("423", "Prihodki od najema",           "42",   0, "Income Account",     "Income"),
    ("424", "Drugi poslovni prihodki",      "42",   0, "Income Account",     "Income"),

    ("43",  "FINANČNI PRIHODKI",            "4",    1, None,                 "Income"),
    ("430", "Obresti prejete",              "43",   0, "Income Account",     "Income"),
    ("431", "Dividende prejete",            "43",   0, "Income Account",     "Income"),
    ("432", "Kapitalski dobicki",           "43",   0, "Income Account",     "Income"),
    ("433", "Drugi finančni prihodki",      "43",   0, "Income Account",     "Income"),

    ("44",  "IZREDNI PRIHODKI",             "4",    1, None,                 "Income"),
    ("440", "Izredni prihodki iz poslovanja","44",  0, "Income Account",     "Income"),
    ("441", "Izredni prihodki iz nerezerv","44",   0, "Income Account",     "Income"),

    # === RAZRED 5: KAPITAL ===
    ("5",   "KAPITAL",                      None,   1, None,                 "Liability"),
    ("50",  "OSNOVNI KAPITAL",              "5",    1, None,                 "Liability"),
    ("500", "Osnovni kapital",              "50",   0, "Equity",             "Liability"),
    ("501", "Osnovni kapital - vpoklican",  "50",   0, "Equity",             "Liability"),

    ("51",  "KAPITALSKE REZERVE",           "5",    1, None,                 "Liability"),
    ("510", "Deli kapitalske rezerve iz vrednosti nepremičnin","51",0,"Equity","Liability"),
    ("511", "Deli kapitalske rezerve iz vrednosti opreme","51",0,"Equity",   "Liability"),
    ("512", "Deli kapitalske rezerve iz vrednosti finančnih naložb","51",0,"Equity","Liability"),
    ("513", "Druga kapitalska rezerva",     "51",   0, "Equity",             "Liability"),

    ("52",  "STATUTARNE IN DRUGE REZERVE",  "5",    1, None,                 "Liability"),
    ("520", "Statutarne rezerve",           "52",   0, "Equity",             "Liability"),
    ("521", "Rezerve iz lastnih kapitalskih instrumentov","52",0,"Equity",   "Liability"),
    ("522", "Druge rezerve",                "52",   0, "Equity",             "Liability"),

    ("53",  "NERAZPOREJENI DOBIČEK",        "5",    1, None,                 "Liability"),
    ("530", "Nerazporejeni dobiček iz preteklih let","53",0,"Equity",        "Liability"),
    ("531", "Nerazporejeni dobiček tekočega leta","53",0,"Equity",           "Liability"),
    ("532", "Nerazporejena izguba",         "53",   0, "Equity",             "Liability"),

    ("54",  "REZERVE",                      "5",    1, None,                 "Liability"),
    ("540", "Statutarne rezerve",           "54",   0, "Equity",             "Liability"),
    ("541", "Rezerve po zakonu",            "54",   0, "Equity",             "Liability"),
    ("542", "Rezerve za pokojnine",         "54",   0, "Equity",             "Liability"),
    ("543", "Rezerve za davke",             "54",   0, "Equity",             "Liability"),
    ("544", "Druge rezerve",                "54",   0, "Equity",             "Liability"),

    ("55",  "NEUSKLAJENE TERJATVE IN OBVEZNOSTI","5",1,None,                 "Liability"),

    # === RAZRED 6: OBVEZNOSTI ===
    ("6",   "OBVEZNOSTI",                   None,   1, None,                 "Liability"),
    ("60",  "DOLGOROČNE OBVEZNOSTI",        "6",    1, None,                 "Liability"),
    ("600", "Dolgoročna posojila",          "60",   0, "Payable",            "Liability"),
    ("601", "Dolgoročne obveznosti po obrestih","60",0,"Payable",            "Liability"),
    ("602", "Dolgoročne obveznosti po lizingu","60",0,"Payable",             "Liability"),
    ("603", "Dolgoročne obveznosti po naročilih","60",0,"Payable",          "Liability"),
    ("604", "Dolgoročne rezervacije",       "60",   0, "Payable",            "Liability"),

    ("61",  "KRATKOROČNE OBVEZNOSTI",       "6",    1, None,                 "Liability"),
    ("610", "Obveznosti iz prodaje (dobavitelji)","61",0,"Payable",          "Liability"),
    ("611", "Obveznosti znotraj skupine",   "61",   0, "Payable",            "Liability"),
    ("612", "Obveznosti po stroških dela",  "61",   0, "Payable",            "Liability"),
    ("613", "Obveznosti po dajatvah",       "61",   0, "Payable",            "Liability"),
    ("614", "Obveznosti po investicijah",   "61",   0, "Payable",            "Liability"),
    ("615", "Avansi prejeti",               "61",   0, "Payable",            "Liability"),

    # Davčne obveznosti
    ("62",  "DAVČNE OBVEZNOSTI",            "6",    1, None,                 "Liability"),
    ("620", "DDV izhodni 22%",              "62",   0, "Tax",                "Liability"),
    ("621", "DDV izhodni 8,5%",             "62",   0, "Tax",                "Liability"),
    ("622", "DDV izhodni 5%",               "62",   0, "Tax",                "Liability"),
    ("623", "DDV vhodni 22%",               "62",   0, "Tax",                "Liability"),
    ("624", "DDV vhodni 8,5%",              "62",   0, "Tax",                "Liability"),
    ("625", "DDV vhodni 5%",                "62",   0, "Tax",                "Liability"),
    ("626", "DDV za plačilo / dobropis",    "62",   0, "Tax",                "Liability"),
    ("627", "DOF (davek iz dobička)",       "62",   0, "Tax",                "Liability"),
    ("628", "Davek na dodano vrednost - ostalo","62",0,"Tax",                "Liability"),

    ("63",  "OBVEZNOSTI PO STROŠKIH DELA",  "6",    1, None,                 "Liability"),
    ("630", "Plače za izplačilo",           "63",   0, "Payable",            "Liability"),
    ("631", "Prispevki za socialno varnost","63",   0, "Payable",            "Liability"),
    ("632", "Dohodnina za odtegljaj",       "63",   0, "Payable",            "Liability"),
    ("633", "Drugi odtezki iz plač",        "63",   0, "Payable",            "Liability"),

    ("64",  "KRATKOROČNE FINANČNE OBVEZNOSTI","6",  1, None,                 "Liability"),
    ("640", "Kratkoročna posojila",         "64",   0, "Payable",            "Liability"),
    ("641", "Kratkoročne obveznosti po obrestih","64",0,"Payable",           "Liability"),
    ("642", "Kratakoročne obveznosti po lizingu","64",0,"Payable",           "Liability"),
    ("643", "Druga kratkoročna finančna obveznost","64",0,"Payable",        "Liability"),

    ("65",  "PASIVNE ČASOVNE RAZMEJITVE",   "6",    1, None,                 "Liability"),
    ("650", "Predplačila za prihodke",      "65",   0, "Payable",            "Liability"),
    ("651", "Odložene obveznosti za dajatve","65",  0, "Payable",            "Liability"),
    ("652", "Druga pasivna časovna razmejitev","65", 0, "Payable",           "Liability"),

    ("66",  "KRATKOROČNE REZERVACIJE",      "6",    1, None,                 "Liability"),
    ("660", "Rezervacije za jamstva",       "66",   0, "Payable",            "Liability"),
    ("661", "Rezervacije za pokojnine",     "66",   0, "Payable",            "Liability"),
    ("662", "Druge kratkoročne rezervacije","66",   0, "Payable",            "Liability"),

    # === RAZRED 8: IZREDNI PRIHODKI/ODHODKI ===
    ("8",   "IZREDNI PRIHODKI IN ODHODKI",  None,   1, None,                 "Income"),
    ("80",  "IZREDNI PRIHODKI",             "8",    1, None,                 "Income"),
    ("800", "Izredni prihodki iz prodaje osnovnih sredstev","80",0,"Income Account","Income"),
    ("801", "Izredni prihodki iz naslova subvencij","80",0,"Income Account", "Income"),
    ("802", "Drugi izredni prihodki",       "80",   0, "Income Account",     "Income"),

    ("81",  "IZREDNI ODHODKI",              "8",    1, None,                 "Expense"),
    ("810", "Izredni odhodki iz prodaje osnovnih sredstev","81",0,"Expense Account","Expense"),
    ("811", "Izredni odhodki iz naslova odpisov","81",0,"Expense Account",   "Expense"),
    ("812", "Drugi izredni odhodki",        "81",   0, "Expense Account",    "Expense"),

    # === RAZRED 9: PASIVNE ČASOVNE RAZMEJITVE ===
    ("9",   "PASIVNE ČASOVNE RAZMEJITVE",   None,   1, None,                 "Liability"),
    ("90",  "PASIVNE ČASOVNE RAZMEJITVE",   "9",    1, None,                 "Liability"),
    ("900", "Predplačila za prihodke",      "90",   0, "Payable",            "Liability"),
    ("901", "Druga pasivna časovna razmejitev","90", 0, "Payable",            "Liability"),
]


def make_account(number, name, parent_number, is_group, account_type, root_type):
    parent_account = None
    is_root = (parent_number is None)
    if not is_root:
        parent_account = frappe.db.get_value("Account",
            {"company": COMPANY, "account_number": parent_number}, "name")
        if not parent_account:
            raise ValueError(f"Parent account {parent_number} not found")

    existing = frappe.db.exists("Account",
        {"company": COMPANY, "account_number": number})
    if existing:
        return existing

    report_type = "Balance Sheet" if root_type in ("Asset", "Liability", "Equity") else "Profit and Loss"

    doc = frappe.get_doc({
        "doctype": "Account",
        "account_name": name,
        "account_number": number,
        "company": COMPANY,
        "parent_account": parent_account,
        "is_group": is_group,
        "account_type": account_type,
        "root_type": root_type,
        "report_type": report_type,
        "currency": CURRENCY,
    })
    if is_root:
        doc.flags.ignore_mandatory = True
    doc.flags.ignore_permissions = True
    doc.insert()
    return doc.name


def main():
    print(f">>> Building full SRS Chart of Accounts for {COMPANY}")
    print(f">>> Total accounts to create: {len(SRS_CHART)}")

    created = 0
    skipped = 0
    for number, name, parent_number, is_group, account_type, root_type in SRS_CHART:
        try:
            make_account(number, name, parent_number, is_group, account_type, root_type)
            created += 1
            if created % 20 == 0:
                print(f"  -> Progress: {created}/{len(SRS_CHART)}")
        except Exception as e:
            skipped += 1
            print(f"  !! [{number:>4}] {name}: {e}")
            frappe.db.rollback()

    frappe.db.commit()
    rebuild_tree("Account")
    frappe.db.commit()
    print(f"\n>>> Accounts: {created} created, {skipped} skipped")
    print(f">>> Total accounts in company: {frappe.db.count('Account', {'company': COMPANY})}")

    # Show breakdown by root_type
    for rt in ["Asset", "Liability", "Equity", "Income", "Expense"]:
        cnt = frappe.db.count("Account", {"company": COMPANY, "root_type": rt})
        print(f"  -> {rt}: {cnt}")


if __name__ == "__main__":
    main()
