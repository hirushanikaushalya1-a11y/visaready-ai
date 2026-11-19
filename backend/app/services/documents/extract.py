"""Deterministic document classification and field extraction.

Every extracted value records the page number and a short snippet so findings can cite exactly
where information came from. When an AI provider is configured, `ai_extract` (services/ai) may add
fields with method='ai'; deterministic results are kept alongside so they can be compared.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from statistics import median

from app.services.documents.text import PageText

# ------------------------------------------------------------------ classification
# (pattern, weight). Patterns are matched case-insensitively against the full text.
CLASSIFIER: dict[str, list[tuple[str, float]]] = {
    "passport": [(r"\bpassport\b", 2), (r"P<[A-Z<]{3}", 6), (r"date of expiry|date of issue", 1.5), (r"place of birth", 1), (r"nationality", 1)],
    "bank_statement": [(r"\bstatement\b", 2), (r"account (?:no|number|holder|name)", 2.5), (r"(?:opening|closing|available) balance", 3),
                       (r"\bdebit\b", 1), (r"\bcredit\b", 1), (r"\bbalance\b", 1), (r"\bbank\b", 1)],
    "salary_slip": [(r"pay ?slip|salary slip|salary advice", 5), (r"gross (?:pay|salary)", 2), (r"net (?:pay|salary)", 2), (r"deductions", 1.5), (r"\bEPF\b|\bETF\b|provident fund", 1)],
    "employment_letter": [(r"to whom it may concern", 1.5), (r"(?:is|was) employed|has been working|employment confirmation|currently working", 4),
                          (r"designation|position of|job title", 1.5), (r"date of (?:joining|appointment)|joined (?:us|the company)", 2), (r"human resources|HR manager", 1)],
    "experience_certificate": [(r"experience certificate|certificate of experience|service certificate", 6), (r"worked with us|served (?:as|in)", 2)],
    "academic_certificate": [(r"(?:degree|diploma) of|bachelor|master of|has been (?:awarded|conferred)|certificate of", 2.5), (r"university|college|institute", 1), (r"conferred|awarded|class honours|first class|second class", 2)],
    "academic_transcript": [(r"transcript|statement of results|mark ?sheet|academic record", 5), (r"\bGPA\b|grade point|credits?", 2), (r"semester|course code|module", 1.5)],
    "english_test_result": [(r"\bIELTS\b|\bTOEFL\b|\bPTE\b|Pearson Test|Duolingo English|Cambridge English", 5), (r"overall (?:band|score)", 3), (r"listening|reading|writing|speaking", 1)],
    "offer_letter": [(r"offer of (?:admission|a place)|letter of (?:offer|acceptance)|unconditional offer|conditional offer", 5),
                     (r"\bCAS\b|confirmation of acceptance for studies|confirmation of enrolment|\bCoE\b|designated learning institution|\bDLI\b", 4), (r"tuition fee", 1.5), (r"commencement|course start", 1)],
    "employment_contract": [(r"employment contract|contract of employment|offer of employment|job offer", 5), (r"certificate of sponsorship|\bLMIA\b|nominat", 3), (r"annual salary|probation|notice period", 1.5)],
    "birth_certificate": [(r"birth certificate|certificate of birth|registration of birth", 6), (r"name of (?:father|mother)", 2), (r"place of birth", 1)],
    "marriage_certificate": [(r"marriage certificate|certificate of marriage|registration of marriage", 6), (r"bride|bridegroom|husband|wife", 1.5)],
    "tax_record": [(r"income tax|tax return|tax assessment|\bTIN\b|inland revenue|form 16", 5), (r"assessment year|taxable income", 2)],
    "business_registration": [(r"business registration|certificate of incorporation|registrar of companies|business name", 5), (r"registration no", 1.5)],
    "visa_refusal": [(r"refus(?:al|ed)|not satisfied|decision to refuse|application (?:has been|is) refused", 4), (r"immigration rules|paragraph \d|visa application", 1.5), (r"right of (?:appeal|review)|administrative review", 2)],
    "affidavit": [(r"affidavit|sworn (?:before|statement)|solemnly (?:declare|affirm)|commissioner (?:of|for) oaths|notary public", 5)],
    "sponsorship_letter": [(r"sponsor(?:ship)? letter|I (?:will|shall) (?:sponsor|bear)|undertake to (?:support|bear)|financial support for", 5)],
    "cv": [(r"curriculum vitae|\bresume\b|\brésumé\b", 5), (r"work experience|professional experience", 2), (r"\bskills\b", 1), (r"education", 1)],
    "sop": [(r"statement of purpose|personal statement|study plan", 5), (r"my (?:goal|aim|interest|passion)|I (?:am|was) (?:interested|motivated)", 2)],
    "police_certificate": [(r"police (?:clearance|certificate|report)|certificate of good conduct|criminal record", 6)],
    "medical_report": [(r"tuberculosis|\bTB\b|chest x-?ray|medical examination|panel physician", 5)],
    "travel_document": [(r"\bvisa\b", 1.5), (r"valid (?:from|until)|entries|type of visa|residence permit|biometric residence", 3), (r"arrival|departure|immigration stamp", 1.5)],
    "professional_registration": [(r"registration (?:certificate|number)|licen[cs]e to practi[cs]e|registered (?:member|engineer|nurse)|council", 4)],
    "skills_assessment": [(r"skills assessment|assessing authority|suitable skilled occupation", 6)],
}


@dataclass
class Classification:
    doc_type: str | None
    confidence: float
    scores: dict[str, float]


def classify(text: str, declared: str | None = None) -> Classification:
    if not text.strip():
        return Classification(None, 0.0, {})
    scores: dict[str, float] = {}
    for doc_type, patterns in CLASSIFIER.items():
        s = 0.0
        for pat, w in patterns:
            hits = len(re.findall(pat, text, flags=re.I))
            if hits:
                s += w * min(hits, 3) ** 0.5
        if s:
            scores[doc_type] = round(s, 2)
    if not scores:
        return Classification(None, 0.0, {})
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    best, best_score = ranked[0]
    runner = ranked[1][1] if len(ranked) > 1 else 0.0
    margin = (best_score - runner) / best_score
    confidence = min(1.0, (best_score / 8.0)) * (0.5 + 0.5 * margin)
    # If the applicant's declared type also scores well, prefer it (they know their document).
    if declared and declared in scores and scores[declared] >= 0.6 * best_score:
        return Classification(declared, round(min(1.0, confidence + 0.2), 2), scores)
    if best_score < 3:
        return Classification(None, round(confidence, 2), scores)
    return Classification(best, round(confidence, 2), scores)


# ------------------------------------------------------------------ fields
@dataclass
class Field:
    name: str
    value: str
    normalized: str | None
    page: int | None
    snippet: str | None
    confidence: float
    method: str = "pattern"


MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
DATE_PATTERNS = [
    (re.compile(r"\b(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})\b"), "ymd"),
    (re.compile(r"\b(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})\b"), "dmy"),
    (re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?[ -]([A-Za-z]{3,9})[ ,-]+(\d{4})\b"), "d_mon_y"),
    (re.compile(r"\b([A-Za-z]{3,9}) (\d{1,2})(?:st|nd|rd|th)?,? (\d{4})\b"), "mon_d_y"),
]


def parse_date(s: str) -> date | None:
    s = s.strip()
    for rx, kind in DATE_PATTERNS:
        m = rx.search(s)
        if not m:
            continue
        try:
            if kind == "ymd":
                return date(int(m[1]), int(m[2]), int(m[3]))
            if kind == "dmy":  # South Asian / UK convention: day first
                return date(int(m[3]), int(m[2]), int(m[1]))
            if kind == "d_mon_y":
                mon = MONTHS.get(m[2][:3].lower())
                return date(int(m[3]), mon, int(m[1])) if mon else None
            if kind == "mon_d_y":
                mon = MONTHS.get(m[1][:3].lower())
                return date(int(m[3]), mon, int(m[2])) if mon else None
        except ValueError:
            continue
    return None


def _snippet(text: str, start: int, end: int, pad: int = 40) -> str:
    return re.sub(r"\s+", " ", text[max(0, start - pad): end + pad]).strip()[:200]


def normalize_name(name: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z ]", " ", name.upper())).strip()


AMOUNT_RX = re.compile(r"(?<![\d.])(\d{1,3}(?:,\d{2,3})+(?:\.\d{2})?|\d+\.\d{2})(?![\d])")


def parse_amount(s: str) -> float | None:
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return None


# ---------------- MRZ (ICAO 9303 TD3 — passports)
def _mrz_check(data: str) -> int:
    weights = (7, 3, 1)
    total = 0
    for i, ch in enumerate(data):
        if ch.isdigit():
            v = int(ch)
        elif ch.isalpha():
            v = ord(ch) - 55
        else:
            v = 0
        total += v * weights[i % 3]
    return total % 10


def _mrz_date(yymmdd: str, future: bool) -> date | None:
    try:
        yy, mm, dd = int(yymmdd[:2]), int(yymmdd[2:4]), int(yymmdd[4:6])
    except ValueError:
        return None
    now_yy = datetime.now().year % 100
    century = 2000 if (future or yy <= now_yy) else 1900
    try:
        return date(century + yy, mm, dd)
    except ValueError:
        return None


def parse_mrz(pages: list[PageText]) -> list[Field]:
    for p in pages:
        lines = [re.sub(r"\s", "", ln).upper().replace("«", "<") for ln in p.text.splitlines()]
        for i in range(len(lines) - 1):
            l1, l2 = lines[i], lines[i + 1]
            if not (l1.startswith("P") and len(l1) >= 40 and "<<" in l1 and len(l2) >= 40):
                continue
            l1, l2 = l1[:44].ljust(44, "<"), l2[:44].ljust(44, "<")
            number, dob, expiry = l2[0:9], l2[13:19], l2[21:27]
            checks_ok = sum([
                _mrz_check(number) == int(l2[9]) if l2[9].isdigit() else False,
                _mrz_check(dob) == int(l2[19]) if l2[19].isdigit() else False,
                _mrz_check(expiry) == int(l2[27]) if l2[27].isdigit() else False,
            ])
            conf = {3: 0.97, 2: 0.8, 1: 0.55}.get(checks_ok, 0.3)
            names = l1[5:44].split("<<", 1)
            surname = names[0].replace("<", " ").strip()
            given = names[1].replace("<", " ").strip() if len(names) > 1 else ""
            snippet = f"{l1}\n{l2}"
            d_dob, d_exp = _mrz_date(dob, False), _mrz_date(expiry, True)
            out = [
                Field("surname", surname, normalize_name(surname), p.page_number, snippet, conf, "mrz"),
                Field("given_names", given, normalize_name(given), p.page_number, snippet, conf, "mrz"),
                Field("full_name", f"{given} {surname}".strip(), normalize_name(f"{given} {surname}"), p.page_number, snippet, conf, "mrz"),
                Field("passport_number", number.replace("<", ""), number.replace("<", ""), p.page_number, snippet, conf, "mrz"),
                Field("nationality_iso3", l2[10:13].replace("<", ""), l2[10:13].replace("<", ""), p.page_number, snippet, conf, "mrz"),
                Field("sex", l2[20], l2[20], p.page_number, snippet, conf, "mrz"),
            ]
            if d_dob:
                out.append(Field("date_of_birth", dob, d_dob.isoformat(), p.page_number, snippet, conf, "mrz"))
            if d_exp:
                out.append(Field("expiry_date", expiry, d_exp.isoformat(), p.page_number, snippet, conf, "mrz"))
            out.append(Field("mrz_check_digits_valid", str(checks_ok), str(checks_ok), p.page_number, None, 1.0, "mrz"))
            return out
    return []


# ---------------- labelled fields
LABELLED = [
    ("full_name", r"(?:^|\n)\s*(?:full name|name of (?:the )?(?:applicant|candidate|student|employee|account holder)|candidate name|student name|account (?:holder|name)|name)\s*[:\-]\s*(?:mr\.?|mrs\.?|ms\.?|miss)?\s*([A-Za-z][A-Za-z .'\-]{2,80})"),
    ("date_of_birth", r"(?:date of birth|d\.?o\.?b\.?|birth date)\s*[:\-]?\s*([0-9A-Za-z ,/.\-]{6,20})"),
    ("passport_number", r"passport (?:no|number)\.?\s*[:\-]?\s*([A-Z]{1,2}\d{6,8})"),
    ("account_number", r"account (?:no|number)\.?\s*[:\-]?\s*([0-9\- ]{6,24})"),
    ("employer_name", r"(?:employer|company name|organisation|organization)\s*[:\-]\s*([A-Za-z0-9 &.,'\-()]{2,80})"),
    ("job_title", r"(?:designation|job title|position)\s*[:\-]\s*([A-Za-z &/\-]{2,60})"),
    ("employment_start", r"(?:date of (?:joining|appointment|commencement)|joined (?:on|us on)|employed (?:since|from)|start date)\s*[:\-]?\s*([0-9A-Za-z ,/.\-]{6,20})"),
    ("employment_end", r"(?:date of (?:leaving|resignation|relieving)|end date|left (?:on|the company on))\s*[:\-]?\s*([0-9A-Za-z ,/.\-]{6,20})"),
    ("closing_balance", r"(?:closing|available|ledger) balance\s*[:\-]?\s*(?:[A-Z]{3}|Rs\.?|LKR|INR|BDT|NPR|USD|GBP)?\s*([\d,]+\.\d{2})"),
    ("currency", r"\b(LKR|INR|BDT|NPR|USD|GBP|CAD|AUD|EUR)\b"),
    ("statement_period", r"(?:statement period|period|from)\s*[:\-]?\s*([0-9A-Za-z ,/.\-]{6,20}\s*(?:to|-|–)\s*[0-9A-Za-z ,/.\-]{6,20})"),
    ("overall_score", r"overall (?:band )?(?:score)?\s*[:\-]?\s*(\d{1,3}(?:\.\d)?)"),
    ("test_date", r"(?:test date|date of test)\s*[:\-]?\s*([0-9A-Za-z ,/.\-]{6,20})"),
    ("institution", r"(?:university|college|institute) of [A-Z][A-Za-z ]{2,60}|[A-Z][A-Za-z ]{2,60} (?:University|College|Institute)"),
    ("course_name", r"(?:course|programme|program)\s*(?:title|name)?\s*[:\-]\s*([A-Za-z ,&()\-]{4,120})"),
    ("award_date", r"(?:date of (?:award|conferment|graduation)|awarded on|conferred on)\s*[:\-]?\s*([0-9A-Za-z ,/.\-]{6,20})"),
    ("salary", r"(?:gross (?:salary|pay)|basic salary|annual salary|monthly salary|net (?:pay|salary))\s*[:\-]?\s*(?:[A-Z]{3}|Rs\.?)?\s*([\d,]+(?:\.\d{2})?)"),
    ("cas_number", r"\bCAS (?:number|no\.?|reference)?\s*[:\-]?\s*([A-Z0-9]{14})\b"),
    ("refusal_date", r"(?:date of decision|decision date|date)\s*[:\-]\s*([0-9A-Za-z ,/.\-]{6,20})"),
]
DATE_FIELDS = {"date_of_birth", "employment_start", "employment_end", "test_date", "award_date", "refusal_date"}


def extract_labelled(pages: list[PageText]) -> list[Field]:
    out: list[Field] = []
    for p in pages:
        for name, pat in LABELLED:
            for m in re.finditer(pat, p.text, flags=re.I):
                raw = (m.group(1) if m.groups() else m.group(0)).strip()
                raw = re.split(r"\s{3,}|\n", raw)[0].strip(" .,:")
                if not raw:
                    continue
                norm: str | None = raw
                conf = 0.6
                if name in DATE_FIELDS:
                    d = parse_date(raw)
                    if not d:
                        continue
                    norm, conf = d.isoformat(), 0.7
                elif name == "full_name":
                    norm = normalize_name(raw)
                    if len(norm.split()) < 2:
                        continue
                elif name in ("closing_balance", "salary"):
                    amt = parse_amount(raw)
                    if amt is None:
                        continue
                    norm = f"{amt:.2f}"
                elif name == "currency":
                    norm = raw.upper()
                out.append(Field(name, raw, norm, p.page_number, _snippet(p.text, m.start(), m.end()), conf))
                if name in ("currency",):
                    break
    return out


# ---------------- bank statement transactions (balance-delta method)
TXN_LINE = re.compile(r"^\s*(\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}|\d{4}-\d{2}-\d{2}|\d{1,2}[ -][A-Za-z]{3}[ -]\d{2,4})\b(.*)$")


@dataclass
class Txn:
    date: date | None
    description: str
    balance: float
    delta: float | None
    page: int
    line: str


def extract_transactions(pages: list[PageText]) -> list[Txn]:
    txns: list[Txn] = []
    prev_balance: float | None = None
    for p in pages:
        for line in p.text.splitlines():
            m = TXN_LINE.match(line)
            if not m:
                continue
            amounts = [parse_amount(a) for a in AMOUNT_RX.findall(m.group(2))]
            amounts = [a for a in amounts if a is not None]
            if not amounts:
                continue
            balance = amounts[-1]
            delta = None if prev_balance is None else round(balance - prev_balance, 2)
            desc = re.sub(r"\s{2,}", " ", AMOUNT_RX.sub("", m.group(2))).strip()[:120]
            txns.append(Txn(parse_date(m.group(1)), desc, balance, delta, p.page_number, line.strip()[:200]))
            prev_balance = balance
    return txns


def significant_deposits(txns: list[Txn]) -> list[Txn]:
    """Credits that are large relative to the account's own typical activity. This is a prompt to
    prepare a source-of-funds explanation, NOT an accusation: legitimate deposits are common."""
    credits = [t for t in txns if t.delta and t.delta > 0]
    if len(txns) < 3 or not credits:
        return []
    typical = median([t.delta for t in credits])
    avg_balance = sum(t.balance for t in txns) / len(txns)
    threshold = max(3 * typical, 0.25 * avg_balance)
    return [t for t in credits if t.delta >= threshold and t.delta > 0]


# ---------------- missing pages ("Page x of y")
def missing_page_hints(pages: list[PageText]) -> list[str]:
    seen: set[int] = set()
    total = None
    for p in pages:
        for m in re.finditer(r"page\s+(\d{1,3})\s*(?:of|/)\s*(\d{1,3})", p.text, flags=re.I):
            seen.add(int(m[1]))
            total = max(total or 0, int(m[2]))
    if total and total <= 200:
        missing = sorted(set(range(1, total + 1)) - seen)
        if missing and len(pages) < total:
            return [f"The document says it has {total} pages but pages {', '.join(map(str, missing[:10]))} were not found."]
    return []


def extract_all(pages: list[PageText]) -> list[Field]:
    fields = parse_mrz(pages) + extract_labelled(pages)
    # De-duplicate identical (name, normalized) pairs keeping highest confidence.
    best: dict[tuple[str, str | None], Field] = {}
    for f in fields:
        k = (f.name, f.normalized)
        if k not in best or f.confidence > best[k].confidence:
            best[k] = f
    return list(best.values())
