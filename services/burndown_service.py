"""Burndown chart computation for the currently active sprint.

Reconstructs each day's *actual* remaining work from the Stage 6
`bug_history` audit trail rather than only reporting today's snapshot --
per the Definition of Done, "the actual line reflects real remaining
story points/issues as of each day, not a static mock." No new table is
needed for this: `bug_history` already records every status change with a
timestamp, which is exactly what "as of day D" requires.
"""

from datetime import date, datetime, time, timedelta

from repositories import bug_history_repository

DONE_STATUS = "Done"


def compute_burndown(sprint: dict, issues: list[dict], organization_id: int) -> dict | None:
    """Build the chart data for one sprint, or None if it can't be charted
    (no start date, no end date, or an end date before the start date --
    both are nullable on `sprints`, so a brand-new sprint may not have
    them set yet).

    The "total scope" used for the ideal line and the weight of each
    issue in the actual-remaining calculation, is `story_points` if *any*
    issue in the sprint has one set, otherwise a flat 1-per-issue count --
    see STAGE-08-REPORT.md for why point totals aren't recomputed
    historically (this uses the sprint's *current* membership and current
    point values throughout, not what scope looked like on each historical
    day).
    """
    start_date = sprint["start_date"]
    end_date = sprint["end_date"]
    if not start_date or not end_date or end_date < start_date:
        return None

    day_count = (end_date - start_date).days + 1
    labels = [(start_date + timedelta(days=i)).isoformat() for i in range(day_count)]

    use_points = any(issue["story_points"] for issue in issues)
    metric = "Story Points" if use_points else "Issues"

    def weight_of(issue: dict) -> float:
        return (issue["story_points"] or 0) if use_points else 1

    total = sum(weight_of(issue) for issue in issues)

    if day_count == 1:
        ideal = [total]
    else:
        ideal = [round(total - (total * i / (day_count - 1)), 2) for i in range(day_count)]

    history_by_issue = {
        issue["id"]: bug_history_repository.list_by_bug(issue["id"], organization_id)
        for issue in issues
    }

    today = date.today()
    actual: list[float | None] = []
    for i in range(day_count):
        day = start_date + timedelta(days=i)
        if day > today:
            # Can't know the future -- the actual line simply stops at
            # today, same as a real burndown chart.
            actual.append(None)
            continue

        day_end = datetime.combine(day, time.max)
        remaining = 0.0
        for issue in issues:
            status = _status_as_of(history_by_issue[issue["id"]], day_end, issue["status"])
            if status != DONE_STATUS:
                remaining += weight_of(issue)
        actual.append(remaining)

    return {"labels": labels, "ideal": ideal, "actual": actual, "metric": metric, "total": total}


def _status_as_of(history_rows: list[dict], day_end: datetime, current_status: str) -> str:
    """What status one issue held as of the end of `day_end`, reconstructed
    from its chronologically-ascending `bug_history` rows.

    Only rows that actually recorded a status change (`new_status` is not
    None -- the plain "created the issue"/"edited the issue" entries from
    `issue_service` never do) matter here. Three cases: (1) a status
    change happened on or before this day -- use the most recent one's
    `new_status`; (2) no status change happened by this day, but one
    happened *after* it -- that first change's `old_status` is what the
    issue held for all time up to and including this day; (3) the issue's
    status has never changed at all -- assume it has always been what it
    is right now.
    """
    last_known_on_or_before = None
    earliest_old_status = None

    for row in history_rows:
        if row["new_status"] is None:
            continue
        if earliest_old_status is None:
            earliest_old_status = row["old_status"]
        if row["changed_at"] <= day_end:
            last_known_on_or_before = row["new_status"]
        else:
            break  # rows are chronological ascending -- nothing earlier follows

    if last_known_on_or_before is not None:
        return last_known_on_or_before
    if earliest_old_status is not None:
        return earliest_old_status
    return current_status
