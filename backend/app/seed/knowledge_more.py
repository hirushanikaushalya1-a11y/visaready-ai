"""Requirements for Ireland, France, Italy, Malta, Germany, Netherlands, Sweden, Finland, Lithuania,
Hungary and Georgia (researched Nov 2026).

Provenance rules (same as the rest of the knowledge base):
* Every item cites an official source: the national immigration authority / foreign ministry where
  its page was identified, otherwise the European Commission's EU Immigration Portal page for that
  country and route.
* All items are seeded as pending_review. Administrators must confirm each against the official
  source before marking it verified.
* Money figures appear only inside `notes` as "commonly cited — confirm"; they are never enforced.
* Wording is deliberately conservative where sources disagreed (noted in descriptions).
"""

EU = "https://home-affairs.ec.europa.eu/policies/migration-and-asylum/eu-immigration-portal/"
EU_PUB = "European Commission – EU Immigration Portal"
NON_ENGLISH = {"fact": "documents.has_non_english", "op": "truthy"}
PARTNER = {"fact": "family.relation_to_principal", "op": "in", "value": ["spouse", "partner"]}
CHILD = {"fact": "family.relation_to_principal", "op": "eq", "value": "child"}


def R(key, title, level, description, docs, src, **kw):
    d = dict(key=key, title=title, level=level, description=description, document_types=docs, source_url=src)
    if "when" in kw:
        d["applies_when"] = kw.pop("when")
    if "money" in kw:
        d["financial_requirement"] = {"amount": None, "currency": kw.pop("currency", "EUR"), "notes": kw.pop("money")}
    d.update(kw)
    return d


def passport(src, extra=""):
    return R("valid-passport", "Valid passport", "mandatory",
             "A valid passport (copy of the bio page and any previous visas)." + extra, ["passport"], src)


def translations(src, language="the language accepted by the authority"):
    return R("translations", "Certified translations of foreign-language documents", "conditional",
             f"Documents not in {language} usually need a certified (sworn) translation, and some need legalisation or an apostille.",
             [], src, when=NON_ENGLISH, translation=True)


def health_insurance(src, detail="covering the whole stay"):
    return R("health-insurance", "Health insurance", "mandatory", f"Health insurance {detail}.", ["other"], src)


def partner_rel(src, extra=""):
    return R("relationship-partner", "Proof of marriage or partnership", "conditional",
             "Marriage or registered-partnership certificate (legalised/apostilled where required) and, for unmarried partners, "
             "evidence of a durable relationship such as living together." + extra,
             ["marriage_certificate", "relationship_evidence"], src, when=PARTNER)


def child_rel(src):
    return R("relationship-child", "Birth certificates for children", "conditional",
             "Full birth certificates showing both parents, plus consent of the other parent where only one parent is moving.",
             ["birth_certificate"], src, when=CHILD)


def sponsor_status(src, extra=""):
    return R("sponsor-status", "Evidence of the family member's residence status", "mandatory",
             "A copy of the residence permit / visa of the person you are joining." + extra, ["travel_document"], src)


# ------------------------------------------------------------------------------------------------
SOURCES = []
CATEGORIES = []


def add(country, sources, cats):
    SOURCES.extend((country, t, u, p) for t, u, p in sources)
    CATEGORIES.extend((country,) + c for c in cats)


