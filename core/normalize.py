"""
Normalize raw CatchAll records into flat dicts and deduplicate across queries.
Uses rapidfuzz for fuzzy name and location matching — faster and more accurate
than regex-based token overlap, and handles multilingual business names natively.
"""

from rapidfuzz import fuzz


def normalize_record(record: dict) -> dict:
    enrichment = record.get("enrichment", {})
    citations  = record.get("citations", [])
    return {
        "record_id":         record.get("record_id"),
        "record_title":      record.get("record_title"),
        "business_name":     enrichment.get("business_name"),
        "business_type":     enrichment.get("business_type"),
        "opening_date":      enrichment.get("opening_date"),
        "opening_qualifier": enrichment.get("opening_qualifier"),
        "location_details":  enrichment.get("location_details"),
        "owner_operator":    enrichment.get("owner_operator"),
        "evidence_summary":  enrichment.get("evidence_summary"),
        "source_url":        enrichment.get("source_url") or (
            citations[0].get("link") if citations else None
        ),
        "citations":         citations,
        "confidence":        enrichment.get("enrichment_confidence"),
    }


def deduplicate(records: list) -> list:
    """
    Fuzzy deduplication using token_sort_ratio — handles:
    - Translated names: "LONGJING Restaurant" vs "LONGJING Restaurant 绿茶餐厅"
    - Address variations: "6th floor Lucky Plaza" vs "sixth floor, Lucky Plaza"
    A record is a duplicate only if both name AND location match.
    """
    seen, result = [], []

    for record in records:
        name     = record.get("business_name") or ""
        location = record.get("location_details") or ""

        if not name or not location:
            continue

        is_dup = any(
            fuzz.token_sort_ratio(name, s_name) >= 85
            and fuzz.token_sort_ratio(location, s_loc) >= 60
            for s_name, s_loc in seen
        )

        if not is_dup:
            seen.append((name, location))
            result.append(record)

    return result


def filter_by_qualifier(records: list, qualifiers: list) -> list:
    return [r for r in records if r.get("opening_qualifier") in qualifiers]


def filter_by_confidence(records: list, level: str = "high") -> list:
    return [r for r in records if r.get("confidence") == level]


def filter_by_business_type(records: list, business_type: str) -> list:
    t = business_type.lower()
    return [r for r in records if t in str(r.get("business_type") or "").lower()]
