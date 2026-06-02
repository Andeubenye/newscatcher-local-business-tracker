"""
CatchAll SDK helpers — submit, poll, pull, monitor.
Used by both tracker.py (article script) and api.py (backend).
"""

import os
import time
from newscatcher_catchall import CatchAllApi
from newscatcher_catchall.core.api_error import ApiError


def _to_dict(obj):
    """Convert SDK typed objects to plain dicts so .get() works safely."""
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "dict"):
        return obj.dict()
    try:
        return vars(obj)
    except TypeError:
        return {}


client = CatchAllApi(api_key=os.environ["CATCHALL_API_KEY"])


def submit(query: str, context: str, validators: list, enrichments: list, limit: int = 50) -> str:
    """
    Preview then submit a CatchAll job.
    Returns job_id. Credits are spent on submit, not preview.
    """
    try:
        preview = client.jobs.initialize(query=query, context=context)
        if preview.date_modification_message:
            print(f"  Note: {preview.date_modification_message}")
    except Exception:
        pass  # preview is optional

    job = client.jobs.create_job(
        query=query,
        context=context,
        validators=validators,
        enrichments=enrichments,
        limit=limit,
        mode="base",
    )
    print(f"  Job submitted: {job.job_id}")
    return job.job_id


def get_status(job_id: str) -> dict:
    """Return current job status as a plain dict."""
    return _to_dict(client.jobs.get_job_status(job_id))


def wait_for_completion(job_id: str, interval: int = 60):
    """
    Poll until a job completes or fails.
    Waits for each job before submitting the next — keeps within concurrency limits.
    """
    while True:
        status = client.jobs.get_job_status(job_id)
        print(f"  Status: {status.status}")
        if status.status == "completed":
            break
        if status.status == "failed":
            raise RuntimeError(f"Job failed: {job_id}")
        time.sleep(interval)


def pull_all(job_id: str) -> list:
    """Pull all paginated results and return as plain dicts."""
    results = client.jobs.get_job_results(job_id)
    print(f"  Found {results.valid_records} confirmed openings")
    return [_to_dict(r) for r in results.all_records]


def create_monitor(job_id: str, schedule: str = "every day at 8 AM UTC") -> str:
    """
    Turn a completed job into a daily recurring monitor.
    Returns monitor_id.
    """
    monitor = client.monitors.create_monitor(
        reference_job_id=job_id,
        schedule=schedule,
        backfill=True,
    )
    print(f"  Monitor created: {monitor.monitor_id}")
    return monitor.monitor_id
