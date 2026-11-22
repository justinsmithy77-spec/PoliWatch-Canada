import io
import json
import os
import re
from datetime import datetime, timezone
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

try:
    from pypdf import PdfReader
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
}
OUTPUT_PATH = "data/all_bills.json"

SECTOR_RULES = [
    ("Healthcare", [
        "health", "hospital", "medical", "medicine", "pharmacy", "pharmac", "drug",
        "mental", "addiction", "cancer", "patient", "doctor", "nurse", "clinic",
        "reproductive", "ivf", "dental", "tobacco", "vaping", "smoking", "coroner",
        "termination of life", "long-term care", "care home", "ambulance",
    ]),
    ("Education & Childcare", [
        "education", "school", "university", "college", "student", "teacher",
        "classroom", "literacy", "numeracy", "childcare", "child care", "daycare",
        "early years", "vocational", "post-secondary", "campus", "tuition", "parental",
    ]),
    ("Energy & Environment", [
        "energy", "environment", "climate", "carbon", "emission", "water", "utility",
        "utilities", "electricity", "hydro", "oil", "gas", "pipeline", "mining",
        "mineral", "forestry", "wildlife", "conservation", "park", "species",
        "waste", "recycling", "clean", "renewable", "nuclear", "fuel", "animal protection",
    ]),
    ("Justice & Public Safety", [
        "justice", "crime", "criminal", "police", "policing", "court", "judicial",
        "safety", "emergency", "forfeiture", "lawful access", "prison", "correction",
        "security guard", "investigator", "firearm", "weapon", "victim", "offence",
        "enforcement", "border", "cyber", "fraud", "violence", "harassment",
        "intimate image", "non-disclosure", "whistleblower", "legal profession",
    ]),
    ("Housing & Municipal", [
        "housing", "municipal", "property tax", "rent", "tenant", "landlord",
        "zoning", "real estate", "condominium", "mortgage", "homeless", "city",
        "town", "local government", "urban", "rural", "land use", "assessment",
        "building code", "construction", "affordability",
    ]),
    ("Transportation & Infrastructure", [
        "transport", "highway", "road", "traffic", "motor vehicle", "driver",
        "transit", "rail", "railway", "aviation", "airport", "marine", "ferry",
        "port", "bridge", "infrastructure", "scooter", "seatbelt", "vehicle",
        "shipping", "trucking",
    ]),
    ("Labour & Social Services", [
        "labour", "labor", "worker", "employment", "wage", "union", "workplace",
        "pension", "family", "families", "children", "child", "youth", "senior",
        "accessibility", "accessible", "disability", "social", "welfare", "income support",
        "immigration", "human rights", "indigenous", "first nation", "métis", "inuit",
        "poverty", "volunteer",
    ]),
    ("Economy & Finance", [
        "finance", "financial", "budget", "appropriation", "tax", "fiscal", "economy",
        "economic", "trade", "business", "commerce", "consumer", "grocery", "tariff",
        "red tape", "innovation", "investment", "bank", "insurance", "credit",
        "supply", "revenue", "agriculture", "livestock", "farm", "fisheries",
        "tourism", "traveller", "whisky", "liquor", "cannabis", "digital market",
        "technology", "research", "industry", "industries", "professions",
    ]),
]


def classify_sector(title, background="", sponsor=""):
    text = f"{title} {background} {sponsor}".lower()
    for sector, keywords in SECTOR_RULES:
        for kw in keywords:
            if kw in text:
                return sector
    return "Governance & General"


