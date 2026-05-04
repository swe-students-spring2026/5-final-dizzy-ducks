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

from web.tags import JOB_TAGS

from ..db import get_db
from ..utils.auth import login_required, require_poster

bp = Blueprint("management", __name__)


def _oid(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError, ValueError):
        abort(404)


@bp.get("/my/gigs")
@login_required
def my_gigs():
    db = get_db()
    if "_id" in g.user:
        gigs = list(db.gigs.find({"poster_id": g.user["_id"]}).sort("created_at", -1))
    else:
        gigs = current_app.repository.list_gigs_by_poster(g.user["id"])
    return render_template("my_gigs.html", gigs=gigs)


@bp.route("/my/gigs/new", methods=("GET", "POST"))
@login_required
def new_gig():
    values = _gig_form_values()
    questions = _parse_questions()
    errors: list[str] = []

    if request.method == "POST":
        errors = _validate_gig_form(values)
        if not errors:
            _create_gig(values, questions)
            flash("Gig posted.", "success")
            return redirect(url_for("management.my_gigs"))

    return render_template(
        "gig_form.html",
        errors=errors,
        job_tags=JOB_TAGS,
        values=values,
        questions=questions,
    )


@bp.get("/my/gigs/<gig_id>")
@login_required
def gig_applicants(gig_id: str):
    if "_id" not in g.user:
        return _repository_gig_applicants(gig_id)

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
    if "_id" not in g.user:
        return _decide_repository_application(gig_id, application_id)

    db = get_db()
    gig = db.gigs.find_one({"_id": _oid(gig_id)})
    if not gig:
        abort(404)
    require_poster(gig)

    action = request.form.get("action", "").strip().lower()
    if action not in {"accept", "reject"}:
        abort(400)

    application = db.applications.find_one(
        {"_id": _oid(application_id), "gig_id": gig["_id"]}
    )
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


def _repository_gig_applicants(gig_id: str):
    repository = current_app.repository
    gig = repository.get_gig_by_id(gig_id)
    if not gig:
        abort(404)
    if str(gig.get("poster_id")) != str(g.user["id"]):
        abort(403)

    enriched = []
    for application in repository.list_applications_by_gig(gig["id"]):
        applicant = repository.get_user_by_id(application["applicant_id"]) or {
            "name": "Unknown user"
        }
        enriched.append(
            {
                "application": application,
                "applicant": applicant,
                "stats": {
                    "rating_avg": applicant.get("rating_avg", 0),
                    "rating_count": applicant.get("rating_count", 0),
                    "jobs_completed": applicant.get("jobs_completed", 0),
                },
            }
        )

    return render_template("gig_applicants.html", gig=gig, enriched=enriched)


def _decide_repository_application(gig_id: str, application_id: str):
    repository = current_app.repository
    gig = repository.get_gig_by_id(gig_id)
    if not gig:
        abort(404)
    if str(gig.get("poster_id")) != str(g.user["id"]):
        abort(403)

    action = request.form.get("action", "").strip().lower()
    if action not in {"accept", "reject"}:
        abort(400)

    application = repository.get_application_by_id(application_id)
    if not application or str(application["gig_id"]) != str(gig["id"]):
        abort(404)

    new_status = "accepted" if action == "accept" else "rejected"
    repository.update_application_status(application_id, new_status)

    if action == "accept":
        repository.update_gig_status(gig["id"], "filled")
        flash("Applicant accepted. Gig marked filled.", "success")
    else:
        flash("Applicant rejected.", "info")

    return redirect(url_for("management.gig_applicants", gig_id=gig["id"]))


def _gig_form_values() -> dict[str, str]:
    return {
        "title": request.form.get("title", "").strip(),
        "category": request.form.get("category", "").strip(),
        "pay": request.form.get("pay", "").strip(),
        "location": request.form.get("location", "").strip(),
        "date": request.form.get("date", "").strip(),
        "description": request.form.get("description", "").strip(),
    }


def _parse_questions() -> list[dict]:
    count = int(request.form.get("question_count", "0") or "0")
    questions = []
    for i in range(count):
        text = request.form.get(f"question_text_{i}", "").strip()
        if text:
            required = request.form.get(f"question_required_{i}") == "on"
            questions.append({"text": text, "required": required})
    return questions


def _validate_gig_form(values: dict[str, str]) -> list[str]:
    errors = []
    required_labels = {
        "title": "Title",
        "category": "Category",
        "pay": "Pay",
        "location": "Location",
        "date": "Date",
        "description": "Description",
    }

    for field, label in required_labels.items():
        if not values[field]:
            errors.append(f"{label} is required.")

    if values["category"] and values["category"] not in JOB_TAGS:
        errors.append("Choose a valid category.")

    if values["date"]:
        try:
            parsed_date = datetime.strptime(values["date"], "%Y-%m-%d")
            if parsed_date.strftime("%Y-%m-%d") != values["date"]:
                raise ValueError
        except ValueError:
            errors.append("Date must use YYYY-MM-DD format.")

    return errors


def _create_gig(values: dict[str, str], questions: list[dict]) -> None:
    if "_id" in g.user:
        document = {
            **values,
            "poster_id": g.user["_id"],
            "status": "open",
            "created_at": datetime.now(timezone.utc),
            "questions": questions,
        }
        get_db().gigs.insert_one(document)
        return

    current_app.repository.create_gig(
        **values,
        poster_id=g.user["id"],
        status="open",
    )
