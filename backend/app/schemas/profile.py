"""Validated shapes for the JSONB profile sections and category-specific application details."""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

YM = r"^\d{4}-(0[1-9]|1[0-2])(-\d{2})?$"


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Qualification(_M):
    level: Literal["secondary", "diploma", "bachelor", "master", "doctorate", "professional", "other"]
    title: str = Field(max_length=200)
    institution: str | None = Field(default=None, max_length=200)
    country: str | None = Field(default=None, max_length=2)
    completion_date: str | None = Field(default=None, pattern=YM)
    result: str | None = Field(default=None, max_length=100)


class EnglishTest(_M):
    type: Literal["IELTS Academic", "IELTS General", "IELTS UKVI", "TOEFL iBT", "PTE Academic", "Duolingo", "Cambridge", "Other"] | None = None
    overall_score: float | None = Field(default=None, ge=0, le=200)
    test_date: str | None = Field(default=None, pattern=YM)


class Academic(_M):
    qualifications: list[Qualification] = Field(default_factory=list, max_length=15)
    english_test: EnglishTest | None = None


class Job(_M):
    employer: str = Field(max_length=200)
    job_title: str | None = Field(default=None, max_length=200)
    start_date: str | None = Field(default=None, pattern=YM)
    end_date: str | None = Field(default=None, pattern=YM)
    country: str | None = Field(default=None, max_length=2)
    monthly_salary: float | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, max_length=3)


class Employment(_M):
    status: Literal["employed", "self_employed", "unemployed", "student", "retired", "other"] | None = None
    history: list[Job] = Field(default_factory=list, max_length=25)
    career_change: bool | None = None
    regulated_occupation: bool | None = None


class Sponsor(_M):
    name: str | None = Field(default=None, max_length=200)
    relationship: Literal["father", "mother", "parent", "spouse", "sibling", "uncle", "aunt", "grandparent", "relative", "employer", "other"] | None = None
    employment_type: Literal["salaried", "self_employed", "business_owner", "retired", "other"] | None = None
    annual_income: float | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, max_length=3)


class Financial(_M):
    funding_source: Literal["self", "sponsor", "mixed", "scholarship", "employer"] | None = None
    savings_amount: float | None = Field(default=None, ge=0)
    savings_currency: str | None = Field(default=None, max_length=3)
    sponsor: Sponsor | None = None
    declared_large_deposits: bool | None = None
    large_deposit_explanation: str | None = Field(default=None, max_length=2000)
    has_education_loan: bool | None = None
    loan_amount: float | None = Field(default=None, ge=0)
    liabilities: str | None = Field(default=None, max_length=1000)


class Refusal(_M):
    country: str | None = Field(default=None, max_length=2)
    year: int | None = Field(default=None, ge=1950, le=2100)
    visa_type: str | None = Field(default=None, max_length=100)


class PrevVisa(_M):
    country: str | None = Field(default=None, max_length=2)
    year: int | None = Field(default=None, ge=1950, le=2100)
    visa_type: str | None = Field(default=None, max_length=100)


class Immigration(_M):
    has_previous_refusals: bool | None = None
    previous_refusals: list[Refusal] = Field(default_factory=list, max_length=20)
    previous_visas: list[PrevVisa] = Field(default_factory=list, max_length=50)
    overstays: bool | None = None
    overstay_details: str | None = Field(default=None, max_length=2000)
    travel_countries: list[str] = Field(default_factory=list, max_length=100)


class ProfileIn(_M):
    given_names: str | None = Field(default=None, max_length=200)
    family_name: str | None = Field(default=None, max_length=200)
    date_of_birth: date | None = None
    nationality: str | None = Field(default=None, min_length=2, max_length=2)
    residence_country: str | None = Field(default=None, min_length=2, max_length=2)
    marital_status: Literal["single", "married", "partnered", "divorced", "widowed", "separated"] | None = None
    passport_number: str | None = Field(default=None, max_length=40, pattern=r"^[A-Za-z0-9 ]*$")
    passport_expiry: date | None = None
    phone: str | None = Field(default=None, max_length=40)
    academic: Academic | None = None
    employment: Employment | None = None
    financial: Financial | None = None
    immigration_history: Immigration | None = None

    @field_validator("nationality", "residence_country")
    @classmethod
    def upper(cls, v):
        return v.upper() if v else v


class StudentDetails(_M):
    course_name: str | None = Field(default=None, max_length=200)
    course_level: Literal["foundation", "diploma", "bachelor", "master", "doctorate", "language", "other"] | None = None
    institution: str | None = Field(default=None, max_length=200)
    course_start: str | None = Field(default=None, pattern=YM)
    course_related_to_previous: Literal["yes", "partly", "no"] | None = None
    tuition_fee: float | None = Field(default=None, ge=0)
    tuition_currency: str | None = Field(default=None, max_length=3)
    career_goal: str | None = Field(default=None, max_length=1000)


class WorkDetails(_M):
    employer: str | None = Field(default=None, max_length=200)
    job_title: str | None = Field(default=None, max_length=200)
    occupation_code: str | None = Field(default=None, max_length=40)
    salary: float | None = Field(default=None, ge=0)
    salary_currency: str | None = Field(default=None, max_length=3)
    job_offer_sector: Literal["education", "health", "social_care", "it", "engineering", "hospitality", "other"] | None = None
    start_date: str | None = Field(default=None, pattern=YM)


class FamilyDetails(_M):
    relation_to_principal: Literal["spouse", "partner", "child", "parent", "other"] | None = None
    principal_name: str | None = Field(default=None, max_length=200)
    principal_status: str | None = Field(default=None, max_length=200)


DETAILS_SCHEMA = {"student": StudentDetails, "work": WorkDetails, "family": FamilyDetails}
