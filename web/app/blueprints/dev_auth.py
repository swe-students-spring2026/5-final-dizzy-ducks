from __future__ import annotations

import os

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from ..db import get_db

bp = Blueprint("auth", __name__)


def _enabled() -> bool:
    return os.environ.get("ENABLE_DEV_AUTH", "").strip() == "1"


@bp.get("/auth/dev-login")
def dev_login_form():
    if not _enabled():
        return {"error": "ENABLE_DEV_AUTH is not enabled"}, 404
    return render_template("dev_login.html")


@bp.post("/auth/dev-login")
def dev_login_submit():
    if not _enabled():
        return {"error": "ENABLE_DEV_AUTH is not enabled"}, 404

    email = (request.form.get("email") or "").strip().lower()
    name = (request.form.get("name") or "").strip()
    if not email:
        flash("Email is required.", "error")
        return redirect(url_for(".dev_login_form"))

    db = get_db()
    user = db.users.find_one({"email": email})
    if not user:
        user_id = db.users.insert_one(
            {"email": email, "name": name or email.split("@")[0], "tags": []}
        ).inserted_id
    else:
        user_id = user["_id"]

    session["user_id"] = str(user_id)
    flash("Logged in (dev).", "success")
    return redirect("/my/gigs")


@bp.post("/auth/logout")
def logout():
    if not _enabled():
        return {"error": "ENABLE_DEV_AUTH is not enabled"}, 404
    session.pop("user_id", None)
    flash("Logged out.", "info")
    return redirect(url_for(".dev_login_form"))
