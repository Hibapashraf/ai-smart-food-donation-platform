import hmac
import re
from functools import wraps

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from sqlalchemy.exc import IntegrityError

from models import CATEGORIES, UNITS, Admin, Charity, Donor, User, db

bp = Blueprint("auth", __name__)


def login_required(role=None):
    def decorator(func):
        @wraps(func)
        def wrapped(*args, **kwargs):
            if not g.user:
                flash("Please sign in to continue.", "info")
                return redirect(url_for("auth.login"))
            if role and g.user.role != role:
                abort(403)
            return func(*args, **kwargs)

        return wrapped

    return decorator


def coordinates(form):
    lat, lon = float(form.get("latitude", "")), float(form.get("longitude", ""))
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError(
            "Enter valid latitude (-90 to 90) and longitude (-180 to 180)."
        )
    return lat, lon


def profile_values(form):
    lat, lon = coordinates(form)
    values = {k: form.get(k, "").strip() for k in ["organization", "phone", "location"]}
    if (
        not all(values.values())
        or len(values["organization"]) > 160
        or len(values["phone"]) > 40
        or len(values["location"]) > 255
    ):
        raise ValueError(
            "Enter an organization, contact number and pickup address within the field limits."
        )
    return dict(**values, latitude=lat, longitude=lon)


def charity_values(form):
    categories = form.getlist("categories")
    quantity = float(form.get("required_quantity", "0"))
    radius = float(form.get("max_distance", "30"))
    unit = form.get("unit")
    if (
        not categories
        or not set(categories).issubset(CATEGORIES)
        or not 0 < quantity <= 100000
        or not 0 < radius <= 500
        or unit not in UNITS
    ):
        raise ValueError(
            "Select food categories, a valid unit, a positive quantity and a collection radius up to 500 km."
        )
    return dict(
        categories=",".join(categories),
        required_quantity=quantity,
        unit=unit,
        max_distance=radius,
        vegetarian_only=form.get("vegetarian_only") == "on",
        description=form.get("description", "")[:1000],
    )


@bp.route("/register", methods=["GET", "POST"])
def register():
    if g.user:
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        f = request.form
        try:
            role, name, email, password = [
                f.get(k, "").strip() for k in ["role", "name", "email", "password"]
            ]
            if role not in ["donor", "charity", "admin"]:
                raise ValueError("Please choose a valid account type.")
            if (
                not name
                or len(name) > 120
                or len(email) > 180
                or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email)
            ):
                raise ValueError("Enter your name and a valid email address.")
            if (
                len(password) < 8
                or len(password) > 128
                or password != f.get("confirm_password")
            ):
                raise ValueError("Passwords must match and contain 8–128 characters.")
            if role == "admin":
                code = current_app.config["ADMIN_REGISTRATION_CODE"]
                if not code or not hmac.compare_digest(code, f.get("admin_code", "")):
                    raise ValueError(
                        "A valid administrator invitation code is required."
                    )
            user = User(name=name, email=email.lower(), role=role)
            user.set_password(password)
            db.session.add(user)
            db.session.flush()
            if role == "donor":
                db.session.add(Donor(user_id=user.id, **profile_values(f)))
            elif role == "charity":
                db.session.add(
                    Charity(user_id=user.id, **profile_values(f), **charity_values(f))
                )
            else:
                db.session.add(Admin(user_id=user.id))
            db.session.commit()
            session.clear()
            session["user_id"] = user.id
            flash("Welcome to FoodConnect! Your account is ready.", "success")
            return redirect(url_for("main.dashboard"))
        except (ValueError, TypeError) as exc:
            db.session.rollback()
            flash(str(exc) if str(exc) else "Please check your form fields.", "error")
        except IntegrityError:
            db.session.rollback()
            flash("An account with that email already exists.", "error")
    return render_template("auth.html", registering=True)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        user = User.query.filter_by(
            email=request.form.get("email", "").strip().lower()
        ).first()
        if (
            user
            and user.active
            and user.check_password(request.form.get("password", ""))
        ):
            session.clear()
            session["user_id"] = user.id
            flash(f"Welcome back, {user.name.split()[0]}!", "success")
            return redirect(url_for("main.dashboard"))
        flash("Email or password is incorrect, or this account is inactive.", "error")
    return render_template("auth.html", registering=False)


@bp.post("/logout")
def logout():
    session.clear()
    flash("You have been signed out.", "info")
    return redirect(url_for("main.home"))


@bp.route("/profile", methods=["GET", "POST"])
@login_required()
def profile():
    profile = g.user.donor or g.user.charity
    if request.method == "POST":
        try:
            name = request.form.get("name", "").strip()
            if not name or len(name) > 120:
                raise ValueError("Please enter a name up to 120 characters.")
            g.user.name = name
            if profile:
                values = profile_values(request.form)
                if g.user.role == "charity":
                    values.update(charity_values(request.form))
                for key, value in values.items():
                    setattr(profile, key, value)
            db.session.commit()
            flash(
                "Your profile has been updated. New recommendations use your current requirements.",
                "success",
            )
            return redirect(url_for("auth.profile"))
        except (ValueError, TypeError) as exc:
            db.session.rollback()
            flash(str(exc), "error")
    return render_template("profile.html", profile=profile)
