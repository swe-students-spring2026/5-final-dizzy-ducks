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

from ..db import get_db
from ..utils.auth import login_required

bp = Blueprint("profile", __name__)


def _parse_tags(raw: str) -> list[str]:
    parts = [p.strip().lower() for p in (raw or "").split(",")]
    seen: set[str] = set()
    tags: list[str] = []
    for p in parts:
        if not p:
            continue
        if p in seen:
            continue
        seen.add(p)
        tags.append(p)
    return tags[:25]


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

    updates: dict = {
        "tags": tags,
        "notification_preferences.tags": tags,
    }
    if name:
        updates["name"] = name

    if "_id" in g.user:
        db.users.update_one({"_id": g.user["_id"]}, {"$set": updates})
    else:
        current_app.repository.update_user_profile(g.user["id"], name=name, tags=tags)

    flash("Profile updated.", "success")
    return redirect(url_for("profile.me"))


def _user_tags(user: dict) -> list[str]:
    if user.get("tags"):
        return user["tags"]
    return user.get("notification_preferences", {}).get("tags", [])
