from __future__ import annotations

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

from web.tags import normalize_tags

from ..db import get_db
from ..utils.auth import login_required

bp = Blueprint("profile", __name__)


def _parse_tags(raw: str) -> list[str]:
    parts = [p.strip().lower() for p in (raw or "").split(",")]
    return normalize_tags(parts)


@bp.get("/me")
@login_required
def me():
    return render_template("profile.html", user=g.user, tags=_user_tags(g.user))


@bp.post("/me")
@login_required
def update_me():
    db = get_db()
    name = (request.form.get("name") or "").strip()
    tags = _parse_tags(request.form.get("tags") or "")

    new_gig_alerts = request.form.get("new_gig_alerts") == "on"
    application_alerts = request.form.get("application_alerts") == "on"
    status_alerts = request.form.get("status_alerts") == "on"
    updates: dict = {
        "tags": tags,
        "notification_preferences.tags": tags,
        "notification_preferences.new_gig_alerts": new_gig_alerts,
        "notification_preferences.application_alerts": application_alerts,
        "notification_preferences.status_alerts": status_alerts,
    }
    if name:
        updates["name"] = name

    if "_id" in g.user:
        db.users.update_one({"_id": g.user["_id"]}, {"$set": updates})
    else:
        current_app.repository.update_user_profile(
            g.user["id"],
            name=name,
            tags=tags,
            notification_preferences={
                "new_gig_alerts": new_gig_alerts,
                "application_alerts": application_alerts,
                "status_alerts": status_alerts,
            },
        )

    flash("Profile updated.", "success")
    return redirect(url_for("profile.me"))


def _user_tags(user: dict) -> list[str]:
    if user.get("tags"):
        return user["tags"]
    return user.get("notification_preferences", {}).get("tags", [])
