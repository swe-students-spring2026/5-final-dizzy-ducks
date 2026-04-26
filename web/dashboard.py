from flask import Blueprint, render_template

from web.auth import login_required

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
@login_required
def index():
    return render_template("dashboard.html", gigs=[], selected_tags=[], search="")
