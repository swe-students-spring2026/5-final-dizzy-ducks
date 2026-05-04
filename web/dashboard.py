from flask import Blueprint, current_app, g, render_template, request

from web.auth import login_required
from web.tags import JOB_TAGS, normalize_tags

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
@login_required
def index():
    saved_tags = g.user.get("notification_preferences", {}).get("tags", [])
    multi_raw = request.args.getlist("tag")
    search = request.args.get("q", "").strip()

    # Single <select name="tag"> sends one value; multiple ?tag= still supported.
    tag_filter_value: str | None
    if len(multi_raw) > 1:
        selected_tags = normalize_tags(multi_raw)
        tag_filter_value = selected_tags[0] if selected_tags else None
    elif len(multi_raw) == 1:
        raw = (multi_raw[0] or "").strip()
        if raw == "__all__":
            selected_tags = []
            tag_filter_value = "__all__"
        elif raw == "":
            selected_tags = saved_tags
            tag_filter_value = None
        else:
            selected_tags = normalize_tags([raw])
            if selected_tags:
                tag_filter_value = selected_tags[0]
            else:
                selected_tags = saved_tags
                tag_filter_value = None
    else:
        selected_tags = saved_tags
        tag_filter_value = None

    gigs = current_app.repository.list_open_gigs(tags=selected_tags, search=search)

    return render_template(
        "dashboard.html",
        gigs=gigs,
        job_tags=JOB_TAGS,
        saved_tags=saved_tags,
        search=search,
        tag_filter_value=tag_filter_value,
    )
