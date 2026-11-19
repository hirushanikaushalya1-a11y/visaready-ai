"""Public knowledge endpoints: countries, visa categories, requirements, services, Knowledge Centre."""
from __future__ import annotations

import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.knowledge import Country, ImmigrationRequirement, OfficialSource, PolicyAlert, VisaCategory
from app.models.commerce import ServiceCatalogItem

router = APIRouter(tags=["knowledge"])


def req_out(r: ImmigrationRequirement) -> dict:
    return {
        "id": str(r.id), "key": r.key, "title": r.title, "description": r.description, "level": r.requirement_level,
        "eligibility_conditions": r.eligibility_conditions, "document_types": r.document_types,
        "financial_requirement": r.financial_requirement, "exceptions": r.exceptions, "source_url": r.source_url,
        "source_excerpt": r.source_excerpt, "effective_date": r.effective_date.isoformat() if r.effective_date else None,
        "last_verified_at": r.last_verified_at.isoformat() if r.last_verified_at else None, "review_status": r.review_status,
        "version": r.version, "applies_when": r.applies_when,
    }


@router.get("/countries")
def countries(kind: str = Query("destination", pattern="^(destination|all|future)$"), db: Session = Depends(get_db)):
    q = select(Country)
    if kind == "destination":
        q = q.where(Country.is_destination.is_(True))
    elif kind == "future":
        q = q.where(Country.is_destination.is_(False), Country.sort_order == 200)
    rows = db.scalars(q.order_by(Country.sort_order, Country.name)).all()
    return [{"code": c.code, "name": c.name, "region": c.region, "module_status": c.module_status,
             "is_source_market": c.is_source_market} for c in rows]


@router.get("/countries/{code}/visa-categories")
def categories(code: str, db: Session = Depends(get_db)):
    rows = db.scalars(select(VisaCategory).where(VisaCategory.country_code == code.upper(), VisaCategory.is_active.is_(True))
                      .order_by(VisaCategory.category_type)).all()
    out = []
    for c in rows:
        n = len(db.scalars(select(ImmigrationRequirement.id).where(ImmigrationRequirement.visa_category_id == c.id,
                                                                   ImmigrationRequirement.review_status.in_(("pending_review", "verified")))).all())
        out.append({"id": str(c.id), "code": c.code, "name": c.name, "category_type": c.category_type, "description": c.description,
                    "official_url": c.official_url, "requirement_count": n})
    return out


@router.get("/visa-categories/{category_id}/requirements")
def requirements(category_id: uuid.UUID, db: Session = Depends(get_db)):
    cat = db.get(VisaCategory, category_id)
    if not cat:
        raise HTTPException(404, "Not found")
    rows = db.scalars(select(ImmigrationRequirement).where(ImmigrationRequirement.visa_category_id == cat.id,
                                                           ImmigrationRequirement.review_status.in_(("pending_review", "verified")))
                      .order_by(ImmigrationRequirement.sort_order)).all()
    return {"category": {"id": str(cat.id), "name": cat.name, "country_code": cat.country_code, "official_url": cat.official_url,
                         "category_type": cat.category_type},
            "requirements": [req_out(r) for r in rows],
            "note": None if rows else "Detailed requirements for this visa have not been loaded yet. Please consult the official source."}


@router.get("/services")
def services(db: Session = Depends(get_db)):
    rows = db.scalars(select(ServiceCatalogItem).where(ServiceCatalogItem.is_active.is_(True)).order_by(ServiceCatalogItem.sort_order)).all()
    return [{"code": s.code, "kind": s.kind, "name": s.name, "description": s.description, "price_cents": s.price_cents,
             "currency": s.currency, "sla_hours": s.sla_hours, "required_information": s.required_information,
             "inclusions": s.inclusions, "exclusions": s.exclusions, "disclaimer": s.disclaimer,
             "restricted_countries": s.restricted_countries or []} for s in rows]


@router.get("/knowledge/search")
def knowledge_search(q: str = Query(min_length=2, max_length=200), country: str | None = None, db: Session = Depends(get_db)):
    """Global Visa Knowledge Centre. Answers come ONLY from recorded requirements with official
    sources; if nothing matches we say so rather than inventing an answer."""
    terms = [t for t in re.findall(r"[a-zA-Z]{3,}", q.lower()) if t not in {"what", "the", "for", "how", "need", "does", "visa", "and", "can"}][:6]
    if not terms:
        return {"query": q, "results": [], "answer_available": False,
                "message": "Please ask a more specific question (for example: 'English requirement UK student')."}
    stmt = select(ImmigrationRequirement).join(VisaCategory).where(
        ImmigrationRequirement.review_status.in_(("pending_review", "verified")),
        or_(*[or_(ImmigrationRequirement.title.ilike(f"%{t}%"), ImmigrationRequirement.description.ilike(f"%{t}%"),
                  VisaCategory.name.ilike(f"%{t}%")) for t in terms]))
    if country:
        stmt = stmt.where(VisaCategory.country_code == country.upper())
    rows = db.scalars(stmt.limit(200)).all()

    def score(r):
        text = f"{r.title} {r.description} {r.visa_category.name} {r.visa_category.country.name}".lower()
        return sum(t in text for t in terms)

    # Relevance floor: at least half of the meaningful terms must match, so one stray word never
    # produces a confident-looking but unrelated answer.
    needed = max(1, -(-len(terms) // 2))
    rows = [r for r in sorted(rows, key=score, reverse=True) if score(r) >= needed][:12]
    return {"query": q, "answer_available": bool(rows),
            "message": None if rows else "We don't have verified information that answers this yet. Please check the official government source for your destination.",
            "results": [{**req_out(r), "country_code": r.visa_category.country_code, "country_name": r.visa_category.country.name,
                         "visa_category": r.visa_category.name} for r in rows]}


@router.get("/policy-alerts")
def policy_alerts(db: Session = Depends(get_db)):
    rows = db.scalars(select(PolicyAlert).where(PolicyAlert.status == "published").order_by(PolicyAlert.published_at.desc()).limit(20)).all()
    return [{"id": str(a.id), "country_code": a.country_code, "title": a.title, "summary": a.summary, "source_url": a.source_url,
             "effective_date": a.effective_date.isoformat() if a.effective_date else None,
             "published_at": a.published_at.isoformat() if a.published_at else None} for a in rows]


@router.get("/official-sources")
def official_sources(country: str | None = None, db: Session = Depends(get_db)):
    q = select(OfficialSource)
    if country:
        q = q.where(OfficialSource.country_code == country.upper())
    return [{"id": str(s.id), "country_code": s.country_code, "title": s.title, "url": s.url, "publisher": s.publisher,
             "last_checked_at": s.last_checked_at.isoformat() if s.last_checked_at else None} for s in db.scalars(q).all()]
