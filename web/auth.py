from __future__ import annotations

from functools import wraps
from urllib.parse import urlsplit

from flask import (
    Blueprint,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from web.repositories import DuplicateEmailError

auth_bp = Blueprint("auth", __name__)


@auth_bp.before_app_request
def load_logged_in_user():
    user_id = session.get("user_id")
    if user_id is None:
        g.user = None
        return

    g.user = current_app.repository.get_user_by_id(user_id)
    if g.user is None:
        session.clear()


def login_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for("auth.login", next=request.path))
        return view(**kwargs)

    return wrapped_view


@auth_bp.route("/signup", methods=("GET", "POST"))
def signup():
    errors = []
    values = {"name": "", "email": ""}

    if request.method == "POST":
        values = {
            "name": request.form.get("name", "").strip(),
            "email": request.form.get("email", "").strip(),
        }
        password = request.form.get("password", "")

        if not values["name"]:
            errors.append("Name is required.")
        if "@" not in values["email"]:
            errors.append("Enter a valid email address.")
        if len(password) < 8:
            errors.append("Password must be at least 8 characters.")

        if not errors:
            try:
                user = current_app.repository.create_user(
                    name=values["name"],
                    email=values["email"],
                    password_hash=generate_password_hash(password),
                )
            except DuplicateEmailError:
                errors.append("An account with that email already exists.")
            else:
                session.clear()
                session["user_id"] = user["id"]
                flash("Account created. Choose the job tags you want to follow.")
                return redirect(url_for("onboarding.choose_tags"))

    return render_template("auth/signup.html", errors=errors, values=values)


@auth_bp.route("/login", methods=("GET", "POST"))
def login():
    errors = []
    values = {"email": ""}

    if request.method == "POST":
        values = {"email": request.form.get("email", "").strip()}
        password = request.form.get("password", "")
        user = current_app.repository.get_user_by_email(values["email"])

        if user is None or not check_password_hash(user["password_hash"], password):
            errors.append("Invalid email or password.")
        else:
            session.clear()
            session["user_id"] = user["id"]
            return redirect(_safe_next_url(request.args.get("next")))

    return render_template("auth/login.html", errors=errors, values=values)


@auth_bp.route("/logout", methods=("POST",))
def logout():
    session.clear()
    return redirect(url_for("auth.login"))


def _safe_next_url(target: str | None) -> str:
    if target:
        parsed = urlsplit(target)
        if parsed.netloc == "" and parsed.scheme == "" and target.startswith("/"):
            return target
    return url_for("dashboard.index")
