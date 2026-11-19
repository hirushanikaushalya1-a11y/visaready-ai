"""Idempotent seed: roles/permissions, countries, knowledge base, evidence rules, service catalogue.

Usage:  python -m app.seed.seed            (safe to re-run; updates catalogue text, never resets verification)
        SEED_ADMIN_EMAIL=... SEED_ADMIN_PASSWORD=... python -m app.seed.seed   (also creates a super admin)
        python -m app.seed.seed --demo-staff  (development only: one account per staff role)
"""
from __future__ import annotations

import os
import sys

import pycountry
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal, utcnow
from app.core.security import hash_password
from app.models import (
    Country,
    EvidenceRule,
    ImmigrationRequirement,
    OfficialSource,
    Permission,
    RequirementVersion,
    Role,
    RolePermission,
    ServiceCatalogItem,
    User,
    VisaCategory,
)
from app.models.enums import DEFAULT_PERMISSIONS, ROLES
from app.seed import knowledge_data as K
from app.services.knowledge.requirements import requirement_snapshot

COUNTRY_NAME_OVERRIDES = {"GB": "United Kingdom", "TR": "Türkiye", "KR": "South Korea", "RU": "Russia", "IR": "Iran",
                          "VN": "Vietnam", "TW": "Taiwan", "LA": "Laos", "SY": "Syria", "BO": "Bolivia",
                          "VE": "Venezuela", "TZ": "Tanzania", "MD": "Moldova", "CZ": "Czech Republic"}


def seed_roles(db: Session) -> None:
    for name, label in ROLES.items():
        r = db.get(Role, name) or Role(name=name)
        r.label, r.is_staff = label, name != "applicant"
        db.merge(r)
    for code, roles in DEFAULT_PERMISSIONS.items():
        db.merge(Permission(code=code))
        db.flush()
        for role in roles:
            db.merge(RolePermission(role_name=role, permission_code=code))


def seed_countries(db: Session) -> None:
    dest = {c: (region, status, order) for c, region, status, order in K.DESTINATIONS}
    for c in pycountry.countries:
        code = c.alpha_2
        name = COUNTRY_NAME_OVERRIDES.get(code, getattr(c, "common_name", None) or c.name)
        row = db.get(Country, code) or Country(code=code, name=name)
        row.name = name
        row.is_source_market = code in K.SOURCE_MARKETS
        if code in dest:
            region, status, order = dest[code]
            row.is_destination, row.region, row.sort_order = True, region, order
            if row.module_status != "live":  # never downgrade a module an admin promoted to live
                row.module_status = status
        elif code in K.FUTURE_DESTINATIONS:
            row.is_destination, row.module_status, row.sort_order = False, "planned", 200
        db.merge(row)
    db.flush()


