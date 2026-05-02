from __future__ import annotations

from datetime import datetime, timezone

from bson import ObjectId
from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from ..db import get_db
from ..utils.auth import load_current_user, login_required

bp = Blueprint("gigs", __name__)


def _oid(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except (TypeError, ValueError):
        abort(404)


@bp.get("/gigs/<gig_id>")
def gig_detail(gig_id: str):
    load_current_user()
    db = get_db()
    gig = db.gigs.find_one({"_id": _oid(gig_id)})
    if not gig:
        abort(404)

    poster = db.users.find_one({"_id": gig["poster_id"]}) if gig.get("poster_id") else None

    current_user = getattr(g, "user", None)
    existing_application = None
    is_poster = False

    if current_user:
        is_poster = str(gig.get("poster_id")) == str(current_user["_id"])
        existing_application = db.applications.find_one(
            {"gig_id": gig["_id"], "applicant_id": current_user["_id"]}
        )

    return render_template(
        "gig_detail.html",
        gig=gig,
        poster=poster,
        existing_application=existing_application,
        is_poster=is_poster,
    )


@bp.post("/gigs/<gig_id>/apply")
@login_required
def apply(gig_id: str):
    db = get_db()
    gig = db.gigs.find_one({"_id": _oid(gig_id)})
    if not gig:
        abort(404)

    if str(gig.get("poster_id")) == str(g.user["_id"]):
        flash("You cannot apply to your own gig.", "error")
        return redirect(url_for("gigs.gig_detail", gig_id=gig_id))

    if gig.get("status") != "open":
        flash("This gig is no longer accepting applications.", "error")
        return redirect(url_for("gigs.gig_detail", gig_id=gig_id))

    already = db.applications.find_one({"gig_id": gig["_id"], "applicant_id": g.user["_id"]})
    if already:
        flash("You already applied to this gig.", "info")
        return redirect(url_for("gigs.gig_detail", gig_id=gig_id))

    message = (request.form.get("message") or "").strip()
    now = datetime.now(timezone.utc)
    result = db.applications.insert_one(
        {
            "gig_id": gig["_id"],
            "applicant_id": g.user["_id"],
            "status": "pending",
            "message": message,
            "applied_at": now,
        }
    )

    db.notifications.update_one(
        {"dedupe_key": f"new_application:{result.inserted_id}"},
        {
            "$setOnInsert": {
                "type": "new_application",
                "status": "pending",
                "to_user_id": gig["poster_id"],
                "payload": {
                    "gig_id": gig["_id"],
                    "gig_title": gig.get("title"),
                    "application_id": result.inserted_id,
                    "applicant_name": g.user.get("name"),
                },
                "created_at": now,
            }
        },
        upsert=True,
    )

    flash("Application submitted!", "success")
    return redirect(url_for("gigs.gig_detail", gig_id=gig_id))


@bp.get("/my/applied")
@login_required
def my_applied():
    db = get_db()
    applications = list(
        db.applications.find({"applicant_id": g.user["_id"]}).sort("applied_at", -1)
    )

    gig_ids = [a["gig_id"] for a in applications]
    gigs_by_id = {g_doc["_id"]: g_doc for g_doc in db.gigs.find({"_id": {"$in": gig_ids}})}

    rows = []
    for app in applications:
        gig = gigs_by_id.get(app["gig_id"])
        rows.append({"application": app, "gig": gig})

    return render_template("my_applied.html", rows=rows)
