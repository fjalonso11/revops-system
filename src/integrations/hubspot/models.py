from datetime import datetime
from pydantic import BaseModel


class HubSpotCompany(BaseModel):
    hubspot_id: str
    name: str
    domain: str | None = None
    industry: str | None = None
    country: str | None = None
    city: str | None = None
    mrr: float | None = None
    arr: float | None = None
    raw_data: dict = {}


class HubSpotContact(BaseModel):
    hubspot_id: str
    email: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    lifecycle_stage: str | None = None
    lead_status: str | None = None
    became_lead_at: datetime | None = None
    became_mql_at: datetime | None = None
    became_sql_at: datetime | None = None
    became_customer_at: datetime | None = None
    raw_data: dict = {}


class HubSpotDeal(BaseModel):
    hubspot_id: str
    name: str | None = None
    pipeline: str | None = None
    stage: str | None = None
    amount: float | None = None
    currency: str = "USD"
    close_date: str | None = None
    is_closed: bool = False
    is_won: bool = False
    type: str | None = None  # newbusiness | existingbusiness
    closed_at: datetime | None = None
    hubspot_company_id: str | None = None
    hubspot_contact_id: str | None = None
    raw_data: dict = {}
