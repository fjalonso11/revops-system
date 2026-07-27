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


def _first_association_id(associations, kind: str) -> str | None:
    """Return the first associated object id for `kind` ('companies' or 'contacts').

    Valid output: a HubSpot object id string when the deal has an association
                  of this kind, else None.
    Provenance:   id <- associations[kind]['results'][0]['id']

    HubSpot's SDK returns `associations` as a dict on this API path (verified
    against a live response on 2026-07-27), but older/other SDK paths return an
    object with attributes. This reads BOTH shapes so an SDK version change
    cannot silently reintroduce the NULL-company bug. Takes the FIRST result
    only: a deal is assumed to map to one company; the response can contain
    label variants (e.g. 'deal_to_company' and 'deal_to_company_unlabeled')
    that repeat the same id, so first-wins is intended, not a bug.
    """
    if not associations:
        return None

    # Top level: dict {'companies': {...}} or object with .companies attribute
    if isinstance(associations, dict):
        block = associations.get(kind)
    else:
        block = getattr(associations, kind, None)
    if not block:
        return None

    # Results list: dict {'results': [...]} or object with .results attribute
    if isinstance(block, dict):
        results = block.get("results")
    else:
        results = getattr(block, "results", None)
    if not results:
        return None

    # First result: dict {'id': '...'} or object with .id attribute
    first = results[0]
    if isinstance(first, dict):
        obj_id = first.get("id")
    else:
        obj_id = getattr(first, "id", None)

    return str(obj_id) if obj_id is not None else None


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

            company_hs_id = _first_association_id(deal.associations, "companies")
            contact_hs_id = _first_association_id(deal.associations, "contacts")

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
