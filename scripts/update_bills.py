import json
import os
import re
from datetime import datetime, timezone
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
}
OUTPUT_PATH = "data/all_bills.json"

# Baseline fallback bills so no jurisdiction ever goes blank if a government site is down
FALLBACK_BILLS = [
    {
        "id": "FED-C-39",
        "jurisdiction": "FED",
        "jurisdictionName": "Federal (Canada)",
        "number": "Bill C-39",
        "title": "Building Canada Strong Act",
        "sponsor": "House Government Bill (45th Parliament, 1st Session)",
        "stageStep": 3,
        "stageLabel": "Committee",
        "latestActivity": "At Committee in the House of Commons",
        "background": "An Act respecting measures to strengthen Canada's economy and infrastructure.",
        "officialUrl": "https://www.parl.ca/legisinfo/en/bill/45-1/c-39",
    },
    {
        "id": "BC-1",
        "jurisdiction": "BC",
        "jurisdictionName": "British Columbia",
        "number": "Bill 1",
        "title": "An Act to Ensure the Supremacy of Parliament",
        "sponsor": "Legislative Assembly of British Columbia",
        "stageStep": 1,
        "stageLabel": "1st Reading",
        "latestActivity": "Introduced in the Legislative Assembly of British Columbia",
        "background": "Active legislation before the Legislative Assembly of British Columbia.",
        "officialUrl": "https://www.leg.bc.ca/parliamentary-business/bills",
    },
    {
        "id": "QC-1",
        "jurisdiction": "QC",
        "jurisdictionName": "Quebec",
        "number": "Bill 1",
        "title": "National Assembly of Quebec Current Legislation",
        "sponsor": "National Assembly of Quebec",
        "stageStep": 1,
        "stageLabel": "1st Reading",
        "latestActivity": "Active in the National Assembly of Quebec",
        "background": "Active legislation before the National Assembly of Quebec.",
        "officialUrl": "https://www.assnat.qc.ca/en/travaux-parlementaires/projets-loi/projets-loi-43-1.html",
    },
    {
        "id": "ON-148",
        "jurisdiction": "ON",
        "jurisdictionName": "Ontario",
        "number": "Bill 148",
        "title": "Protect Ontario Families and Communities Act, 2026",
        "sponsor": "Minister of Children, Community and Social Services",
        "stageStep": 2,
        "stageLabel": "2nd Reading",
        "latestActivity": "Second Reading debated in the Ontario Legislature",
        "background": "Enacts protections regarding intimate images and amends family and community safety statutes.",
        "officialUrl": "https://www.ola.org/en/legislative-business/bills/current",
    },
    {
        "id": "SK-67",
        "jurisdiction": "SK",
        "jurisdictionName": "Saskatchewan",
        "number": "Bill 67",
        "title": "The Coroners Amendment Act, 2026",
        "sponsor": "Government Bill (30th Legislature, 3rd Session)",
        "stageStep": 1,
        "stageLabel": "1st Reading",
        "latestActivity": "Introduced in the Legislative Assembly of Saskatchewan",
        "background": "Amends Saskatchewan's Coroners Act to update death investigation and reporting procedures.",
        "officialUrl": "https://www.legassembly.sk.ca/legislative-business/bills/",
    },
    {
        "id": "MB-2",
        "jurisdiction": "MB",
        "jurisdictionName": "Manitoba",
        "number": "Bill 2",
        "title": "The Livestock and Livestock Products Amendment Act",
        "sponsor": "Minister of Agriculture",
        "stageStep": 1,
        "stageLabel": "1st Reading",
        "latestActivity": "Introduced in the Legislative Assembly of Manitoba",
        "background": "Updates Manitoba's regulatory framework for livestock and agricultural products.",
        "officialUrl": "https://web2.gov.mb.ca/bills/sess/index.php",
    },
    {
        "id": "NS-303",
        "jurisdiction": "NS",
        "jurisdictionName": "Nova Scotia",
        "number": "Bill 303",
        "title": "Strengthening the Innovation Economy Act",
        "sponsor": "Private Member's Public Bill",
        "stageStep": 1,
        "stageLabel": "1st Reading",
        "latestActivity": "First Reading in the Nova Scotia House of Assembly",
        "background": "Establishes a Nova Scotia Intellectual Property Bank as a division of Invest Nova Scotia.",
        "officialUrl": "https://nslegislature.ca/legislative-business/bills-statutes/current-bills",
    },
    {
        "id": "NB-14",
        "jurisdiction": "NB",
        "jurisdictionName": "New Brunswick",
        "number": "Bill 14",
        "title": "An Act Respecting Property Tax Reform Measures",
        "sponsor": "Government Bill",
        "stageStep": 2,
        "stageLabel": "2nd Reading",
        "latestActivity": "Second Reading passed in New Brunswick Legislature",
        "background": "Implements provincial property tax reform and assessment relief measures.",
        "officialUrl": "https://www.legnb.ca/en/legislation/bills",
    },
    {
        "id": "PE-41",
        "jurisdiction": "PE",
        "jurisdictionName": "Prince Edward Island",
        "number": "Bill 41",
        "title": "Government Reorganization Act (No. 2)",
        "sponsor": "Government Bill",
        "stageStep": 1,
        "stageLabel": "1st Reading",
        "latestActivity": "Introduced in the PEI Legislative Assembly",
        "background": "Updates provincial department names and ministerial titles following government reorganization.",
        "officialUrl": "https://www.assembly.pe.ca/legislative-business/house-records/bills",
    },
    {
        "id": "NL-CF-2026",
        "jurisdiction": "NL",
        "jurisdictionName": "Newfoundland & Labrador",
        "number": "Civil Forfeiture Bill",
        "title": "Civil Forfeiture Legislation (Proceeds of Crime)",
        "sponsor": "Minister of Justice and Public Safety",
        "stageStep": 1,
        "stageLabel": "1st Reading",
        "latestActivity": "Introduced in the House of Assembly",
        "background": "Allows the province to seize cash and property linked to criminal activity without a criminal conviction.",
        "officialUrl": "https://www.assembly.nl.ca/HouseBusiness/Bills/",
    },
    {
        "id": "YT-204",
        "jurisdiction": "YT",
        "jurisdictionName": "Yukon",
        "number": "Bill 204",
        "title": "Second Appropriation Act 2026-27",
        "sponsor": "Premier of Yukon",
        "stageStep": 2,
        "stageLabel": "2nd Reading",
        "latestActivity": "Active on the Yukon Order Paper",
        "background": "Authorizes supplementary territorial government appropriations for the 2026-27 fiscal year.",
        "officialUrl": "https://yukonassembly.ca/house-business/progress-bills",
    },
    {
        "id": "NT-66",
        "jurisdiction": "NT",
        "jurisdictionName": "Northwest Territories",
        "number": "Bill 66",
        "title": "An Act to Amend the Motor Vehicles Act No. 2",
        "sponsor": "20th Assembly, 1st Session",
        "stageStep": 3,
        "stageLabel": "Committee",
        "latestActivity": "Committee Review completed — Awaiting Third Reading",
        "background": "Updates NWT motor vehicle regulations regarding electric scooters and seatbelt requirements.",
        "officialUrl": "https://www.ntlegislativeassembly.ca/documents-proceedings/bills",
    },
    {
        "id": "NU-6",
        "jurisdiction": "NU",
        "jurisdictionName": "Nunavut",
        "number": "Bill 6",
        "title": "Archaeological and Palaeontological Sites Act",
        "sponsor": "6th Legislative Assembly of Nunavut",
        "stageStep": 3,
        "stageLabel": "Committee",
        "latestActivity": "In Committee review",
        "background": "Updates protection, permitting, and management of archaeological and palaeontological sites in Nunavut.",
        "officialUrl": "https://www.assembly.nu.ca/bills-and-legislation",
    },
]

