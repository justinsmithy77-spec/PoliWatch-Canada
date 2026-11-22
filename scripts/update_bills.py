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

    # Direct fallback to the current 30th Legislature, 3rd Session Progress of Bills PDF
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
    # Matches: "<BillNo>  [EN]  [*]  <Title>   <Member/Dates>"
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