# Baseline fallbacks so no jurisdiction ever breaks if a government site is down
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
        "id": "BC-SESSION",
        "jurisdiction": "BC",
        "jurisdictionName": "British Columbia",
        "number": "Between Sessions",
        "title": "Awaiting Opening of the 44th Parliament",
        "sponsor": "Legislative Assembly of British Columbia",
        "stageStep": 1,
        "stageLabel": "Between Sessions",
        "latestActivity": "43rd Parliament dissolved; awaiting 44th Parliament",
        "background": "New bills will appear here automatically once the 44th Parliament of British Columbia convenes.",
        "officialUrl": "https://www.leg.bc.ca/parliamentary-business/bills",
    },
    {
        "id": "QC-SESSION",
        "jurisdiction": "QC",
        "jurisdictionName": "Quebec",
        "number": "Between Sessions",
        "title": "44th Legislature Opens December 1, 2026",
        "sponsor": "National Assembly of Quebec",
        "stageStep": 1,
        "stageLabel": "Between Sessions",
        "latestActivity": "Awaiting 44th Legislature, 1st Session",
        "background": "New bills will appear here automatically once the 44th Legislature of Quebec convenes.",
        "officialUrl": "https://www.assnat.qc.ca/en/travaux-parlementaires/projets-loi/projets-loi-44-1.html",
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
        "officialUrl": "https://www.legnb.ca/en/legislation/bills/61/3",
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
        "id": "NL-1",
        "jurisdiction": "NL",
        "jurisdictionName": "Newfoundland & Labrador",
        "number": "Bill 1",
        "title": "Current Legislation (51st General Assembly, 1st Session)",
        "sponsor": "House of Assembly of NL",
        "stageStep": 1,
        "stageLabel": "1st Reading",
        "latestActivity": "Active in the House of Assembly",
        "background": "Active legislation before the Newfoundland & Labrador House of Assembly.",
        "officialUrl": "https://www.assembly.nl.ca/HouseBusiness/Bills/ga51session1/",
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
        "sponsor": "7th Legislative Assembly of Nunavut",
        "stageStep": 3,
        "stageLabel": "Committee",
        "latestActivity": "In Committee review",
        "background": "Updates protection, permitting, and management of archaeological and palaeontological sites in Nunavut.",
        "officialUrl": "https://www.assembly.nu.ca/bills-and-legislation",
    },
]

# Full Alberta 31st Legislature, 2nd Session safety fallback
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
    if "royal assent" in text or "assented" in text or "assent" in text or "enacted" in text:
        return 5, "Royal Assent"
    if "third reading" in text or "3rd reading" in text or "passed" in text:
        return 4, "3rd Reading"
    if "committee" in text or "report stage" in text:
        return 3, "Committee"
    if "second reading" in text or "2nd reading" in text:
        return 2, "2nd Reading"
    return 1, "1st Reading"


def make_bill(jur_code, jur_name, num_clean, title, sponsor, status_text, url, stage_override=None):
    if stage_override:
        step, label = stage_override
    else:
        step, label = map_stage(status_text)
    clean_id = re.sub(r"[^A-Za-z0-9-]", "", str(num_clean).upper())
    clean_title = " ".join(title.split()).strip(" -–:.")
    clean_sponsor = " ".join(str(sponsor).split()).strip()
    background = f"Active legislation before the {clean_sponsor}: {clean_title}."
    return {
        "id": f"{jur_code}-{clean_id}",
        "jurisdiction": jur_code,
        "jurisdictionName": jur_name,
        "number": f"Bill {num_clean}" if not str(num_clean).lower().startswith("bill") else str(num_clean),
        "title": clean_title,
        "sponsor": clean_sponsor,
        "sector": classify_sector(clean_title, background, clean_sponsor),
        "stageStep": step,
        "stageLabel": label,
        "latestActivity": " ".join(str(status_text).split())[:180],
        "background": background,
        "officialUrl": url,
    }


def fetch_html_with_browser(browser, url, wait_ms=2500):
    context = browser.new_context(user_agent=HEADERS["User-Agent"])
    page = context.new_page()
    try:
        page.goto(url, wait_until="networkidle", timeout=40000)
        page.wait_for_timeout(wait_ms)
        return page.content()
    finally:
        context.close()