# Full Alberta 31st Legislature, 2nd Session (2025-2026) bill list
ALBERTA_31_2_BILLS = [
    ("1", "International Agreements Act"),
    ("2", "Back to School Act"),
    ("3", "Private Vocational Training Amendment Act, 2025"),
    ("4", "Public Safety and Emergency Services Statutes Amendment Act, 2025 (No. 2)"),
    ("5", "Miscellaneous Statutes Amendment Act, 2025"),
    ("6", "Education (Prioritizing Literacy and Numeracy) Amendment Act, 2025 (No. 2)"),
    ("7", "Water Amendment Act, 2025"),
    ("8", "Utilities Statutes Amendment Act, 2025"),
    ("9", "Protecting Alberta's Children Statutes Amendment Act, 2025"),
    ("10", "Red Tape Reduction Statutes Amendment Act, 2025 (No. 2)"),
    ("11", "Health Statutes Amendment Act, 2025 (No. 2)"),
    ("12", "Financial Statutes Amendment Act, 2025 (No. 2)"),
    ("13", "Regulated Professions Neutrality Act"),
    ("14", "Justice Statutes Amendment Act, 2025"),
    ("15", "Public Safety and Emergency Services Statutes Amendment Act, 2026"),
    ("16", "Traveller Protection and Destination Development Act"),
    ("17", "Fiscal Measures Statutes Amendment Act, 2026"),
    ("18", "Safeguards for Last Resort Termination of Life Act"),
    ("19", "Appropriation Act, 2026"),
    ("20", "Appropriation (Supplementary Supply) Act, 2026"),
    ("21", "Interprovincial Trade Mutual Recognition Act"),
    ("22", "Animal Protection Amendment Act, 2026"),
    ("23", "Justice Statutes Amendment Act, 2026"),
    ("24", "Alberta Whisky Act"),
    ("25", "An Act to Remove Politics and Ideology from Classrooms and Amend the Education Act, 2026"),
    ("26", "Immigration Oversight Act"),
    ("27", "Financial Statutes Amendment Act, 2026"),
    ("28", "Municipal Affairs and Housing Statutes Amendment Act, 2026"),
    ("29", "Health Statutes Amendment Act, 2026"),
    ("30", "Expedited 120-Day Approvals Act"),
    ("31", "Red Tape Reduction Statutes Amendment Act, 2026"),
    ("32", "Electoral Boundaries Commission Amendment Act, 2026"),
    ("33", "Justice Statutes Amendment Act, 2026 (No. 2)"),
    ("34", "Service Alberta and Red Tape Reduction Statutes Amendment Act, 2026"),
    ("35", "Education and Childcare (Securing Parental Involvement) Statutes Amendment Act, 2026"),
    ("36", "Children and Family Services (Supporting Alberta Families) Statutes Amendment Act, 2026"),
    ("37", "Miscellaneous Statutes Amendment Act, 2026"),
    ("38", "Advanced Education Statutes Amendment Act, 2026"),
    ("39", "Health Statutes Amendment Act, 2026 (No. 2)"),
    ("40", "Electoral Divisions Act"),
    ("41", "Financial Statutes Amendment Act, 2026 (No. 2)"),
    ("42", "Energy, Environment and Utilities Statutes Amendment Act, 2026"),
    ("43", "Transportation (Safe and Sensible Roads) Statutes Amendment Act, 2026"),
    ("201", "Employment Standards (Protecting Workers' Pay) Amendment Act, 2025"),
    ("202", "Conflicts of Interest (Ethical Governance) Amendment Act, 2025"),
    ("203", "Energy Storage Planning for Investment Act"),
    ("204", "Public Interest Disclosure (Publicly Funded Health Entity Whistleblower Protection) Act"),
    ("205", "Non-Disclosure Agreements Act"),
    ("206", "Accessible Alberta Act"),
    ("207", "Primary Provincial Industries Recognition Statutes Amendment Act, 2026"),
    ("208", "Tobacco, Smoking and Vaping Reduction Amendment Act, 2026"),
    ("209", "Consumer Protection (Affordability Measures) Amendment Act, 2026"),
    ("210", "Consumer Protection (Fraud Prevention Measures) Amendment Act, 2026"),
    ("211", "Patient Outcomes Reporting Act"),
    ("212", "Pharmacy Statutes (Rewards Points) Amendment Act, 2026"),
    ("213", "Alberta Personal Income Tax (Emergency Services Volunteer Tax Credits) Amendment Act, 2026"),
    ("214", "Alberta Health Care Insurance (Protecting Public Health Care) Amendment Act, 2026"),
    ("215", "Municipal Government (Reserve Land Use) Amendment Act, 2026"),
    ("Pr1", "The Ranchmen's Club Ordinance Amendment Act, 2026"),
    ("Pr2", "Prairie Bible Institute Amendment Act, 2026"),
]

