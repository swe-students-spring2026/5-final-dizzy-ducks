from __future__ import annotations

from datetime import datetime, timezone

from bson import ObjectId
from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from web.app.db import get_db
from web.app.utils.auth import login_required, require_poster

bp = Blueprint("management", __name__)


def _oid(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except (TypeError, ValueError):
        abort(404)


@bp.get("/my/gigs")
@login_required
def my_gigs():
    db = get_db()
    gigs = list(
        db.gigs.find({"poster_id": g.user["_id"]}).sort("created_at", -1)
    )
    return render_template("my_gigs.html", gigs=gigs)


@bp.get("/my/gigs/<gig_id>")
@login_required
def gig_applicants(gig_id: str):
    db = get_db()
    gig = db.gigs.find_one({"_id": _oid(gig_id)})
    if not gig:
        abort(404)
    require_poster(gig)

    applications = list(
        db.applications.find({"gig_id": gig["_id"]}).sort("applied_at", -1)
    )
    applicant_ids = [a["applicant_id"] for a in applications]
    applicants_by_id = {
        u["_id"]: u for u in db.users.find({"_id": {"$in": applicant_ids}})
    }

    enriched = []
    for app in applications:
        user = applicants_by_id.get(app["applicant_id"])
        if user:
            enriched.append(
                {
                    "application": app,
                    "applicant": user,
                    "stats": {
                        "rating_avg": user.get("rating_avg", 0),
                        "rating_count": user.get("rating_count", 0),
                        "jobs_completed": user.get("jobs_completed", 0),
                    },
                }
            )
        else:
            enriched.append(
                {
                    "application": app,
                    "applicant": {"name": "Unknown user"},
                    "stats": {"rating_avg": 0, "rating_count": 0, "jobs_completed": 0},
                }
            )

    return render_template("gig_applicants.html", gig=gig, enriched=enriched)


@bp.post("/my/gigs/<gig_id>/applications/<application_id>/decision")
@login_required
def decide_application(gig_id: str, application_id: str):
    db = get_db()
    gig = db.gigs.find_one({"_id": _oid(gig_id)})
    if not gig:
        abort(404)
    require_poster(gig)

    action = request.form.get("action", "").strip().lower()
    if action not in {"accept", "reject"}:
        abort(400)

    application = db.applications.find_one({"_id": _oid(application_id), "gig_id": gig["_id"]})
    if not application:
        abort(404)

    new_status = "accepted" if action == "accept" else "rejected"
    db.applications.update_one(
        {"_id": application["_id"]},
        {"$set": {"status": new_status, "decided_at": datetime.now(timezone.utc)}},
    )

    db.notifications.update_one(
        {"dedupe_key": f"status_change:{application['_id']}:{new_status}"},
        {
            "$setOnInsert": {
                "type": "status_change",
                "status": "pending",
                "to_user_id": application["applicant_id"],
                "payload": {
                    "gig_id": gig["_id"],
                    "gig_title": gig.get("title"),
                    "application_id": application["_id"],
                    "new_status": new_status,
                },
                "created_at": datetime.now(timezone.utc),
            }
        },
        upsert=True,
    )

    if action == "accept":
        db.gigs.update_one({"_id": gig["_id"]}, {"$set": {"status": "filled"}})
        flash("Applicant accepted. Gig marked filled.", "success")
    else:
        flash("Applicant rejected.", "info")

    return redirect(url_for("management.gig_applicants", gig_id=str(gig["_id"])))