# ---------------------------------------------------------------------------
# 1. FEDERAL (Live Official JSON — ALL active bills, no cap)
# ---------------------------------------------------------------------------
def fetch_federal_bills():
    url = "https://www.parl.ca/legisinfo/en/bills/json"
    res = requests.get(url, headers=HEADERS, timeout=30)
    res.raise_for_status()
    raw = res.json()
    if not isinstance(raw, list):
        return []

    raw.sort(key=lambda x: str(x.get("LatestActivityDateTime") or ""), reverse=True)
    bills, seen = [], set()
    for item in raw:
        num = item.get("NumberCode")
        if not num or num in seen:
            continue
        seen.add(num)
        parl = item.get("ParliamentNumber", 45)
        sess = item.get("SessionNumber", 1)
        title = (item.get("ShortTitle") or item.get("LongTitle") or f"Federal Bill {num}").strip()
        long_title = (item.get("LongTitle") or title).strip()
        status = item.get("StatusName") or "Active in Parliament"
        sponsor = str(item.get("SponsorEn") or item.get("SponsorName") or f"{parl}th Parliament, Session {sess}").strip()
        step, label = map_stage(status)
        date_str = str(item.get("LatestActivityDateTime") or "")[:10]
        activity = f"{status} ({date_str})" if date_str else status

        bills.append({
            "id": f"FED-{num}",
            "jurisdiction": "FED",
            "jurisdictionName": "Federal (Canada)",
            "number": f"Bill {num}",
            "title": title,
            "sponsor": sponsor,
            "sector": classify_sector(title, long_title, sponsor),
            "stageStep": step,
            "stageLabel": label,
            "latestActivity": activity,
            "background": long_title,
            "officialUrl": f"https://www.parl.ca/legisinfo/en/bill/{parl}-{sess}/{num.lower()}",
        })
    return bills


# ---------------------------------------------------------------------------
# 2. ONTARIO (Paginated OLA card/heading parser)
# ---------------------------------------------------------------------------
def fetch_ontario_bills():
    base_url = "https://www.ola.org/en/legislative-business/bills/current"
    bills, seen = [], set()
    pattern = re.compile(r"^Bill\s+([A-Za-z]?\d+[A-Za-z]?)\s*,\s*(.+)$", re.I)

    for page_num in range(15):
        url = base_url if page_num == 0 else f"{base_url}?page={page_num}"
        res = requests.get(url, headers=HEADERS, timeout=25)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")

        page_found = 0
        for a in soup.select("a[href*='/bills/parliament-']"):
            text = " ".join(a.get_text(" ", strip=True).split())
            m = pattern.match(text)
            if not m:
                continue
            num, title = m.group(1).upper(), m.group(2).strip()
            if num in seen:
                continue
            seen.add(num)
            page_found += 1
            parent_text = a.parent.parent.get_text(" ", strip=True) if a.parent and a.parent.parent else text
            full_url = urljoin(base_url, a["href"])
            bills.append(make_bill("ON", "Ontario", num, title, "Legislative Assembly of Ontario", parent_text, full_url))

        if page_found == 0:
            break
    return bills


# ---------------------------------------------------------------------------
# 3. SASKATCHEWAN (Live Progress of Bills PDF via pypdf layout mode)
# ---------------------------------------------------------------------------
def fetch_saskatchewan_bills():
    if not PYPDF_AVAILABLE:
        return []
    landing_url = "https://www.legassembly.sk.ca/legislative-business/bills/"
    pdf_url = None
    try:
        res = requests.get(landing_url, headers=HEADERS, timeout=25)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(" ", strip=True).lower()
            if ".pdf" in href.lower() and ("progress" in text or "progress-of-bills" in href.lower()):
                pdf_url = urljoin(landing_url, href)
                break
    except Exception:
        pass

    if not pdf_url:
        pdf_url = "https://www.legassembly.sk.ca/media/obro0uvn/progress-of-bills.pdf"

    pdf_res = requests.get(pdf_url, headers=HEADERS, timeout=30)
    pdf_res.raise_for_status()
    reader = PdfReader(io.BytesIO(pdf_res.content))

    lines = []
    for page in reader.pages:
        try:
            text = page.extract_text(extraction_mode="layout") or ""
        except TypeError:
            text = page.extract_text() or ""
        lines.extend(text.splitlines())

    bills, seen = [], set()
    row_pattern = re.compile(
        r"^\s*(\d{1,3})\s+(?:EN\s+)?(?:\*\s+)?((?:The|An|Loi)\s+.+?)(?:\s{2,}|$)",
        re.I,
    )

    for line in lines:
        m = row_pattern.match(line)
        if not m:
            continue
        num = m.group(1)
        title = m.group(2).split("/")[0].strip()
        if num in seen or len(title) < 6:
            continue
        seen.add(num)
        bills.append(
            make_bill(
                "SK",
                "Saskatchewan",
                num,
                title,
                "Legislative Assembly of Saskatchewan (30th Legislature, 3rd Session)",
                "Active on Progress of Bills",
                pdf_url,
            )
        )
    return bills