# ---- Ireland -----------------------------------------------------------------------------------
IE_ST, IE_WORK, IE_FAM = EU + "student-ireland_en", EU + "highly-qualified-worker-ireland_en", EU + "family-member-ireland_en"
add("IE", [("Student – Ireland", IE_ST, EU_PUB), ("Highly qualified worker – Ireland", IE_WORK, EU_PUB),
           ("Family member – Ireland", IE_FAM, EU_PUB)], [
    ("student", "ie-student", "Study visa (Stamp 2)", "For full-time study on a course listed on Ireland's Interim List of Eligible Programmes (ILEP).", IE_ST, [
        passport(IE_ST),
        R("ilep-acceptance", "Letter of acceptance on an ILEP-listed course", "mandatory",
          "A letter of acceptance from the college for a full-time course on the Interim List of Eligible Programmes (ILEP).", ["offer_letter"], IE_ST),
        R("fees-paid", "Evidence that course fees are paid", "mandatory", "Receipt or confirmation from the college that fees have been paid.", ["offer_letter", "other"], IE_ST),
        R("finances", "Evidence of sufficient finances", "mandatory",
          "Bank statements showing immediate access to enough money to support yourself, covering a recent continuous period, plus an explanation of any large lodgements.",
          ["bank_statement"], IE_ST, money="Commonly cited: €10,000 per year of study for visa-required nationals (lower pro-rata for short courses). Confirm on irishimmigration.ie."),
        health_insurance(IE_ST, "(private medical insurance) for the period of study"),
        R("english", "Evidence of English language ability", "conditional", "English test result or other evidence accepted by the college, where the course is taught in English.", ["english_test_result"], IE_ST),
        R("education-gaps", "Explanation of gaps in your education history", "conditional",
          "Applicants are expected to account for gaps in their education or employment history.", ["employment_letter", "other"], IE_ST,
          when={"fact": "academic.study_gap_months", "op": "gte", "value": 12}),
        translations(IE_ST, "English or Irish"),
    ]),
    ("work", "ie-work", "Employment permit and work visa (Critical Skills / General Employment Permit)",
     "For a job offer in Ireland supported by an employment permit from the Department of Enterprise.", IE_WORK, [
        passport(IE_WORK),
        R("employment-permit", "Employment permit (Critical Skills or General Employment Permit)", "mandatory",
          "An employment permit issued for the specific job and employer before (or alongside) the visa application.", ["employment_contract"], IE_WORK),
        R("job-offer", "Job offer / contract of employment", "mandatory", "Signed offer or contract showing role, salary and duration.", ["employment_contract"], IE_WORK,
          money="Salary thresholds depend on the permit type and occupation lists; confirm on enterprise.gov.ie."),
        R("qualifications", "Qualifications and experience for the role", "mandatory", "Degree certificates and employer references showing you meet the job's requirements.",
          ["academic_certificate", "employment_letter", "experience_certificate"], IE_WORK),
        translations(IE_WORK, "English or Irish"),
    ]),
    ("family", "ie-family", "Join family visa (spouse, partner or child of a permit holder)",
     "For family members joining a non-EEA employment permit holder or other eligible sponsor in Ireland.", IE_FAM, [
        passport(IE_FAM), sponsor_status(IE_FAM, " Waiting periods before family can join differ by permit type."),
        partner_rel(IE_FAM), child_rel(IE_FAM),
        R("sponsor-finances", "Sponsor's income and finances", "mandatory", "Evidence the sponsor can support the family (payslips, employment letter, bank statements).",
          ["salary_slip", "employment_letter", "bank_statement"], IE_FAM, money="Income thresholds depend on the sponsor's permit type; confirm with the Irish Immigration Service."),
        translations(IE_FAM, "English or Irish"),
    ]),
])

# ---- Germany -----------------------------------------------------------------------------------
DE_ST = "https://www.study-in-germany.de/en/plan-your-studies/requirements/proof-of-financing"
DE_WORK, DE_FAM = EU + "highly-qualified-worker-germany_en", EU + "family-member-germany_en"
DE_MIIG = "https://www.make-it-in-germany.com"
add("DE", [("Study in Germany (DAAD) – proof of financing", DE_ST, "DAAD / Federal Foreign Office"),
           ("Highly qualified worker – Germany", DE_WORK, EU_PUB), ("Family member – Germany", DE_FAM, EU_PUB)], [
    ("student", "de-student", "National visa for study (D visa)", "For admission to a degree programme at a German university.", DE_ST, [
        passport(DE_ST),
        R("admission", "Admission letter from a German university", "mandatory", "Letter of admission (Zulassungsbescheid), or conditional admission / preparatory course where accepted.", ["offer_letter"], DE_ST),
        R("proof-of-financing", "Proof of financing (usually a blocked account)", "mandatory",
          "Proof that living costs for the first year are covered — most applicants use a blocked account (Sperrkonto); scholarships or a formal obligation letter may also be accepted in some cases.",
          ["bank_statement", "sponsorship_letter"], DE_ST, money="Commonly cited: about €11,900 per year (12 × €992) for 2025/26. Confirm with the German mission."),
        R("health-insurance", "Health insurance", "mandatory", "Travel health insurance for entry, then statutory or recognised private student health insurance after enrolment.", ["other"], DE_ST),
        R("academic-records", "Academic certificates and transcripts", "mandatory", "School-leaving and university certificates/transcripts (and APS certificate where your country requires it).",
          ["academic_certificate", "academic_transcript"], DE_ST),
        R("language", "Language proof for the course", "conditional", "German (e.g. TestDaF/DSH) or English (e.g. IELTS/TOEFL) proof as required by the programme.", ["english_test_result"], DE_ST),
        translations(DE_ST, "German or English"),
    ]),
    ("work", "de-work", "EU Blue Card / skilled worker visa", "For qualified professionals with a job offer in Germany.", DE_WORK, [
        passport(DE_WORK),
        R("job-offer", "Concrete job offer / employment contract", "mandatory", "Signed contract or binding job offer with salary and role.", ["employment_contract"], DE_WORK,
          money="EU Blue Card salary thresholds are set annually (lower threshold for shortage occupations and new graduates). Confirm on make-it-in-germany.com."),
        R("recognition", "Recognition of your qualification", "mandatory", "Evidence your degree or vocational qualification is recognised in Germany (e.g. anabin entry or recognition notice).",
          ["academic_certificate", "skills_assessment"], DE_MIIG),
        R("occupational-licence", "Licence to practise (regulated professions)", "conditional", "Approval to practise for regulated professions such as medicine or nursing.",
          ["professional_registration"], DE_MIIG, when={"fact": "employment.regulated_occupation", "op": "truthy"}),
        R("cv-experience", "CV and evidence of work experience", "mandatory", "Up-to-date CV and employer references.", ["cv", "employment_letter", "experience_certificate"], DE_WORK),
        R("health-insurance", "Health insurance", "mandatory", "Health insurance cover from the start of employment.", ["other"], DE_WORK),
        translations(DE_WORK, "German or English"),
    ]),
    ("family", "de-family", "Family reunification visa", "For spouses and children joining a family member who lives in Germany.", DE_FAM, [
        passport(DE_FAM), sponsor_status(DE_FAM), partner_rel(DE_FAM), child_rel(DE_FAM),
        R("basic-german", "Basic German (A1) for spouses — unless exempt", "conditional",
          "Spouses usually need simple German (A1) before arrival; family of EU Blue Card holders and some others are exempt. Confirm whether an exemption applies.",
          ["english_test_result", "other"], DE_FAM, when=PARTNER),
        R("living-space-income", "Sufficient living space and means of support", "mandatory", "Rental contract and sponsor's income evidence.",
          ["salary_slip", "employment_letter", "other"], DE_FAM),
        translations(DE_FAM, "German"),
    ]),
])

