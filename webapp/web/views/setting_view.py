from flask import Blueprint, render_template, request, redirect, url_for, session
from flask_login import login_required

module = Blueprint("setting", __name__)


@module.route("/setting", methods=["GET", "POST"])
@login_required
def setting():
    if request.method == "POST":
        lang = request.form.get("language")
        next_url = request.form.get("next") or url_for("setting.setting")
        if lang in ["th", "en"]:
            session["lang"] = lang
        return redirect(next_url)
    return render_template("setting/setting.html")