# ---------------------------------------------------------------------------
# 4. MANITOBA (Exact 3-column table: Bill No. | Sponsor | Title)
# ---------------------------------------------------------------------------
def fetch_manitoba_bills():
    url = "https://web2.gov.mb.ca/bills/sess/index.php"
    res = requests.get(url, headers=HEADERS, timeout=25)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, "html.parser")
    bills, seen = [], set()

    for row in soup.select("table tr"):
        cols = [c.get_text(" ", strip=True) for c in row.find_all(["td", "th"])]
        if len(cols) < 3:
            continue
        m = re.search(r"^\s*(?:Bill\s*)?(\d+)\s*$", cols[0], re.I)
        if not m:
            continue
        num = m.group(1)
        sponsor = cols[1] or "Legislative Assembly of Manitoba"
        title = cols[2]
        if num in seen or len(title) < 5:
            continue
        seen.add(num)
        link = row.find("a", href=True)
        full_url = urljoin(url, link["href"]) if link else url
        status = cols[-1] if len(cols) >= 4 else "Active in Manitoba Legislature"
        bills.append(make_bill("MB", "Manitoba", num, title, sponsor, status, full_url))
    return bills


# ---------------------------------------------------------------------------
# 5. NEWFOUNDLAND & LABRADOR (All 37 rows across 51st Assembly, 1st Session)
# ---------------------------------------------------------------------------
def fetch_nl_bills():
    url = "https://www.assembly.nl.ca/HouseBusiness/Bills/ga51session1/"
    res = requests.get(url, headers=HEADERS, timeout=25)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, "html.parser")
    bills, seen = [], set()

    for row in soup.select("table tr"):
        cells = row.find_all(["td", "th"])
        cols = [" ".join(c.get_text(" ", strip=True).split()) for c in cells]
        if len(cols) < 2:
            continue
        m = re.search(r"^(?:Bill\s*)?(\d+[A-Za-z]?)$", cols[0], re.I)
        if not m:
            continue
        num = m.group(1).upper()
        title = cols[1]
        if num in seen or len(title) < 3 or title.lower() in ("title", "bill title"):
            continue
        seen.add(num)

        link = row.find("a", href=True)
        full_url = urljoin(url, link["href"]) if link else url

        date_cols = cols[2:]
        stage_override = None
        status_text = "Active in House of Assembly"
        if len(date_cols) >= 5 and date_cols[4]:
            stage_override = (5, "Royal Assent")
            status_text = f"Royal Assent ({date_cols[4]})"
        elif len(date_cols) >= 4 and date_cols[3]:
            stage_override = (4, "3rd Reading")
            status_text = f"3rd Reading ({date_cols[3]})"
        elif len(date_cols) >= 3 and date_cols[2]:
            stage_override = (3, "Committee")
            status_text = f"Committee ({date_cols[2]})"
        elif len(date_cols) >= 2 and date_cols[1]:
            stage_override = (2, "2nd Reading")
            status_text = f"2nd Reading ({date_cols[1]})"
        elif len(date_cols) >= 1 and date_cols[0]:
            stage_override = (1, "1st Reading")
            status_text = f"1st Reading ({date_cols[0]})"

        bills.append(
            make_bill(
                "NL",
                "Newfoundland & Labrador",
                num,
                title,
                "House of Assembly of NL (51st Assembly, 1st Session)",
                status_text,
                full_url,
                stage_override=stage_override,
            )
        )
    return bills


