"""Provider search tool."""

from openemr_mcp.data_source import get_effective_data_source, get_http_client
from openemr_mcp.schemas import Provider, ProviderSearchResponse

MOCK_PROVIDERS: list[Provider] = [
    Provider(
        provider_id="prov001",
        full_name="Dr. Sarah Chen",
        specialty="Cardiology",
        location="Portland",
        accepting_new_patients=True,
    ),
    Provider(
        provider_id="prov002",
        full_name="Dr. Marcus Johnson",
        specialty="Cardiology",
        location="Anytown",
        accepting_new_patients=False,
    ),
    Provider(
        provider_id="prov003",
        full_name="Dr. Priya Patel",
        specialty="Endocrinology",
        location="Portland",
        accepting_new_patients=True,
    ),
    Provider(
        provider_id="prov004",
        full_name="Dr. James Okafor",
        specialty="Endocrinology",
        location="Springfield",
        accepting_new_patients=True,
    ),
    Provider(
        provider_id="prov005",
        full_name="Dr. Elena Vasquez",
        specialty="Internal Medicine",
        location="Anytown",
        accepting_new_patients=True,
    ),
    Provider(
        provider_id="prov006",
        full_name="Dr. Robert Kim",
        specialty="Internal Medicine",
        location="Portland",
        accepting_new_patients=True,
    ),
    Provider(
        provider_id="prov007",
        full_name="Dr. Amelia Torres",
        specialty="Psychiatry",
        location="Springfield",
        accepting_new_patients=True,
    ),
    Provider(
        provider_id="prov008",
        full_name="Dr. David Obi",
        specialty="Psychiatry",
        location="Anytown",
        accepting_new_patients=False,
    ),
    Provider(
        provider_id="prov009",
        full_name="Dr. Linda Park",
        specialty="Rheumatology",
        location="Portland",
        accepting_new_patients=True,
    ),
    Provider(
        provider_id="prov010",
        full_name="Dr. Carlos Meza",
        specialty="Neurology",
        location="Springfield",
        accepting_new_patients=True,
    ),
    Provider(
        provider_id="prov011",
        full_name="Dr. Fatima Hassan",
        specialty="Pain Management",
        location="Anytown",
        accepting_new_patients=True,
    ),
    Provider(
        provider_id="prov012",
        full_name="Dr. William Grant",
        specialty="Pulmonology",
        location="Portland",
        accepting_new_patients=True,
    ),
    Provider(
        provider_id="prov013",
        full_name="Dr. Sophie Nguyen",
        specialty="Allergy/Immunology",
        location="Springfield",
        accepting_new_patients=True,
    ),
    Provider(
        provider_id="prov014",
        full_name="Dr. Thomas Reed",
        specialty="Dermatology",
        location="Anytown",
        accepting_new_patients=True,
    ),
    Provider(
        provider_id="prov015",
        full_name="Dr. Mei Li",
        specialty="OB/GYN",
        location="Portland",
        accepting_new_patients=True,
    ),
]


def run_provider_search(specialty: str | None = None, location: str | None = None) -> ProviderSearchResponse:
    ds = get_effective_data_source()
    if ds == "api":
        from openemr_mcp.repositories.fhir_api import search_providers_api

        providers = search_providers_api(specialty, location, get_http_client())
        return ProviderSearchResponse(
            providers=providers, specialty_queried=specialty or "", location_queried=location or ""
        )
    results = list(MOCK_PROVIDERS)
    if specialty and specialty.strip():
        spec_lower = specialty.strip().lower()
        results = [p for p in results if spec_lower in p.specialty.lower()]
    if location and location.strip():
        loc_lower = location.strip().lower()
        results = [p for p in results if loc_lower in p.location.lower()]
    return ProviderSearchResponse(providers=results, specialty_queried=specialty or "", location_queried=location or "")
