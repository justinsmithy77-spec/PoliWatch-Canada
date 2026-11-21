import json
import os
import re
from datetime import datetime, timezone
import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "PoliWatchCanada/1.0 (https://poliwatch-canada.netlify.app)"}
OUTPUT_PATH = "data/all_bills.json"

# Baseline fallback bills so no province ever goes blank if a government site is under maintenance
FALLBACK_BILLS = [
    {
        "id": "FED-C-42",
        "jurisdiction": "FED",
        "jurisdictionName": "Federal (Canada)",
        "number": "Bill C-42",
        "title": "Grocery and Housing Affordability Act",
        "sponsor": "House Government Bill (45th Parliament, 1st Session)",
        "stageStep": 2,
        "stageLabel": "2nd Reading",
        "latestActivity": "At Second Reading debate in the House of Commons",
        "background": "An Act respecting certain measures related to affordability and housing across Canada.",
        "officialUrl": "https://www.parl.ca/legisinfo/en/bill/45-1/c-42",
    },
    {
        "id": "AB-43",
        "jurisdiction": "AB",
        "jurisdictionName": "Alberta",
        "number": "Bill 43",
        "title": "Transportation (Safe and Sensible Roads) Statutes Amendment Act, 2026",
        "sponsor": "Government Bill (31st Legislature, 2nd Session)",
        "stageStep": 1,
        "stageLabel": "1st Reading",
        "latestActivity": "Introduced in the Legislative Assembly of Alberta",
        "background": "Amends provincial transportation statutes regarding road safety, highway rules, and traffic enforcement.",
        "officialUrl": "https://www.assembly.ab.ca/assembly-business/bills/bills-by-legislature",
    },
    {
        "id": "AB-42",
        "jurisdiction": "AB",
        "jurisdictionName": "Alberta",
        "number": "Bill 42",
        "title": "Energy, Environment and Utilities Statutes Amendment Act, 2026",
        "sponsor": "Government Bill (31st Legislature, 2nd Session)",
        "stageStep": 2,
        "stageLabel": "2nd Reading",
        "latestActivity": "At Second Reading debate in the Alberta Legislature",
        "background": "Updates provincial energy, environmental regulation, and utilities governance frameworks.",
        "officialUrl": "https://www.assembly.ab.ca/assembly-business/bills/bills-by-legislature",
    },
    {
        "id": "AB-39",
        "jurisdiction": "AB",
        "jurisdictionName": "Alberta",
        "number": "Bill 39",
        "title": "Health Statutes Amendment Act, 2026 (No. 2)",
        "sponsor": "Government Bill (31st Legislature, 2nd Session)",
        "stageStep": 2,
        "stageLabel": "2nd Reading",
        "latestActivity": "At Second Reading debate in the Alberta Legislature",
        "background": "Amends Alberta health statutes to restructure provincial health service delivery and oversight.",
        "officialUrl": "https://www.assembly.ab.ca/assembly-business/bills/bills-by-legislature",
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
        "id": "ON-143",
        "jurisdiction": "ON",
        "jurisdictionName": "Ontario",
        "number": "Bill 143",
        "title": "Plan to Protect Ontario Act (Budget Measures), 2026 (No. 2)",
        "sponsor": "Minister of Finance",
        "stageStep": 3,
        "stageLabel": "Committee",
        "latestActivity": "At Standing Committee on Finance and Economic Affairs",
        "background": "Implements Fall 2026 Ontario fiscal, tax, and economic budget measures.",
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
        "latestActivity": "Introduced in the 4th Session of the 43rd Legislature",
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
        "sponsor": "Government Bill (61st Legislature, 3rd Session)",
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
        "sponsor": "Government Bill (67th General Assembly, 3rd Session)",
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


def map_stage(status_text):
    text = (status_text or "").lower()
    if "royal assent" in text or "assented" in text:
        return 5, "Royal Assent"
    if "third reading" in text or "3rd reading" in text:
        return 4, "3rd Reading"
    if "committee" in text or "report stage" in text:
        return 3, "Committee"
    if "second reading" in text or "2nd reading" in text:
        return 2, "2nd Reading"
    return 1, "1st Reading"


def fetch_federal_bills():
    """Fetch live active bills directly from Parliament of Canada LEGISinfo JSON."""
    url = "https://www.parl.ca/legisinfo/en/bills/json"
    res = requests.get(url, headers=HEADERS, timeout=25)
    res.raise_for_status()
    raw = res.json()
    if not isinstance(raw, list):
        return []

    # Sort by latest activity date descending so newest active bills come first
    raw.sort(key=lambda x: str(x.get("LatestActivityDateTime") or ""), reverse=True)

    bills = []
    for item in raw[:12]:
        num = item.get("NumberCode")
        if not num:
            continue
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


def fetch_ontario_bills():
    """Fetch live current bills from the Legislative Assembly of Ontario."""
    url = "https://www.ola.org/en/legislative-business/bills/current"
    res = requests.get(url, headers=HEADERS, timeout=25)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, "html.parser")
    bills = []
    seen = set()

    for row in soup.select("table tbody tr"):
        cols = [c.get_text(" ", strip=True) for c in row.find_all("td")]
        link_el = row.find("a", href=True)
        if len(cols) < 2 or not link_el:
            continue
        num_text = cols[0]
        title_text = cols[1]
        status_text = cols[-1] if len(cols) >= 3 else "Active in Ontario Legislature"
        if not re.search(r"\d+", num_text) or num_text in seen:
            continue
        seen.add(num_text)
        href = link_el["href"]
        full_url = href if href.startswith("http") else f"https://www.ola.org{href}"
        step, label = map_stage(status_text)

        bills.append({
            "id": f"ON-{re.sub(r'[^A-Za-z0-9]', '', num_text)}",
            "jurisdiction": "ON",
            "jurisdictionName": "Ontario",
            "number": f"Bill {num_text}" if not num_text.lower().startswith("bill") else num_text,
            "title": title_text,
            "sponsor": "Legislative Assembly of Ontario",
            "stageStep": step,
            "stageLabel": label,
            "latestActivity": status_text,
            "background": f"Active legislation before the Legislative Assembly of Ontario: {title_text}.",
            "officialUrl": full_url,
        })
        if len(bills) >= 8:
            break
    return bills


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

    # 1. Federal (Live Official JSON)
    try:
        fed_live = fetch_federal_bills()
        if fed_live:
            print(f"Fetched {len(fed_live)} live Federal bills.")
            final_bills.extend(fed_live)
        else:
            raise ValueError("Empty federal response")
    except Exception as e:
        print(f"Federal live fetch skipped ({e}); using saved bills.")
        final_bills.extend(existing_by_jur.get("FED") or fallback_by_jur.get("FED", []))

    # 2. Ontario (Live Official HTML)
    try:
        on_live = fetch_ontario_bills()
        if on_live:
            print(f"Fetched {len(on_live)} live Ontario bills.")
            final_bills.extend(on_live)
        else:
            raise ValueError("Empty Ontario response")
    except Exception as e:
        print(f"Ontario live fetch skipped ({e}); using saved bills.")
        final_bills.extend(existing_by_jur.get("ON") or fallback_by_jur.get("ON", []))

    # 3. Remaining Provinces & Territories (Preserved safely)
    for code in ["AB", "BC", "QC", "SK", "MB", "NS", "NB", "NL", "PE", "YT", "NT", "NU"]:
        saved = existing_by_jur.get(code) or fallback_by_jur.get(code, [])
        final_bills.extend(saved)

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