# ---------------------------------------------------------------------------
# 6. YUKON (All sitting tables on Progress of Bills: Fall & Spring)
# ---------------------------------------------------------------------------
def fetch_yukon_bills():
    url = "https://yukonassembly.ca/house-business/progress-bills"
    res = requests.get(url, headers=HEADERS, timeout=25)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, "html.parser")
    bills, seen = [], set()

    for row in soup.select("table tr"):
        cells = row.find_all(["td", "th"])
        cols = [" ".join(c.get_text(" ", strip=True).split()) for c in cells]
        if len(cols) < 2:
            continue
        m = re.search(r"^(?:Bill\s*)?(\d+[A-Za-z]?)$", cols[0], re.I)
        if not m:
            continue
        num = m.group(1).upper()
        title = cols[1]
        if num in seen or len(title) < 4 or title.lower() in ("title", "bill title"):
            continue
        seen.add(num)

        sponsor = cols[2] if len(cols) >= 3 and cols[2] else "Yukon Legislative Assembly"
        link = row.find("a", href=True)
        full_url = urljoin(url, link["href"]) if link else url

        stage_cols = cols[3:]
        non_empty = [c for c in stage_cols if c]
        status_text = non_empty[-1] if non_empty else "Active on the Yukon Order Paper"
        stage_override = None
        if len(stage_cols) >= 5 and stage_cols[-1]:
            stage_override = (5, "Royal Assent")
            status_text = f"Assented ({stage_cols[-1]})"
        elif len(stage_cols) >= 4 and stage_cols[-2]:
            stage_override = (4, "3rd Reading")
            status_text = f"3rd Reading ({stage_cols[-2]})"

        bills.append(
            make_bill(
                "YT",
                "Yukon",
                num,
                title,
                sponsor,
                status_text,
                full_url,
                stage_override=stage_override,
            )
        )
    return bills


# ---------------------------------------------------------------------------
# 7. NORTHWEST TERRITORIES (Paginated Drupal view cards + tables)
# ---------------------------------------------------------------------------
def fetch_nwt_bills():
    base_url = "https://www.ntlegislativeassembly.ca/documents-proceedings/bills"
    bills, seen = [], set()
    bill_re = re.compile(r"Bill\s+(\d+[A-Za-z]?)\s*[:\-–]?\s*(.*)", re.I)

    for page_num in range(12):
        url = base_url if page_num == 0 else f"{base_url}?page={page_num}"
        res = requests.get(url, headers=HEADERS, timeout=25)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
        page_found = 0

        containers = soup.select(".views-row, article, table tr, .node--type-bill")
        for el in containers:
            text = " ".join(el.get_text(" ", strip=True).split())
            m = bill_re.search(text)
            if not m:
                continue
            num = m.group(1).upper()
            if num in seen:
                continue

            title = ""
            link = el.find("a", href=True)
            if link:
                link_text = " ".join(link.get_text(" ", strip=True).split())
                lm = bill_re.match(link_text)
                if lm and lm.group(2).strip():
                    title = lm.group(2).strip()
                elif len(link_text) > 5 and not link_text.lower().startswith("bill "):
                    title = link_text
            if not title:
                title = m.group(2).strip()[:160]
            if len(title) < 4:
                continue

            seen.add(num)
            page_found += 1
            full_url = urljoin(base_url, link["href"]) if link else url
            bills.append(
                make_bill(
                    "NT",
                    "Northwest Territories",
                    num,
                    title,
                    "Legislative Assembly of the NWT (20th Assembly, 1st Session)",
                    text,
                    full_url,
                )
            )

        if page_found == 0:
            break
    return bills


# ---------------------------------------------------------------------------
# 8. PRINCE EDWARD ISLAND (Playwright-rendered Drupal bill list)
# ---------------------------------------------------------------------------
def fetch_pei_bills(browser):
    url = "https://www.assembly.pe.ca/legislative-business/house-records/bills"
    html = ""
    if browser:
        try:
            html = fetch_html_with_browser(browser, url, wait_ms=3500)
        except Exception as e:
            print(f"[PE] Playwright note: {e}")
    if not html:
        res = requests.get(url, headers=HEADERS, timeout=25)
        res.raise_for_status()
        html = res.text

    soup = BeautifulSoup(html, "html.parser")
    bills, seen = [], set()
    bill_re = re.compile(r"Bill\s+(?:No\.?\s*)?(\d+[A-Za-z]?)\s*[:\-–,]?\s*(.*)", re.I)

    for row in soup.select("table tr"):
        cols = [" ".join(c.get_text(" ", strip=True).split()) for c in row.find_all(["td", "th"])]
        if len(cols) < 2:
            continue
        m = re.search(r"^(?:Bill\s*(?:No\.?\s*)?)?(\d+[A-Za-z]?)$", cols[0], re.I)
        if not m:
            continue
        num = m.group(1).upper()
        title = cols[1]
        if num in seen or len(title) < 4:
            continue
        seen.add(num)
        link = row.find("a", href=True)
        full_url = urljoin(url, link["href"]) if link else url
        status = cols[-1] if len(cols) >= 3 and cols[-1] != title else "Active in PEI Legislative Assembly"
        bills.append(make_bill("PE", "Prince Edward Island", num, title, "Legislative Assembly of PEI", status, full_url))

    if len(bills) < 3:
        for el in soup.select(".views-row, article, li, a"):
            text = " ".join(el.get_text(" ", strip=True).split())
            m = bill_re.match(text)
            if not m:
                continue
            num, title = m.group(1).upper(), m.group(2).strip()
            if num in seen or len(title) < 5:
                continue
            seen.add(num)
            link = el if el.name == "a" and el.get("href") else el.find("a", href=True)
            full_url = urljoin(url, link["href"]) if link else url
            bills.append(make_bill("PE", "Prince Edward Island", num, title, "Legislative Assembly of PEI", text, full_url))

    return bills


