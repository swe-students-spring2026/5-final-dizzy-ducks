from flask import (
    Blueprint,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    url_for,
)

from web.auth import login_required
from web.tags import JOB_TAGS, TAG_LABELS, normalize_tags

onboarding_bp = Blueprint("onboarding", __name__)


@onboarding_bp.route("/onboarding", methods=("GET", "POST"))
@login_required
def choose_tags():
    errors = []
    current_tags = g.user["notification_preferences"].get("tags", [])

    if request.method == "POST":
        selected_tags = normalize_tags(request.form.getlist("tags"))
        if not selected_tags:
            errors.append("Choose at least one job tag.")
        else:
            current_app.repository.update_user_tags(g.user["id"], selected_tags)
            flash("Job tags saved.")
            return redirect(url_for("dashboard.index"))
    else:
        selected_tags = current_tags

    return render_template(
        "onboarding.html",
        errors=errors,
        job_tags=JOB_TAGS,
        selected_tags=selected_tags,
        tag_labels=TAG_LABELS,
    )