FALLBACK_BILLS.extend([
    {
        "id": f"AB-{num}",
        "jurisdiction": "AB",
        "jurisdictionName": "Alberta",
        "number": f"Bill {num}",
        "title": title,
        "sponsor": "31st Legislature, 2nd Session (2025–2026)",
        "stageStep": 1,
        "stageLabel": "Active",
        "latestActivity": "31st Legislature, 2nd Session",
        "background": f"Active legislation before the Legislative Assembly of Alberta: {title}.",
        "officialUrl": "https://www.assembly.ab.ca/assembly-business/bills/bills-by-legislature",
    }
    for num, title in ALBERTA_31_2_BILLS
])


def map_stage(status_text):
    text = (status_text or "").lower()
    if "royal assent" in text or "assented" in text or "enacted" in text:
        return 5, "Royal Assent"
    if "third reading" in text or "3rd reading" in text or "passed" in text:
        return 4, "3rd Reading"
    if "committee" in text or "report stage" in text:
        return 3, "Committee"
    if "second reading" in text or "2nd reading" in text:
        return 2, "2nd Reading"
    return 1, "1st Reading"


def fetch_federal_bills():
    """Fetch ALL live active bills from Parliament of Canada LEGISinfo JSON (no cap)."""
    url = "https://www.parl.ca/legisinfo/en/bills/json"
    res = requests.get(url, headers=HEADERS, timeout=30)
    res.raise_for_status()
    raw = res.json()
    if not isinstance(raw, list):
        return []

    raw.sort(key=lambda x: str(x.get("LatestActivityDateTime") or ""), reverse=True)

    bills = []
    seen = set()
    for item in raw:
        num = item.get("NumberCode")
        if not num or num in seen:
            continue
        seen.add(num)
        parl = item.get("ParliamentNumber", 45)
        sess = item.get("SessionNumber", 1)
        title = item.get("ShortTitle") or item.get("LongTitle") or f"Federal Bill {num}"
        long_title = item.get("LongTitle") or title
        status = item.get("StatusName") or "Active in Parliament"
        sponsor = item.get("SponsorEn") or item.get("SponsorName") or f"{parl}th Parliament, Session {sess}"
        step, label = map_stage(status)
        date_str = str(item.get("LatestActivityDateTime") or "")[:10]
        activity = f"{status} ({date_str})" if date_str else status

        bills.append({
            "id": f"FED-{num}",
            "jurisdiction": "FED",
            "jurisdictionName": "Federal (Canada)",
            "number": f"Bill {num}",
            "title": title.strip(),
            "sponsor": str(sponsor).strip(),
            "stageStep": step,
            "stageLabel": label,
            "latestActivity": activity,
            "background": long_title.strip(),
            "officialUrl": f"https://www.parl.ca/legisinfo/en/bill/{parl}-{sess}/{num.lower()}",
        })
    return bills


