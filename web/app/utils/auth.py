from __future__ import annotations

from functools import wraps
from typing import Callable, TypeVar

from bson import ObjectId
from bson.errors import InvalidId
from flask import abort, current_app, g, redirect, session, url_for

from ..db import get_db

F = TypeVar("F", bound=Callable[..., object])


def load_current_user() -> None:
    """
    Lightweight helper so P3 pages can work before full auth is implemented.
    P1 can replace this with their auth system, but keeping the interface stable:
    - sets g.user (dict) when session['user_id'] exists
    - otherwise leaves g.user unset
    """
    user_id = session.get("user_id")
    if not user_id:
        return
    try:
        oid = ObjectId(str(user_id))
    except (InvalidId, TypeError, ValueError):
        return
    user = get_db().users.find_one({"_id": oid})
    if user:
        g.user = user


def login_required(fn: F) -> F:
    @wraps(fn)
    def wrapper(*args, **kwargs):
        load_current_user()
        if not getattr(g, "user", None):
            # P1 will own real login. Until then, support optional dev login.
            if current_app.view_functions.get("auth.login"):
                return redirect(url_for("auth.login"))
            if current_app.view_functions.get("auth.dev_login_form"):
                return redirect(url_for("auth.dev_login_form"))
            abort(401)
        return fn(*args, **kwargs)

    return wrapper


def require_poster(gig: dict) -> None:
    user = getattr(g, "user", None)
    if not user:
        abort(401)
    if str(gig.get("poster_id")) != str(user.get("_id")):
        abort(403)