# ---------------------------------------------------------------------------
# 9. PAGINATED TABLE SCRAPER (Nova Scotia)
# ---------------------------------------------------------------------------
def fetch_paginated_table_bills(base_url, jur_code, jur_name, default_sponsor, max_pages=10):
    bills, seen = [], set()
    for page_num in range(max_pages):
        url = base_url if page_num == 0 else f"{base_url}?page={page_num}"
        res = requests.get(url, headers=HEADERS, timeout=25)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")

        page_found = 0
        for row in soup.select("table tr"):
            cols = [c.get_text(" ", strip=True) for c in row.find_all(["td", "th"])]
            if len(cols) < 2:
                continue
            num_raw, title_raw = cols[0], cols[1]
            if not re.search(r"\d+", num_raw) and len(cols) >= 3 and re.search(r"\d+", cols[1]):
                num_raw, title_raw = cols[1], cols[2]
            m = re.search(r"(?:Bill\s*)?([A-Za-z]{0,2}-?\d+[A-Za-z]?)", num_raw, re.I)
            if not m or len(title_raw) < 4:
                continue
            num = m.group(1).upper()
            if num in seen:
                continue
            seen.add(num)
            page_found += 1
            link = row.find("a", href=True)
            full_url = urljoin(base_url, link["href"]) if link else base_url
            status = cols[-1] if len(cols) >= 3 and cols[-1] != title_raw else f"Active in {jur_name}"
            bills.append(make_bill(jur_code, jur_name, num, title_raw, default_sponsor, status, full_url))

        if page_found == 0:
            break
    return bills


# ---------------------------------------------------------------------------
# 10. GENERIC TABLE + LIST PARSER (AB, BC, QC, NB, NU)
# ---------------------------------------------------------------------------
def parse_bills_from_html(html, url, jur_code, jur_name, default_sponsor):
    soup = BeautifulSoup(html, "html.parser")
    bills, seen = [], set()

    for row in soup.select("table tr"):
        cols = [c.get_text(" ", strip=True) for c in row.find_all(["td", "th"])]
        if len(cols) < 2:
            continue
        num_raw, title_raw = cols[0], cols[1]
        if not re.search(r"\d+", num_raw) and len(cols) >= 3 and re.search(r"\d+", cols[1]):
            num_raw, title_raw = cols[1], cols[2]
        m = re.search(r"(?:Bill\s*)?([A-Za-z]{0,2}-?\d+[A-Za-z]?)", num_raw, re.I)
        if not m or len(title_raw) < 4:
            continue
        num = m.group(1).upper()
        if num in seen:
            continue
        seen.add(num)
        link = row.find("a", href=True)
        full_url = urljoin(url, link["href"]) if link else url
        status = cols[-1] if len(cols) >= 3 and cols[-1] != title_raw else f"Active in {jur_name}"
        bills.append(make_bill(jur_code, jur_name, num, title_raw, default_sponsor, status, full_url))

    if len(bills) < 3:
        bill_pattern = re.compile(r"^\s*Bill\s+([A-Za-z]{0,2}-?\d+[A-Za-z]?)\s*[\.\-–:,]?\s+(.{5,220})$", re.I)
        for el in soup.select("li, a, p, h3, h4"):
            text = " ".join(el.get_text(" ", strip=True).split())
            m = bill_pattern.match(text)
            if not m:
                continue
            num, title_raw = m.group(1).upper(), m.group(2).strip(" *$()")
            if num in seen or len(title_raw) < 5:
                continue
            seen.add(num)
            link = el if el.name == "a" and el.get("href") else el.find("a", href=True)
            full_url = urljoin(url, link["href"]) if link else url
            bills.append(make_bill(jur_code, jur_name, num, title_raw, default_sponsor, text, full_url))

    return bills