# ---- France ------------------------------------------------------------------------------------
FR_ST = "https://france-visas.gouv.fr/en/student"
FR_SP = "https://www.service-public.fr/particuliers/vosdroits/F2231?lang=en"
FR_WORK, FR_FAM = EU + "highly-qualified-worker-france_en", EU + "family-member-france_en"
add("FR", [("France-Visas – Student", FR_ST, "Government of France (France-Visas)"), ("Service-Public – student long-stay visa", FR_SP, "Government of France"),
           ("Highly qualified worker – France", FR_WORK, EU_PUB), ("Family member – France", FR_FAM, EU_PUB)], [
    ("student", "fr-student", "Long-stay student visa (VLS-TS étudiant)", "For studies in France longer than 90 days; validated online after arrival.", FR_ST, [
        passport(FR_ST),
        R("admission", "Admission to a French higher-education institution", "mandatory",
          "Admission letter; in countries covered by the Campus France 'Études en France' procedure, the application must go through Campus France first.", ["offer_letter"], FR_ST),
        R("resources", "Proof of financial resources", "mandatory", "Evidence of enough money per month for the stay (own funds, sponsor or scholarship).",
          ["bank_statement", "sponsorship_letter"], FR_ST, money="France-Visas states about €877.50 per month for applications from 1 August 2026 — confirm on france-visas.gouv.fr."),
        R("accommodation", "Proof of accommodation (where required)", "conditional", "Accommodation in France for at least the first months, depending on your situation.", ["other"], FR_ST),
        R("academic-records", "Academic certificates and transcripts", "mandatory", "Previous diplomas and transcripts.", ["academic_certificate", "academic_transcript"], FR_ST),
        R("validation", "Validate the VLS-TS online after arrival", "supplementary", "The visa must be validated online (OFII) within 3 months of arrival, with a fee.", [], FR_SP),
        translations(FR_ST, "French"),
    ]),
    ("work", "fr-work", "Talent passport / salaried worker visa", "For skilled employment in France.", FR_WORK, [
        passport(FR_WORK),
        R("contract", "Employment contract", "mandatory", "Signed contract; for ordinary salaried posts the employer obtains a work authorisation first.", ["employment_contract"], FR_WORK,
          money="Talent-passport categories have salary thresholds linked to the minimum wage; confirm on france-visas.gouv.fr."),
        R("qualifications", "Diplomas and experience", "mandatory", "Degree certificates and evidence of professional experience.", ["academic_certificate", "employment_letter", "cv"], FR_WORK),
        translations(FR_WORK, "French"),
    ]),
    ("family", "fr-family", "Family reunification / family of a talent-passport holder", "For family members of a foreign resident in France.", FR_FAM, [
        passport(FR_FAM), sponsor_status(FR_FAM), partner_rel(FR_FAM), child_rel(FR_FAM),
        R("resources-housing", "Sponsor's stable resources and suitable housing", "mandatory",
          "For ordinary family reunification, the resident must show stable resources and housing (assessed by OFII and the town hall).", ["salary_slip", "bank_statement", "other"], FR_FAM),
        translations(FR_FAM, "French"),
    ]),
])

