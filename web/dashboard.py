from flask import Blueprint, current_app, g, render_template, request

from web.auth import login_required
from web.tags import JOB_TAGS, normalize_tags

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
@login_required
def index():
    requested_tags = request.args.getlist("tag")
    saved_tags = g.user["notification_preferences"].get("tags", [])
    selected_tags = normalize_tags(requested_tags) if requested_tags else saved_tags
    search = request.args.get("q", "").strip()
    gigs = current_app.repository.list_open_gigs(tags=selected_tags, search=search)

    return render_template(
        "dashboard.html",
        gigs=gigs,
        job_tags=JOB_TAGS,
        saved_tags=saved_tags,
        search=search,
        selected_tags=selected_tags,
    )
