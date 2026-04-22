from datetime import datetime
import hubspot
from src.core.config import settings
from src.integrations.hubspot.models import HubSpotCompany, HubSpotContact, HubSpotDeal

_CONTACT_PROPERTIES = [
    "email", "firstname", "lastname", "lifecyclestage", "hs_lead_status",
    "hs_lifecyclestage_lead_date",
    "hs_lifecyclestage_marketingqualifiedlead_date",
    "hs_lifecyclestage_salesqualifiedlead_date",
    "hs_lifecyclestage_customer_date",
]

_COMPANY_PROPERTIES = [
    "name", "domain", "industry", "country", "city", "annualrevenue",
]

_DEAL_PROPERTIES = [
    "dealname", "pipeline", "dealstage", "amount", "currency",
    "closedate", "hs_is_closed", "hs_is_closed_won", "dealtype",
]


def _client() -> hubspot.Client:
    return hubspot.Client.create(access_token=settings.hubspot_access_token)


def _parse_hs_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        if value.isdigit():
            return datetime.fromtimestamp(int(value) / 1000)
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _bool_prop(props: dict, key: str) -> bool:
    return str(props.get(key, "false")).lower() == "true"


def fetch_all_contacts() -> list[HubSpotContact]:
    client = _client()
    results, after = [], None
    while True:
        page = client.crm.contacts.basic_api.get_page(
            limit=100, properties=_CONTACT_PROPERTIES, after=after
        )
        for c in page.results:
            p = c.properties
            results.append(HubSpotContact(
                hubspot_id=c.id,
                email=p.get("email"),
                first_name=p.get("firstname"),
                last_name=p.get("lastname"),
                lifecycle_stage=p.get("lifecyclestage"),
                lead_status=p.get("hs_lead_status"),
                became_lead_at=_parse_hs_timestamp(p.get("hs_lifecyclestage_lead_date")),
                became_mql_at=_parse_hs_timestamp(
                    p.get("hs_lifecyclestage_marketingqualifiedlead_date")
                ),
                became_sql_at=_parse_hs_timestamp(
                    p.get("hs_lifecyclestage_salesqualifiedlead_date")
                ),
                became_customer_at=_parse_hs_timestamp(
                    p.get("hs_lifecyclestage_customer_date")
                ),
                raw_data=dict(p),
            ))
        if not page.paging or not page.paging.next:
            break
        after = page.paging.next.after
    return results


def fetch_all_companies() -> list[HubSpotCompany]:
    client = _client()
    results, after = [], None
    while True:
        page = client.crm.companies.basic_api.get_page(
            limit=100, properties=_COMPANY_PROPERTIES, after=after
        )
        for co in page.results:
            p = co.properties
            arr_raw = p.get("annualrevenue")
            arr = float(arr_raw) if arr_raw else None
            results.append(HubSpotCompany(
                hubspot_id=co.id,
                name=p.get("name") or "Unknown",
                domain=p.get("domain"),
                industry=p.get("industry"),
                country=p.get("country"),
                city=p.get("city"),
                arr=arr,
                mrr=round(arr / 12, 2) if arr else None,
                raw_data=dict(p),
            ))
        if not page.paging or not page.paging.next:
            break
        after = page.paging.next.after
    return results


def fetch_all_deals() -> list[HubSpotDeal]:
    client = _client()
    results, after = [], None
    while True:
        page = client.crm.deals.basic_api.get_page(
            limit=100,
            properties=_DEAL_PROPERTIES,
            associations=["contacts", "companies"],
            after=after,
        )
        for deal in page.results:
            p = deal.properties
            amount_raw = p.get("amount")
            is_won = _bool_prop(p, "hs_is_closed_won")
            is_closed = _bool_prop(p, "hs_is_closed")
            close_date_raw = p.get("closedate")

            company_hs_id, contact_hs_id = None, None
            if deal.associations:
                if getattr(deal.associations, "companies", None) and deal.associations.companies.results:
                    company_hs_id = str(deal.associations.companies.results[0].id)
                if getattr(deal.associations, "contacts", None) and deal.associations.contacts.results:
                    contact_hs_id = str(deal.associations.contacts.results[0].id)

            results.append(HubSpotDeal(
                hubspot_id=deal.id,
                name=p.get("dealname"),
                pipeline=p.get("pipeline"),
                stage=p.get("dealstage"),
                amount=float(amount_raw) if amount_raw else None,
                close_date=close_date_raw,
                is_closed=is_closed,
                is_won=is_won,
                type=p.get("dealtype"),
                closed_at=_parse_hs_timestamp(close_date_raw) if is_closed else None,
                hubspot_company_id=company_hs_id,
                hubspot_contact_id=contact_hs_id,
                raw_data=dict(p),
            ))
        if not page.paging or not page.paging.next:
            break
        after = page.paging.next.after
    return results