def scrape_provincial_bills(url, jur_code, jur_name, default_sponsor):
    """Two-stage scraper: checks HTML tables first, then falls back to list/link patterns."""
    res = requests.get(url, headers=HEADERS, timeout=25)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, "html.parser")
    bills = []
    seen = set()

    # Stage 1: Standard HTML <table> rows
    for row in soup.select("table tr"):
        cols = [c.get_text(" ", strip=True) for c in row.find_all("td")]
        if len(cols) < 2:
            continue

        num_raw, title_raw = cols[0], cols[1]
        if not re.search(r"\d+", num_raw) and len(cols) >= 3 and re.search(r"\d+", cols[1]):
            num_raw, title_raw = cols[1], cols[2]

        num_match = re.search(r"(?:Bill\s*)?([A-Za-z]{0,2}-?\d+[A-Za-z]?)", num_raw, re.I)
        if not num_match or len(title_raw) < 4:
            continue

        clean_num = num_match.group(1).upper()
        bill_id = f"{jur_code}-{re.sub(r'[^A-Za-z0-9-]', '', clean_num)}"
        if bill_id in seen:
            continue
        seen.add(bill_id)

        link_el = row.find("a", href=True)
        full_url = urljoin(url, link_el["href"]) if link_el else url
        status_text = cols[-1] if len(cols) >= 3 and cols[-1] != title_raw else f"Active in {jur_name} Legislature"
        step, label = map_stage(" ".join(cols))

        bills.append({
            "id": bill_id,
            "jurisdiction": jur_code,
            "jurisdictionName": jur_name,
            "number": f"Bill {clean_num}",
            "title": title_raw.strip(),
            "sponsor": default_sponsor,
            "stageStep": step,
            "stageLabel": label,
            "latestActivity": status_text[:180],
            "background": f"Active legislation before the {default_sponsor}: {title_raw.strip()}.",
            "officialUrl": full_url,
        })

    # Stage 2: List items (<li>) and links (<a>) for sites that don't use tables
    if len(bills) < 3:
        bill_pattern = re.compile(
            r"^\s*Bill\s+([A-Za-z]{0,2}-?\d+[A-Za-z]?)\s*[\.\-–:]?\s+(.{5,220})$",
            re.I,
        )
        for el in soup.select("li, a, p, h3, h4"):
            text = " ".join(el.get_text(" ", strip=True).split())
            match = bill_pattern.match(text)
            if not match:
                continue

            clean_num = match.group(1).upper()
            title_raw = match.group(2).strip(" *$()")
            if len(title_raw) < 5:
                continue

            bill_id = f"{jur_code}-{re.sub(r'[^A-Za-z0-9-]', '', clean_num)}"
            if bill_id in seen:
                continue
            seen.add(bill_id)

            link_el = el if el.name == "a" and el.get("href") else el.find("a", href=True)
            full_url = urljoin(url, link_el["href"]) if link_el else url
            step, label = map_stage(text)

            bills.append({
                "id": bill_id,
                "jurisdiction": jur_code,
                "jurisdictionName": jur_name,
                "number": f"Bill {clean_num}",
                "title": title_raw,
                "sponsor": default_sponsor,
                "stageStep": step,
                "stageLabel": label,
                "latestActivity": f"Active in {jur_name} Legislature",
                "background": f"Active legislation before the {default_sponsor}: {title_raw}.",
                "officialUrl": full_url,
            })

    return bills