# ---- Italy -------------------------------------------------------------------------------------
IT_ST = "https://www.universitaly.it"
IT_VISA = "https://vistoperitalia.esteri.it"
IT_WORK, IT_FAM = EU + "highly-qualified-worker-italy_en", EU + "family-member-italy_en"
add("IT", [("Universitaly – pre-enrolment portal", IT_ST, "Ministry of University and Research (Italy)"),
           ("Visto per l'Italia", IT_VISA, "Ministry of Foreign Affairs (Italy)"),
           ("Highly qualified worker – Italy", IT_WORK, EU_PUB), ("Family member – Italy", IT_FAM, EU_PUB)], [
    ("student", "it-student", "Study visa (Type D – university enrolment)", "For enrolment in an Italian university.", IT_VISA, [
        passport(IT_VISA),
        R("universitaly", "Validated Universitaly pre-enrolment", "mandatory", "Pre-enrolment completed on Universitaly and validated by the university; consulates will not issue a study visa without it.", ["offer_letter"], IT_ST),
        R("financial-means", "Proof of financial means (and funds for return)", "mandatory", "Bank statements, sponsorship or scholarship covering the academic year, plus return-journey funds or ticket.",
          ["bank_statement", "sponsorship_letter"], IT_VISA, money="2026/27 embassy checklists cite about €10,180 per year (older documents give lower figures). Confirm with your consulate."),
        R("accommodation", "Proof of accommodation", "mandatory", "Registered lease, hospitality declaration, university housing or initial booking.", ["other"], IT_VISA),
        health_insurance(IT_VISA, "valid in Italy for the whole stay (or enrolment with the national health service after arrival)"),
        R("academic-records", "Academic certificates (with Declaration of Value or CIMEA statement)", "mandatory",
          "Previous qualification and transcripts, usually with a Declaration of Value or CIMEA statement of comparability.", ["academic_certificate", "academic_transcript"], IT_VISA),
        translations(IT_VISA, "Italian (or English where accepted)"),
    ]),
    ("work", "it-work", "Work visa (with nulla osta)", "For subordinate employment, usually under the annual 'Decreto Flussi' quotas or as an EU Blue Card.", IT_WORK, [
        passport(IT_WORK),
        R("nulla-osta", "Work authorisation (nulla osta) obtained by the employer", "mandatory", "The employer applies to the Immigration Desk (Sportello Unico) for a nulla osta before the visa application.",
          ["employment_contract"], IT_WORK),
        R("contract", "Employment contract / job offer", "mandatory", "Signed contract matching the nulla osta.", ["employment_contract"], IT_WORK),
        R("qualifications", "Qualifications and experience", "conditional", "Evidence of qualifications (required for EU Blue Card and regulated jobs).", ["academic_certificate", "experience_certificate"], IT_WORK),
        translations(IT_WORK, "Italian"),
    ]),
    ("family", "it-family", "Family reunification visa", "For family members joining a legally resident person in Italy.", IT_FAM, [
        passport(IT_FAM),
        R("nulla-osta-family", "Family reunification clearance (nulla osta) obtained by the resident", "mandatory", "The family member in Italy applies for the nulla osta first.", ["other"], IT_FAM),
        sponsor_status(IT_FAM), partner_rel(IT_FAM), child_rel(IT_FAM),
        R("income-housing", "Sponsor's income and suitable housing", "mandatory", "Income evidence and housing suitability certificate.", ["salary_slip", "tax_record", "other"], IT_FAM),
        translations(IT_FAM, "Italian"),
    ]),
])

