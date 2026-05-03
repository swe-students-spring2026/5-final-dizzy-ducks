from __future__ import annotations

from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    url_for,
)

from ..db import get_db
from ..utils.auth import load_current_user, login_required

bp = Blueprint("gigs", __name__)


def _oid(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError, ValueError):
        abort(404)


def _try_oid(value: str) -> ObjectId | None:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError, ValueError):
        return None


@bp.get("/gigs/<gig_id>")
def gig_detail(gig_id: str):
    load_current_user()
    db = get_db()
    oid = _try_oid(gig_id)
    gig = db.gigs.find_one({"_id": oid}) if oid else None
    if gig:
        return _render_mongo_gig_detail(gig)

    gig = current_app.repository.get_gig_by_id(gig_id)
    if not gig:
        abort(404)

    current_user = getattr(g, "user", None)
    current_user_id = current_user.get("id") if current_user else None
    existing_application = None
    is_poster = False

    if current_user_id:
        is_poster = str(gig.get("poster_id")) == str(current_user_id)
        existing_application = current_app.repository.get_application(
            gig_id=gig["id"],
            applicant_id=current_user_id,
        )

    poster = None
    if gig.get("poster_id"):
        poster = current_app.repository.get_user_by_id(gig["poster_id"])

    return render_template(
        "gig_detail.html",
        gig=gig,
        poster=poster,
        existing_application=existing_application,
        is_poster=is_poster,
    )


def _render_mongo_gig_detail(gig: dict):
    db = get_db()
    poster = (
        db.users.find_one({"_id": gig["poster_id"]}) if gig.get("poster_id") else None
    )

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
    if "_id" not in g.user:
        return _apply_repository_gig(gig_id)

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

    already = db.applications.find_one(
        {"gig_id": gig["_id"], "applicant_id": g.user["_id"]}
    )
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


def _apply_repository_gig(gig_id: str):
    repository = current_app.repository
    gig = repository.get_gig_by_id(gig_id)
    if not gig:
        abort(404)

    applicant_id = g.user["id"]
    if str(gig.get("poster_id")) == str(applicant_id):
        flash("You cannot apply to your own gig.", "error")
        return redirect(url_for("dashboard.index"))

    if gig.get("status") != "open":
        flash("This gig is no longer accepting applications.", "error")
        return redirect(url_for("dashboard.index"))

    already = repository.get_application(gig_id=gig["id"], applicant_id=applicant_id)
    if already:
        flash("You already applied to this gig.", "info")
        return redirect(url_for("gigs.my_applied"))

    message = (request.form.get("message") or "").strip()
    repository.create_application(
        gig_id=gig["id"],
        applicant_id=applicant_id,
        message=message,
    )

    flash("Application submitted!", "success")
    return redirect(url_for("gigs.my_applied"))


@bp.get("/my/applied")
@login_required
def my_applied():
    if "_id" not in g.user:
        applications = current_app.repository.list_applications_by_applicant(
            g.user["id"]
        )
        rows = [
            {
                "application": application,
                "gig": current_app.repository.get_gig_by_id(application["gig_id"]),
            }
            for application in applications
        ]
        return render_template("my_applied.html", rows=rows)

    db = get_db()
    applications = list(
        db.applications.find({"applicant_id": g.user["_id"]}).sort("applied_at", -1)
    )

    gig_ids = [a["gig_id"] for a in applications]
    gigs_by_id = {
        g_doc["_id"]: g_doc for g_doc in db.gigs.find({"_id": {"$in": gig_ids}})
    }

    rows = []
    for app in applications:
        gig = gigs_by_id.get(app["gig_id"])
        rows.append({"application": app, "gig": gig})

    return render_template("my_applied.html", rows=rows)