PROVINCIAL_SOURCES = [
    ("ON", "Ontario", "https://www.ola.org/en/legislative-business/bills/current", "Legislative Assembly of Ontario"),
    ("AB", "Alberta", "https://www.assembly.ab.ca/assembly-business/bills/bills-by-legislature", "Legislative Assembly of Alberta"),
    ("BC", "British Columbia", "https://www.leg.bc.ca/parliamentary-business/bills", "Legislative Assembly of British Columbia"),
    ("QC", "Quebec", "https://www.assnat.qc.ca/en/travaux-parlementaires/projets-loi/projets-loi-43-1.html", "National Assembly of Quebec"),
    ("SK", "Saskatchewan", "https://www.legassembly.sk.ca/legislative-business/bills/", "Legislative Assembly of Saskatchewan"),
    ("MB", "Manitoba", "https://web2.gov.mb.ca/bills/sess/index.php", "Legislative Assembly of Manitoba"),
    ("NS", "Nova Scotia", "https://nslegislature.ca/legislative-business/bills-statutes/current-bills", "Nova Scotia House of Assembly"),
    ("NB", "New Brunswick", "https://www.legnb.ca/en/legislation/bills", "Legislative Assembly of New Brunswick"),
    ("PE", "Prince Edward Island", "https://www.assembly.pe.ca/legislative-business/house-records/bills", "Legislative Assembly of PEI"),
    ("NL", "Newfoundland & Labrador", "https://www.assembly.nl.ca/HouseBusiness/Bills/", "House of Assembly of NL"),
    ("YT", "Yukon", "https://yukonassembly.ca/house-business/progress-bills", "Yukon Legislative Assembly"),
    ("NT", "Northwest Territories", "https://www.ntlegislativeassembly.ca/documents-proceedings/bills", "Legislative Assembly of the NWT"),
    ("NU", "Nunavut", "https://www.assembly.nu.ca/bills-and-legislation", "Legislative Assembly of Nunavut"),
]


def main():
    existing_by_jur = {}
    if os.path.exists(OUTPUT_PATH):
        try:
            with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
                prev = json.load(f)
                for b in prev.get("bills", []):
                    existing_by_jur.setdefault(b["jurisdiction"], []).append(b)
        except Exception:
            pass

    fallback_by_jur = {}
    for b in FALLBACK_BILLS:
        fallback_by_jur.setdefault(b["jurisdiction"], []).append(b)

    final_bills = []

    # 1. Federal (Live Official JSON — ALL active bills)
    try:
        fed_live = fetch_federal_bills()
        if fed_live:
            print(f"[FED] Fetched {len(fed_live)} live Federal bills.")
            final_bills.extend(fed_live)
        else:
            raise ValueError("Empty federal response")
    except Exception as e:
        print(f"[FED] Live fetch skipped ({e}); using saved/fallback bills.")
        saved = existing_by_jur.get("FED", [])
        fallback = fallback_by_jur.get("FED", [])
        final_bills.extend(saved if len(saved) >= len(fallback) else fallback)

    # 2. All 13 Provinces & Territories (Live table + list scrapers with safe fallbacks)
    for code, name, url, sponsor in PROVINCIAL_SOURCES:
        try:
            live = scrape_provincial_bills(url, code, name, sponsor)
            if live:
                print(f"[{code}] Fetched {len(live)} live bills.")
                final_bills.extend(live)
            else:
                raise ValueError("No bills matched")
        except Exception as e:
            print(f"[{code}] Live fetch skipped ({e}); using saved/fallback bills.")
            saved = existing_by_jur.get(code, [])
            fallback = fallback_by_jur.get(code, [])
            final_bills.extend(saved if len(saved) >= len(fallback) else fallback)

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    payload = {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "count": len(final_bills),
        "bills": final_bills,
    }
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(final_bills)} total bills to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