def seed_knowledge(db: Session) -> None:
    sources: dict[str, OfficialSource] = {}
    def ensure_source(country: str, title: str, url: str, publisher: str) -> OfficialSource:
        if url in sources:  # the same official page can back several requirements / countries' portals
            return sources[url]
        src = db.scalars(select(OfficialSource).where(OfficialSource.url == url)).first()
        if not src:
            src = OfficialSource(country_code=country, title=title, url=url, publisher=publisher)
            db.add(src)
        sources[url] = src
        return src

    for country, title, url, publisher in K.SOURCES:
        ensure_source(country, title, url, publisher)
    for country, (publisher, url) in K.PORTALS.items():
        ensure_source(country, f"{publisher} – official portal", url, publisher)
    db.flush()

    for country, ctype, code, name, desc, url, reqs in K.CATEGORIES:
        cat = db.scalars(select(VisaCategory).where(VisaCategory.country_code == country, VisaCategory.code == code)).first()
        if not cat:
            cat = VisaCategory(country_code=country, category_type=ctype, code=code, name=name, description=desc, official_url=url)
            db.add(cat)
            db.flush()
        elif cat.name in {n for n, _ in K.GENERIC_CATEGORIES.values()}:
            # A placeholder category now has researched content: give it its real name and source.
            cat.name, cat.description, cat.official_url = name, desc, url
        for order, r in enumerate(reqs):
            existing = db.scalars(select(ImmigrationRequirement).where(
                ImmigrationRequirement.visa_category_id == cat.id, ImmigrationRequirement.key == r["key"])).first()
            if existing:
                continue  # never overwrite admin-edited / verified content
            req = ImmigrationRequirement(
                visa_category_id=cat.id, key=r["key"], title=r["title"], description=r["description"],
                requirement_level=r["level"], applies_when=r.get("applies_when"),
                eligibility_conditions=r.get("eligibility_conditions"), document_types=r.get("document_types", []),
                financial_requirement=r.get("financial_requirement"), exceptions=r.get("exceptions"),
                translation_required_if_not_english=r.get("translation", False),
                official_source_id=(sources.get(r["source_url"]).id if sources.get(r["source_url"]) else None),
                source_url=r["source_url"], review_status="pending_review", version=1, sort_order=order,
            )
            db.add(req)
            db.flush()
            db.add(RequirementVersion(requirement_id=req.id, version=1, snapshot=requirement_snapshot(req),
                                      change_note="Initial seed — pending verification against official source", created_at=utcnow()))

    # Planned countries: register generic categories (no requirements) so the platform is navigable,
    # and the engine clearly reports that the country module is not yet populated.
    for country, (publisher, url) in K.PORTALS.items():
        for ctype, (name, desc) in K.GENERIC_CATEGORIES.items():
            code = f"{country.lower()}-{ctype}"
            if not db.scalars(select(VisaCategory).where(VisaCategory.country_code == country, VisaCategory.code == code)).first():
                db.add(VisaCategory(country_code=country, category_type=ctype, code=code, name=name, description=desc, official_url=url))

    for r in K.EVIDENCE_RULES:
        rule = db.scalars(select(EvidenceRule).where(EvidenceRule.key == r["key"])).first() or EvidenceRule(key=r["key"])
        rule.title, rule.applies_when, rule.document_types = r["title"], r["applies_when"], r["document_types"]
        rule.explanation, rule.claim_key = r["explanation"], r.get("claim_key")
        rule.level, rule.category_types = r.get("level", "conditional"), r.get("category_types", [])
        db.add(rule)


def seed_services(db: Session) -> None:
    for s in K.SERVICES:
        existing = db.get(ServiceCatalogItem, s["code"])
        row = existing or ServiceCatalogItem(code=s["code"])
        for k in ("kind", "name", "description", "sort_order"):
            setattr(row, k, s[k])
        if existing is None:  # never overwrite a price an admin has changed
            row.price_cents = s.get("price_cents")
        row.sla_hours = s.get("sla_hours")
        row.required_information = s.get("required_information", [])
        row.inclusions, row.exclusions = s.get("inclusions", []), s.get("exclusions", [])
        row.disclaimer = s.get("disclaimer")
        row.is_active = s.get("is_active", True)
        row.currency = "USD"
        db.merge(row)


def seed_user(db: Session, email: str, password: str, name: str, role: str) -> User:
    u = db.scalars(select(User).where(User.email == email)).first()
    if u:
        return u
    u = User(email=email, password_hash=hash_password(password), full_name=name, role=role, terms_accepted_at=utcnow())
    db.add(u)
    db.flush()
    return u


def run(demo_staff: bool = False) -> None:
    db = SessionLocal()
    try:
        seed_roles(db)
        seed_countries(db)
        seed_knowledge(db)
        seed_services(db)
        if os.environ.get("SEED_ADMIN_EMAIL") and os.environ.get("SEED_ADMIN_PASSWORD"):
            seed_user(db, os.environ["SEED_ADMIN_EMAIL"].lower(), os.environ["SEED_ADMIN_PASSWORD"], "Super Admin", "super_admin")
        if demo_staff:
            if get_settings().environment == "production":
                raise SystemExit("--demo-staff is not allowed in production")
            for role in ("super_admin", "admin", "document_team", "translator", "reviewer", "support"):
                seed_user(db, f"{role.replace('_', '-')}@demo.visaready.local", "DemoPass123!", f"Demo {ROLES[role]}", role)
        db.commit()
        print("Seed complete.")
    finally:
        db.close()


if __name__ == "__main__":
    run(demo_staff="--demo-staff" in sys.argv)