# ---- Malta -------------------------------------------------------------------------------------
MT_ID = "https://identita.gov.mt/working-residing-in-malta/"
MT_FAM = "https://identita.gov.mt/expatriates-unit-non-employment-permits-family-members-policy/"
MT_ST = EU + "student-malta_en"
add("MT", [("Identità – Working & Residing in Malta", MT_ID, "Identità (Government of Malta)"),
           ("Identità – Family Members Policy", MT_FAM, "Identità (Government of Malta)"), ("Student – Malta", MT_ST, EU_PUB)], [
    ("student", "mt-student", "Student visa and residence permit", "For full-time study at an accredited Maltese institution.", MT_ST, [
        passport(MT_ST),
        R("acceptance", "Acceptance letter from an accredited institution", "mandatory", "Acceptance letter, including confirmation that you have sufficient knowledge of the language of the course.", ["offer_letter"], MT_ST),
        R("funds", "Proof of sufficient funds", "mandatory", "Evidence you can support yourself during your studies.", ["bank_statement", "sponsorship_letter"], MT_ST,
          money="No official figure confirmed in research; check the current Identità student form."),
        health_insurance(MT_ST, "covering at least the entire first year of the residence permit"),
        R("accommodation", "Proof of accommodation", "mandatory", "Rental agreement or university residence confirmation.", ["other"], MT_ST),
        R("health-screening", "Health screening (if requested)", "conditional", "Identità may request public-health screening.", ["medical_report"], MT_ID),
        translations(MT_ST, "English or Maltese"),
    ]),
    ("work", "mt-work", "Single Permit (work and residence)", "Combined work and residence permit for third-country nationals employed in Malta.", MT_ID, [
        passport(MT_ID),
        R("job-offer", "Employment contract with a Maltese employer", "mandatory", "Signed contract; the employer submits the Single Permit application.", ["employment_contract"], MT_ID),
        R("qualifications", "Qualifications and CV", "mandatory", "Certificates and CV supporting the role.", ["academic_certificate", "cv", "experience_certificate"], MT_ID),
        health_insurance(MT_ID),
        R("accommodation", "Proof of accommodation", "mandatory", "Registered lease or accommodation confirmation.", ["other"], MT_ID),
        translations(MT_ID, "English or Maltese"),
    ]),
    ("family", "mt-family", "Family reunification", "For family members of a third-country national legally residing in Malta.", MT_FAM, [
        passport(MT_FAM),
        sponsor_status(MT_FAM, " The sponsor needs a permit valid for at least one year with prospects of long-term residence; a minimum period of residence applies before applying (sources differ — confirm with Identità)."),
        partner_rel(MT_FAM), child_rel(MT_FAM),
        R("income-accommodation-insurance", "Sponsor's income, accommodation and health insurance", "mandatory",
          "Stable and regular income, suitable accommodation and health insurance for the family.", ["salary_slip", "bank_statement", "other"], MT_FAM),
        translations(MT_FAM, "English or Maltese"),
    ]),
])

# ---- Netherlands -------------------------------------------------------------------------------
NL_ST = "https://ind.nl/en/residence-permits/study"
NL_HSM = "https://ind.nl/en/work/pages/highly-skilled-migrant.aspx"
NL_FAM = EU + "family-member-netherlands_en"
NL_INCOME = "https://ind.nl/en/required-amounts-income-requirements"
add("NL", [("IND – Study", NL_ST, "IND – Immigration and Naturalisation Service"), ("IND – Highly skilled migrant", NL_HSM, "IND"),
           ("IND – Required amounts / income requirements", NL_INCOME, "IND"), ("Family member – Netherlands", NL_FAM, EU_PUB)], [
    ("student", "nl-student", "Residence permit for study (via recognised sponsor)", "Your Dutch institution (a recognised sponsor) starts the application for you.", NL_ST, [
        passport(NL_ST),
        R("recognised-sponsor", "Admission by a recognised-sponsor institution", "mandatory", "Admission to a full-time programme at an institution that is a recognised sponsor; the institution submits the application.", ["offer_letter"], NL_ST),
        R("sufficient-means", "Sufficient means (checked by the institution)", "mandatory", "Evidence of enough money for the study period, usually provided to the institution.",
          ["bank_statement", "sponsorship_letter"], NL_INCOME, money="The IND publishes the monthly student norm amount, updated each January/July. Confirm on ind.nl."),
        R("tb-test", "Tuberculosis test after arrival (certain nationalities)", "conditional", "Nationals of some countries must take a TB test after arrival.", ["medical_report"], NL_ST,
          when={"fact": "applicant.nationality", "op": "in", "value": ["LK", "IN", "BD", "NP"]}),
        translations(NL_ST, "Dutch, English, French or German"),
    ]),
    ("work", "nl-work", "Highly skilled migrant (kennismigrant)", "For employment with a Dutch employer that is an IND recognised sponsor.", NL_HSM, [
        passport(NL_HSM),
        R("recognised-employer", "Job with a recognised-sponsor employer", "mandatory", "The employer must be on the IND public register of recognised sponsors; it submits the application.", ["employment_contract"], NL_HSM),
        R("salary", "Salary meeting the highly-skilled-migrant threshold", "mandatory", "Gross monthly salary at or above the IND threshold for your age group.", ["employment_contract"], NL_INCOME,
          money="Thresholds are age-dependent and updated every January; confirm on ind.nl."),
        R("tb-test", "Tuberculosis test after arrival (certain nationalities)", "conditional", "Nationals of some countries must take a TB test after arrival.", ["medical_report"], NL_HSM,
          when={"fact": "applicant.nationality", "op": "in", "value": ["LK", "IN", "BD", "NP"]}),
        translations(NL_HSM, "Dutch, English, French or German"),
    ]),
    ("family", "nl-family", "Residence permit to stay with a partner or parent", "For partners and children of residents in the Netherlands.", NL_FAM, [
        passport(NL_FAM), sponsor_status(NL_FAM), partner_rel(NL_FAM), child_rel(NL_FAM),
        R("sponsor-income", "Sponsor's sufficient, independent and sustainable income", "mandatory", "Usually at least the statutory-minimum-wage based norm (lower norms for some sponsors).",
          ["salary_slip", "employment_contract", "tax_record"], NL_INCOME, money="Amounts published by the IND; confirm on ind.nl."),
        R("civic-integration", "Civic integration exam abroad (unless exempt)", "conditional",
          "Partners of some sponsors must pass the basic civic integration exam abroad; family of highly skilled migrants, EU Blue Card holders and researchers are generally exempt. Confirm your situation.",
          ["other"], NL_FAM, when=PARTNER),
        translations(NL_FAM, "Dutch, English, French or German"),
    ]),
])

