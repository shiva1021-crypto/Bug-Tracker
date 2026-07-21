"""HTTP handlers for saved issue filters.

`GET /filters` is a small JSON endpoint (per the spec's own route table)
used to list a user's saved filters; `routes/issue_routes.py`'s list page
calls `services/filter_service.list_saved_filters()` directly to render
its chips rather than making an internal HTTP round-trip to this same
route -- see that route's docstring.
"""

from flask import Blueprint, flash, jsonify, redirect, request, url_for

from services import filter_service
from utils.auth import current_user, login_required

filter_bp = Blueprint("filters", __name__)


@filter_bp.get("/filters")
@login_required
def list_filters():
    user = current_user()
    saved = filter_service.list_saved_filters(user["id"], user["organization_id"])
    return jsonify(
        [{"id": f["id"], "name": f["name"], "filter_data": f["filter_data"]} for f in saved]
    )


@filter_bp.post("/filters/save")
@login_required
def save_filter():
    user = current_user()
    name = request.form.get("name", "")

    # The save form on the issue list page carries the currently-applied
    # filter values as hidden fields (mirroring the query string the
    # results were rendered from) -- reparsing them here from the *form*
    # rather than trusting a client-supplied filter_data blob keeps this
    # consistent with `filter_service.parse_filters()`'s validation of
    # each individual value.
    filters = filter_service.parse_filters(request.form)

    ok, error = filter_service.save_filter(user["id"], user["organization_id"], name, filters)
    flash("Filter saved." if ok else (error or "Could not save the filter."),
          "success" if ok else "error")
    return redirect(url_for("issues.list_issues", **filters))
