"""
Local Business Opening Tracker
--------------------------------
Finds confirmed new business openings anywhere in the world using the
CatchAll Web Search API. Runs three signal-term queries in sequence,
deduplicates results, and optionally emails a digest.

Run:
    python3 tracker.py
"""

import os
import time
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from pydantic import EmailStr, TypeAdapter
from newscatcher_catchall import CatchAllApi
from newscatcher_catchall.core.api_error import ApiError

from core.skill import SKILL_CONTEXT, VALIDATORS, ENRICHMENTS
from core.normalize import normalize_record, deduplicate, filter_by_qualifier
from core.email_router import send_results_email

load_dotenv()


SIGNAL_TERMS = ["grand opening", "now open", "soft opening"]


# ── Search config ─────────────────────────────────────────────────────────────

@dataclass
class SearchConfig:
    business_type: str
    city: str
    country: str
    days: int
    email: str | None

    @property
    def location(self) -> str:
        return f"{self.city}, {self.country}"

    @property
    def queries(self) -> list[str]:
        return [
            f"{signal} {self.business_type} {self.location} last {self.days} days"
            for signal in SIGNAL_TERMS
        ]


def _prompt(question: str, required: bool = True, default: str | None = None) -> str:
    """Prompt the user for input, re-asking if required and empty."""
    suffix = f" (default {default})" if default else ""
    while True:
        value = input(f"{question}{suffix}: ").strip()
        if value:
            return value
        if not required and default is not None:
            return default
        if not required:
            return ""
        print("  This field can't be empty, try again.")


def _validate_email(raw: str) -> str | None:
    """Return a validated email or None. Uses Pydantic EmailStr."""
    if not raw:
        return None
    try:
        TypeAdapter(EmailStr).validate_python(raw)
        return raw
    except Exception:
        print("  That doesn't look like a valid email — skipping alerts.")
        return None


def collect_inputs() -> SearchConfig:
    print("\nLocal Business Opening Tracker")
    print("─" * 40)

    business_type = _prompt("What type of business are you tracking?")
    country = _prompt("Which country?").title()
    city = _prompt(f"Which city in {country}?").title()
    days_raw = _prompt("How many days back to search?",
                       required=False, default="14")
    email_raw = _prompt("Email for results?", required=False)

    try:
        days = min(int(days_raw), 30)
    except ValueError:
        days = 14

    return SearchConfig(
        business_type=business_type,
        city=city,
        country=country,
        days=days,
        email=_validate_email(email_raw),
    )


# ── API calls ─────────────────────────────────────────────────────────────────

def _to_dict(obj) -> dict:
    """Convert SDK typed objects to plain dicts so .get() works safely."""
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "dict"):
        return obj.dict()
    try:
        return vars(obj)
    except TypeError:
        return {}


def run_query(client: CatchAllApi, query: str) -> tuple[str, list[dict]]:
    """Submit one query, wait for completion, and return (job_id, records)."""
    try:
        # Preview costs nothing — confirms the date range is valid
        preview = client.jobs.initialize(query=query, context=SKILL_CONTEXT)
        if preview.date_modification_message:
            print(f"  Note: {preview.date_modification_message}")
    except Exception:
        pass

    job = client.jobs.create_job(
        query=query,
        context=SKILL_CONTEXT,
        validators=VALIDATORS,
        enrichments=ENRICHMENTS,
        limit=50,
        mode="base",
    )

    # Wait for completion before the next query — keeps within concurrency limits
    while True:
        status = client.jobs.get_job_status(job.job_id)
        print(f"  {status.status}...")
        if status.status == "completed":
            break
        if status.status == "failed":
            raise RuntimeError(f"Job {job.job_id} failed")
        time.sleep(60)

    results = client.jobs.get_job_results(job.job_id)
    print(f"  {results.valid_records} openings confirmed")
    return job.job_id, [_to_dict(r) for r in results.all_records]


def create_monitor(client: CatchAllApi, job_id: str) -> None:
    """Set up a daily monitor so this search runs automatically."""
    try:
        monitor = client.monitors.create_monitor(
            reference_job_id=job_id,
            schedule="every day at 8 AM UTC",
            backfill=True,
        )
        print(f"  Daily monitor created: {monitor.monitor_id}")
    except Exception:
        print("  Daily monitor skipped — you've hit your plan limit")


# ── Output ────────────────────────────────────────────────────────────────────

def print_results(results: list[dict]) -> None:
    for i, r in enumerate(results, 1):
        print(f"{i}. {r.get('business_name') or 'Unknown'}")
        for label, key in [
            ("Type",     "business_type"),
            ("Location", "location_details"),
            ("Status",   "opening_qualifier"),
            ("Date",     "opening_date"),
            ("Evidence", "evidence_summary"),
            ("Source",   "source_url"),
        ]:
            value = r.get(key)
            if value:
                display = value.replace(
                    "_", " ") if key == "opening_qualifier" else value
                print(f"   {label:<10}{display}")
        print()


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    config = collect_inputs()

    print(
        f"\nSearching for {config.business_type} openings in {config.location} over the last {config.days} days...")
    if config.email:
        print(f"Results will also be sent to {config.email}")
    print()

    api_key = os.environ.get("CATCHALL_API_KEY")
    if not api_key:
        raise SystemExit(
            "CATCHALL_API_KEY is missing. Add it to your .env file and try again.")

    client = CatchAllApi(api_key=api_key)
    all_raw = []
    monitor_created = False

    for query in config.queries:
        print(f"Running: {query}")
        try:
            job_id, records = run_query(client, query)
            all_raw.extend(records)

            if not monitor_created and records:
                create_monitor(client, job_id)
                monitor_created = True

        except ApiError as e:
            print(f"  API error ({e.status_code}): {e.body}")
        except RuntimeError as e:
            print(f"  {e}")
        print()

    normalized = [normalize_record(r) for r in all_raw]
    deduplicated = deduplicate(normalized)
    now_open = filter_by_qualifier(deduplicated, ["now_open", "event_held"])
    upcoming = filter_by_qualifier(deduplicated, ["date_announced"])

    print("─" * 40)
    print(f"{len(deduplicated)} confirmed openings — {len(now_open)} open now, {len(upcoming)} opening soon")
    print("─" * 40)
    print()

    print_results(deduplicated)

    if config.email and deduplicated:
        send_results_email(
            to_email=config.email,
            results=deduplicated,
            query=f"{config.business_type} openings in {config.location} last {config.days} days",
        )


if __name__ == "__main__":
    main()