# ---- Sweden ------------------------------------------------------------------------------------
SE_ST = "https://www.migrationsverket.se/en/you-want-to-apply/study/higher-education.html"
SE_WORK, SE_FAM = EU + "highly-qualified-worker-sweden_en", EU + "family-member-sweden_en"
add("SE", [("Migrationsverket – Higher education", SE_ST, "Swedish Migration Agency (Migrationsverket)"),
           ("Highly qualified worker – Sweden", SE_WORK, EU_PUB), ("Family member – Sweden", SE_FAM, EU_PUB)], [
    ("student", "se-student", "Residence permit for higher education", "For full-time university studies in Sweden.", SE_ST, [
        passport(SE_ST),
        R("final-admission", "Final admission to full-time studies", "mandatory", "Notification of final admission to full-time studies (distance learning does not qualify).", ["offer_letter"], SE_ST),
        R("tuition-paid", "Tuition fee paid (if the programme charges fees)", "conditional", "Evidence the first instalment / tuition fee has been paid.", ["other"], SE_ST),
        R("maintenance", "Enough money for the whole permit period", "mandatory",
          "Funds for every month of the permit; bank statements must be issued no more than four months before the requested permit start date.", ["bank_statement"], SE_ST,
          money="Migrationsverket publishes a monthly maintenance amount; confirm on migrationsverket.se.", currency="SEK"),
        R("comprehensive-insurance", "Comprehensive health insurance", "conditional", "Required if your institution does not provide it (particularly for permits under one year).", ["other"], SE_ST),
        translations(SE_ST, "Swedish or English"),
    ]),
    ("work", "se-work", "Work permit", "For employment with a Swedish employer.", SE_WORK, [
        passport(SE_WORK),
        R("job-offer", "Offer of employment initiated by the employer", "mandatory", "The employer advertises the job and starts the application with an offer of employment.", ["employment_contract"], SE_WORK),
        R("salary-insurance", "Salary and insurance on Swedish collective-agreement level", "mandatory",
          "Salary at least the minimum threshold and terms on par with collective agreements, with health, life, occupational-injury and pension insurance.",
          ["employment_contract"], SE_WORK, money="A minimum salary threshold applies (linked to the median wage); confirm on migrationsverket.se.", currency="SEK"),
        translations(SE_WORK, "Swedish or English"),
    ]),
    ("family", "se-family", "Residence permit to move to a family member", "For partners and children of residents of Sweden.", SE_FAM, [
        passport(SE_FAM), sponsor_status(SE_FAM), partner_rel(SE_FAM), child_rel(SE_FAM),
        R("maintenance-housing", "Maintenance and housing requirement", "conditional", "The person in Sweden may need to support the family and have adequate housing.", ["salary_slip", "other"], SE_FAM),
        translations(SE_FAM, "Swedish or English"),
    ]),
])

