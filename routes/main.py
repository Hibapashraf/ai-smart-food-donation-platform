from datetime import datetime

from flask import (
    Blueprint,
    abort,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

from ml.matching import distance_km, score_match
from models import (
    STATUSES,
    Charity,
    Donor,
    FoodDonation,
    Match,
    User,
    db,
)
from routes.auth import login_required

bp = Blueprint("main", __name__)


def impact_stats():
    delivered = FoodDonation.query.filter_by(status="Delivered").all()
    kg = sum(d.quantity for d in delivered if d.unit == "kg")
    portions = sum(d.quantity for d in delivered if d.unit == "portions")
    return dict(
        donations=FoodDonation.query.count(),
        organizations=Charity.query.join(User).filter(User.active.is_(True)).count(),
        distributed=round(kg),
        meals=int(kg * 2 + portions),
        donors=Donor.query.count(),
        accepted=FoodDonation.query.filter(
            FoodDonation.status.in_(["Accepted", "Collected"])
        ).count(),
        pending=FoodDonation.query.filter(
            FoodDonation.status.in_(["Available", "Matched"])
        ).count(),
        completed=len(delivered),
    )


@bp.get("/")
def home():
    donations = (
        FoodDonation.query.join(Donor)
        .join(User)
        .filter(
            User.active.is_(True),
            FoodDonation.status.in_(["Available", "Matched"]),
            FoodDonation.expires_at > datetime.utcnow(),
        )
        .order_by(FoodDonation.created_at.desc())
        .limit(3)
        .all()
    )
    return render_template("home.html", stats=impact_stats(), donations=donations)


@bp.get("/about")
def about():
    return render_template("about.html", stats=impact_stats())


@bp.get("/how-it-works")
def how_it_works():
    return render_template("how.html")


@bp.get("/find-food")
def find_food():
    query = (
        FoodDonation.query.join(Donor)
        .join(User)
        .filter(
            User.active.is_(True),
            FoodDonation.status.in_(["Available", "Matched"]),
            FoodDonation.expires_at > datetime.utcnow(),
        )
    )
    search = request.args.get("q", "").strip()[:100]
    category = request.args.get("category", "")
    urgency = request.args.get("urgency", "")
    sort = request.args.get("sort", "newest")
    if search:
        query = query.filter(
            FoodDonation.name.ilike(
                "%" + search.replace("%", "").replace("_", "") + "%"
            )
        )
    if category:
        query = query.filter(FoodDonation.category == category)
    if urgency:
        query = query.filter(FoodDonation.urgency == urgency)
    donations = query.order_by(FoodDonation.created_at.desc()).all()
    profile = (g.user.charity or g.user.donor) if g.user else None
    distances = (
        {
            d.id: round(
                distance_km(
                    profile.latitude, profile.longitude, d.latitude, d.longitude
                ),
                1,
            )
            for d in donations
        }
        if profile
        else {}
    )
    if sort == "distance" and profile:
        donations.sort(key=lambda d: distances[d.id])
    elif sort == "urgency":
        donations.sort(
            key=lambda d: (
                {"Urgent": 0, "High": 1, "Normal": 2}[d.urgency],
                d.expires_at,
            )
        )
    elif sort == "expiry":
        donations.sort(key=lambda d: d.expires_at)
    return render_template("find_food.html", donations=donations, distances=distances)


@bp.get("/charities")
def charities():
    q = request.args.get("q", "").strip()[:100]
    query = Charity.query.join(User).filter(User.active.is_(True))
    if q:
        query = query.filter(
            Charity.organization.ilike("%" + q.replace("%", "").replace("_", "") + "%")
        )
    category = request.args.get("category", "")
    organizations = query.all()
    if category:
        organizations = [
            c for c in organizations if category in c.categories.split(",")
        ]
    profile = (g.user.donor or g.user.charity) if g.user else None
    distances = (
        {
            c.id: round(
                distance_km(
                    profile.latitude, profile.longitude, c.latitude, c.longitude
                ),
                1,
            )
            for c in organizations
        }
        if profile
        else {}
    )
    if request.args.get("sort") == "distance" and profile:
        organizations.sort(key=lambda c: distances[c.id])
    return render_template(
        "charities.html", charities=organizations, distances=distances
    )


@bp.get("/dashboard")
@login_required()
def dashboard():
    tab = request.args.get("tab", "active")
    recommendations = []
    users = []
    if g.user.role == "donor":
        all_donations = (
            FoodDonation.query.filter_by(donor_id=g.user.donor.id)
            .order_by(FoodDonation.created_at.desc())
            .all()
        )
    elif g.user.role == "charity":
        all_donations = (
            FoodDonation.query.filter_by(accepted_charity_id=g.user.charity.id)
            .order_by(FoodDonation.created_at.desc())
            .all()
        )
        available = (
            FoodDonation.query.join(Donor)
            .join(User)
            .filter(
                User.active.is_(True),
                FoodDonation.status.in_(["Available", "Matched"]),
                FoodDonation.expires_at > datetime.utcnow(),
            )
            .all()
        )
        for donation in available:
            rejected = Match.query.filter_by(
                donation_id=donation.id,
                charity_id=g.user.charity.id,
                response="Rejected",
            ).first()
            result = score_match(donation, g.user.charity)
            if result and not rejected:
                recommendations.append((donation, result))
        recommendations.sort(key=lambda x: x[1]["score"], reverse=True)
    else:
        all_donations = FoodDonation.query.order_by(
            FoodDonation.created_at.desc()
        ).all()
        users = User.query.order_by(User.created_at.desc()).all()
    counts = {
        "total": len(all_donations),
        "active": sum(d.status != "Delivered" and not d.expired for d in all_donations),
        "completed": sum(d.status == "Delivered" for d in all_donations),
        "matched": sum(d.status == "Matched" for d in all_donations),
    }
    if tab == "history":
        donations = [d for d in all_donations if d.status == "Delivered" or d.expired]
    elif tab == "matched":
        donations = [d for d in all_donations if d.status == "Matched"]
    elif tab == "all" or g.user.role == "admin":
        donations = all_donations
    else:
        donations = [
            d for d in all_donations if d.status != "Delivered" and not d.expired
        ]
    chart = {s: sum(d.status == s for d in all_donations) for s in STATUSES}
    return render_template(
        "dashboard.html",
        donations=donations,
        counts=counts,
        recommendations=recommendations,
        stats=impact_stats(),
        users=users,
        tab=tab,
        chart=chart,
    )


@bp.post("/admin/users/<int:user_id>/toggle")
@login_required("admin")
def toggle_user(user_id):
    user = db.get_or_404(User, user_id)
    if user.role == "admin":
        abort(403)
    user.active = not user.active
    db.session.commit()
    flash(
        f"{user.name} has been {'activated' if user.active else 'deactivated'}.",
        "success",
    )
    return redirect(url_for("main.dashboard", tab="users"))


@bp.get("/api/stats")
def stats_api():
    return jsonify(impact_stats())
