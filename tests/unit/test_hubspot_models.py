from src.integrations.hubspot.models import HubSpotDeal, HubSpotContact, HubSpotCompany


def test_deal_defaults():
    deal = HubSpotDeal(hubspot_id="123")
    assert deal.is_won is False
    assert deal.is_closed is False
    assert deal.currency == "USD"
    assert deal.raw_data == {}


def test_contact_optional_fields():
    contact = HubSpotContact(hubspot_id="456")
    assert contact.email is None
    assert contact.lifecycle_stage is None


def test_company_mrr_optional():
    company = HubSpotCompany(hubspot_id="789", name="Acme")
    assert company.mrr is None
    assert company.arr is None