# ---- Finland -----------------------------------------------------------------------------------
FI_ST = "https://migri.fi/en/studying-in-finland"
FI_FAM_INC = "https://migri.fi/income-requirement-for-family-members-of-a-person-who-has-been-granted-a-residence-permit-in-finland"
FI_WORK, FI_FAM = EU + "highly-qualified-worker-finland_en", EU + "family-member-finland_en"
add("FI", [("Migri – Studying in Finland", FI_ST, "Finnish Immigration Service (Migri)"), ("Migri – income requirement for family members", FI_FAM_INC, "Migri"),
           ("Highly qualified worker – Finland", FI_WORK, EU_PUB), ("Family member – Finland", FI_FAM, EU_PUB)], [
    ("student", "fi-student", "First residence permit for studies", "For a degree or other qualifying studies in Finland.", FI_ST, [
        passport(FI_ST),
        R("study-place", "Study place (acceptance letter)", "mandatory", "Acceptance to a degree programme or other qualifying studies.", ["offer_letter"], FI_ST),
        R("sufficient-funds", "Sufficient funds for the whole permit period", "mandatory", "Funds in your own account (or scholarship) for living costs, plus unpaid tuition fees.",
          ["bank_statement", "sponsorship_letter"], FI_ST, money="Universities cite €800 per month (€9,600 per year); Migri raised thresholds from 1 Nov 2024. Confirm on migri.fi."),
        R("health-insurance", "Health insurance for the whole study period", "mandatory", "Insurance valid for the whole permit (not needed with a Kela card or EHIC).", ["other"], FI_ST),
        R("tuition", "Tuition fee paid or scholarship", "conditional", "Evidence of tuition payment or tuition-waiver scholarship where fees apply.", ["other"], FI_ST),
        translations(FI_ST, "Finnish, Swedish or English"),
    ]),
    ("work", "fi-work", "Residence permit for an employed person / specialist", "For employment in Finland.", FI_WORK, [
        passport(FI_WORK),
        R("employment-contract", "Employment contract and terms of employment", "mandatory", "Signed contract or terms-of-employment form from the employer.", ["employment_contract"], FI_WORK,
          money="Income must be sufficient (specialist/Blue Card salary thresholds apply); confirm on migri.fi."),
        R("qualifications", "Qualifications for the job", "mandatory", "Degree certificates and references.", ["academic_certificate", "employment_letter"], FI_WORK),
        translations(FI_WORK, "Finnish, Swedish or English"),
    ]),
    ("family", "fi-family", "Residence permit on the basis of family ties", "For family members of a person living in Finland.", FI_FAM, [
        passport(FI_FAM), sponsor_status(FI_FAM), partner_rel(FI_FAM), child_rel(FI_FAM),
        R("income-requirement", "Secure means of support (income requirement)", "mandatory",
          "Usually sufficient net income for the family; income of the family member working in Finland counts.", ["salary_slip", "bank_statement", "tax_record"], FI_FAM_INC,
          money="Required sums depend on family size; confirm on migri.fi."),
        translations(FI_FAM, "Finnish, Swedish or English"),
    ]),
])

# ---- Lithuania ---------------------------------------------------------------------------------
LT_ST, LT_WORK, LT_FAM = EU + "student-lithuania_en", EU + "highly-qualified-worker-lithuania_en", EU + "family-member-lithuania_en"
add("LT", [("Student – Lithuania", LT_ST, EU_PUB), ("Highly qualified worker – Lithuania", LT_WORK, EU_PUB), ("Family member – Lithuania", LT_FAM, EU_PUB)], [
    ("student", "lt-student", "Temporary residence permit for studies", "Full-time students apply for a temporary residence permit (TRP) via the Migration Department's MIGRIS portal.", LT_ST, [
        passport(LT_ST),
        R("admission", "Admission to full-time studies", "mandatory", "Confirmation of admission from a Lithuanian institution.", ["offer_letter"], LT_ST),
        R("funds", "Sufficient means of subsistence", "mandatory", "Evidence of funds for living costs during the permit.", ["bank_statement", "sponsorship_letter"], LT_ST,
          money="Amount set by Lithuanian regulations; confirm on migracija.lrv.lt."),
        health_insurance(LT_ST),
        R("accommodation", "Accommodation in Lithuania", "conditional", "Declared place of residence / accommodation evidence.", ["other"], LT_ST),
        translations(LT_ST, "Lithuanian or English"),
    ]),
    ("work", "lt-work", "Temporary residence permit for work / EU Blue Card", "For employment in Lithuania.", LT_WORK, [
        passport(LT_WORK),
        R("job-offer", "Employment contract or binding job offer", "mandatory", "Contract with a Lithuanian employer.", ["employment_contract"], LT_WORK,
          money="Salary thresholds (e.g. for EU Blue Card) are linked to the national average wage; confirm on migracija.lrv.lt."),
        R("qualifications", "Qualifications / work authorisation", "mandatory", "Evidence of qualifications and, where required, a work permit or decision on labour-market needs.",
          ["academic_certificate", "experience_certificate"], LT_WORK),
        health_insurance(LT_WORK),
        translations(LT_WORK, "Lithuanian or English"),
    ]),
    ("family", "lt-family", "Temporary residence permit for family reunification", "For family members of foreigners residing in Lithuania.", LT_FAM, [
        passport(LT_FAM), sponsor_status(LT_FAM), partner_rel(LT_FAM), child_rel(LT_FAM),
        R("means-insurance", "Means of subsistence, accommodation and health insurance", "mandatory", "Sponsor's income, accommodation and insurance for the family member.",
          ["salary_slip", "bank_statement", "other"], LT_FAM),
        translations(LT_FAM, "Lithuanian or English"),
    ]),
])