GENERIC_SOURCES = [
    ("AB", "Alberta", "https://www.assembly.ab.ca/assembly-business/bills/bills-by-legislature", "Legislative Assembly of Alberta"),
    ("BC", "British Columbia", "https://www.leg.bc.ca/parliamentary-business/bills", "Legislative Assembly of British Columbia"),
    ("QC", "Quebec", "https://www.assnat.qc.ca/en/travaux-parlementaires/projets-loi/projets-loi-44-1.html", "National Assembly of Quebec"),
    ("NB", "New Brunswick", "https://www.legnb.ca/en/legislation/bills/61/3", "Legislative Assembly of New Brunswick"),
    ("NU", "Nunavut", "https://www.assembly.nu.ca/bills-and-legislation", "Legislative Assembly of Nunavut"),
]


def ensure_sectors(bill_list):
    for b in bill_list:
        if not b.get("sector"):
            b["sector"] = classify_sector(b.get("title", ""), b.get("background", ""), b.get("sponsor", ""))
    return bill_list


def choose_best(code, live, existing_by_jur, fallback_by_jur):
    saved = existing_by_jur.get(code, [])
    fallback = fallback_by_jur.get(code, [])
    best_backup = saved if len(saved) >= len(fallback) else fallback
    if live and len(live) >= min(3, len(best_backup)):
        print(f"[{code}] Live fetch succeeded: {len(live)} bills.")
        return ensure_sectors(live)
    print(f"[{code}] Using backup/fallback: {len(best_backup)} bills (live returned {len(live)}).")
    return ensure_sectors(best_backup)


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
        b["sector"] = classify_sector(b.get("title", ""), b.get("background", ""), b.get("sponsor", ""))
        fallback_by_jur.setdefault(b["jurisdiction"], []).append(b)

    final_bills = []

    dedicated = [
        ("FED", fetch_federal_bills),
        ("ON", fetch_ontario_bills),
        ("SK", fetch_saskatchewan_bills),
        ("MB", fetch_manitoba_bills),
        ("NL", fetch_nl_bills),
        ("YT", fetch_yukon_bills),
        ("NT", fetch_nwt_bills),
        ("NS", lambda: fetch_paginated_table_bills(
            "https://nslegislature.ca/legislative-business/bills-statutes/current-bills",
            "NS", "Nova Scotia", "Nova Scotia House of Assembly",
        )),
    ]

    for code, fetcher in dedicated:
        try:
            live = fetcher()
        except Exception as e:
            print(f"[{code}] Fetch error: {e}")
            live = []
        final_bills.extend(choose_best(code, live, existing_by_jur, fallback_by_jur))

    pw_manager = None
    browser = None
    try:
        if PLAYWRIGHT_AVAILABLE:
            pw_manager = sync_playwright().start()
            browser = pw_manager.chromium.launch(headless=True)

        try:
            pe_live = fetch_pei_bills(browser)
        except Exception as e:
            print(f"[PE] Fetch error: {e}")
            pe_live = []
        final_bills.extend(choose_best("PE", pe_live, existing_by_jur, fallback_by_jur))

        for code, name, url, sponsor in GENERIC_SOURCES:
            live = []
            try:
                res = requests.get(url, headers=HEADERS, timeout=20)
                res.raise_for_status()
                live = parse_bills_from_html(res.text, url, code, name, sponsor)
            except Exception as e:
                print(f"[{code}] Fast HTTP note: {e}")

            if len(live) < 3 and browser:
                try:
                    print(f"[{code}] Rendering JS page with Playwright...")
                    html = fetch_html_with_browser(browser, url)
                    js_bills = parse_bills_from_html(html, url, code, name, sponsor)
                    if len(js_bills) > len(live):
                        live = js_bills
                except Exception as e:
                    print(f"[{code}] Playwright note: {e}")

            final_bills.extend(choose_best(code, live, existing_by_jur, fallback_by_jur))
    finally:
        if browser:
            browser.close()
        if pw_manager:
            pw_manager.stop()

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