# ---- Hungary -----------------------------------------------------------------------------------
HU_ST = "https://oif.gov.hu/students"
HU_WORK = "https://oif.gov.hu/factsheets/information-for-employers-and-host-organizations"
HU_FAM = "https://washington.mfa.gov.hu/en/residence-permits"
add("HU", [("Immigration Office – Students", HU_ST, "National Directorate-General for Aliens Policing (Hungary)"),
           ("Immigration Office – Employers and host organisations", HU_WORK, "National Directorate-General for Aliens Policing (Hungary)"),
           ("Embassy of Hungary – Residence permits", HU_FAM, "Ministry of Foreign Affairs and Trade (Hungary)")], [
    ("student", "hu-student", "Residence permit for study purposes", "For full-time study at a Hungarian institution.", HU_ST, [
        passport(HU_ST),
        R("student-status", "Certificate of school attendance / admission", "mandatory", "Letter of admission or certificate of student status from the institution.", ["offer_letter"], HU_ST),
        R("subsistence", "Proof of subsistence", "mandatory", "Evidence you can support yourself during the permit.", ["bank_statement", "sponsorship_letter"], HU_ST,
          money="No official figure confirmed in research; confirm on enterhungary.gov.hu."),
        R("accommodation", "Proof of accommodation in Hungary", "mandatory", "Lease, dormitory confirmation or accommodation declaration.", ["other"], HU_ST),
        health_insurance(HU_ST),
        translations(HU_ST, "Hungarian or English"),
    ]),
    ("work", "hu-work", "Work-related residence permit (e.g. Hungarian Card, EU Blue Card)", "Hungary's 2024 immigration law replaced the single employment permit with several permit types.", HU_WORK, [
        passport(HU_WORK),
        R("contract", "Employment contract / pre-contract", "mandatory", "Contract with a Hungarian employer for the permit category that applies.", ["employment_contract"], HU_WORK),
        R("accommodation", "Proof of accommodation", "mandatory", "Accommodation in Hungary.", ["other"], HU_WORK),
        R("qualifications", "Qualifications for the role", "conditional", "Required for skilled categories such as the EU Blue Card.", ["academic_certificate", "experience_certificate"], HU_WORK),
        health_insurance(HU_WORK),
        translations(HU_WORK, "Hungarian or English"),
    ]),
    ("family", "hu-family", "Residence permit for family reunification", "For spouses and children of residents. Note: family reunification is not available to family of study-permit holders, and cohabiting partners cannot apply.", HU_FAM, [
        passport(HU_FAM), sponsor_status(HU_FAM),
        R("relationship-partner", "Marriage certificate", "conditional", "Marriage certificate (cohabiting partners are not eligible under the 2024 law).",
          ["marriage_certificate"], HU_FAM, when=PARTNER),
        child_rel(HU_FAM),
        R("accommodation-subsistence", "Accommodation and subsistence", "mandatory", "Proof of accommodation and means of subsistence.", ["bank_statement", "salary_slip", "other"], HU_FAM),
        translations(HU_FAM, "Hungarian"),
    ]),
])

# ---- Georgia -----------------------------------------------------------------------------------
GE_VISA = "https://www.geoconsul.gov.ge"
GE_PSH = "https://psh.gov.ge"
add("GE", [("Consular Department – visas (Georgia)", GE_VISA, "Ministry of Foreign Affairs of Georgia"),
           ("Public Service Hall – residence permits", GE_PSH, "Public Service Development Agency (Georgia)")], [
    ("student", "ge-student", "D3 study visa and study residence permit",
     "Visa-required nationals apply for a D3 visa (e-application, often via VFS) before travel, then a study residence permit at the Public Service Hall.", GE_VISA, [
        passport(GE_VISA),
        R("enrolment", "Enrolment letter from an authorised Georgian institution", "mandatory", "Confirmation of admission/enrolment for full-time study.", ["offer_letter"], GE_VISA),
        R("funds", "Proof of financial means", "mandatory", "Bank statements or sponsorship covering the stay.", ["bank_statement", "sponsorship_letter"], GE_VISA,
          money="No official figure confirmed in research; confirm on geoconsul.gov.ge."),
        health_insurance(GE_VISA),
        R("residence-permit-deadline", "Apply for the study residence permit after arrival", "supplementary",
          "Apply at the Public Service Hall soon after arrival (commonly cited: within 45 days); late applications can cause penalties.", [], GE_PSH),
        translations(GE_VISA, "Georgian or English"),
    ]),
    ("work", "ge-work", "D1 work visa and work residence permit", "For employment in Georgia.", GE_VISA, [
        passport(GE_VISA),
        R("employment-contract", "Employment contract / employer documents", "mandatory", "Contract with a Georgian employer and the employer's registration documents.", ["employment_contract", "business_registration"], GE_VISA),
        R("qualifications", "Qualifications and CV", "conditional", "Evidence of qualifications for the role.", ["academic_certificate", "cv"], GE_VISA),
        health_insurance(GE_VISA),
        translations(GE_VISA, "Georgian or English"),
    ]),
    ("family", "ge-family", "Family visa and family reunification residence permit", "For family members of foreigners residing in Georgia.", GE_PSH, [
        passport(GE_PSH), sponsor_status(GE_PSH), partner_rel(GE_PSH), child_rel(GE_PSH),
        health_insurance(GE_PSH),
        translations(GE_PSH, "Georgian or English"),
    ]),
])
