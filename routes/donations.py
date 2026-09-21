from datetime import datetime

from flask import (
    Blueprint,
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    url_for,
)

from ml.matching import generate_matches, score_match
from models import (
    CATEGORIES,
    UNITS,
    Charity,
    DonationStatus,
    FoodDonation,
    Match,
    User,
    db,
)
from routes.auth import coordinates, login_required

bp = Blueprint("donations", __name__)


@bp.route("/donate", methods=["GET", "POST"])
@login_required("donor")
def create():
    if request.method == "POST":
        f = request.form
        try:
            name = f.get("name", "").strip()
            category, unit, condition, urgency = [
                f.get(k, "") for k in ["category", "unit", "condition", "urgency"]
            ]
            quantity = float(f.get("quantity", "0"))
            if (
                not name
                or len(name) > 160
                or category not in CATEGORIES
                or unit not in UNITS
                or not 0 < quantity <= 100000
            ):
                raise ValueError(
                    "Enter a food name, category, unit and a quantity between 0 and 100,000."
                )
            if condition not in [
                "Fresh",
                "Sealed / packaged",
                "Freshly cooked",
            ] or urgency not in ["Normal", "High", "Urgent"]:
                raise ValueError("Select a valid food condition and urgency.")
            prepared = datetime.fromisoformat(f.get("prepared_at", ""))
            expiry = datetime.fromisoformat(f.get("expires_at", ""))
            if (
                prepared.tzinfo
                or expiry.tzinfo
                or prepared > datetime.utcnow()
                or expiry <= datetime.utcnow()
                or expiry <= prepared
            ):
                raise ValueError(
                    "Preparation cannot be in the future; expiry must be in the future and after preparation (UTC)."
                )
            lat, lon = coordinates(f)
            location, contact = (
                f.get("location", "").strip(),
                f.get("contact", "").strip(),
            )
            if not location or not contact or len(location) > 255 or len(contact) > 80:
                raise ValueError(
                    "Enter a pickup address and contact information within the field limits."
                )
            if f.get("diet") not in ["vegetarian", "non-vegetarian"]:
                raise ValueError("Please select the food type.")
            donation = FoodDonation(
                donor_id=g.user.donor.id,
                name=name,
                category=category,
                quantity=quantity,
                unit=unit,
                prepared_at=prepared,
                expires_at=expiry,
                condition=condition,
                urgency=urgency,
                vegetarian=f.get("diet") == "vegetarian",
                location=location,
                contact=contact,
                latitude=lat,
                longitude=lon,
                notes=f.get("notes", "")[:2000],
                status="Available",
            )
            db.session.add(donation)
            db.session.flush()
            db.session.add(
                DonationStatus(
                    donation_id=donation.id, status="Available", changed_by=g.user.id
                )
            )
            generate_matches(donation, g.user.id)
            db.session.commit()
            flash(
                "Your donation is live! We have checked nearby organizations for suitable matches.",
                "success",
            )
            return redirect(url_for("donations.detail", donation_id=donation.id))
        except (ValueError, TypeError) as exc:
            db.session.rollback()
            flash(str(exc), "error")
    return render_template("donate.html", profile=g.user.donor)


@bp.get("/donations/<int:donation_id>")
def detail(donation_id):
    donation = db.get_or_404(FoodDonation, donation_id)
    own = g.user and (
        g.user.role == "admin"
        or (g.user.role == "donor" and g.user.donor.id == donation.donor_id)
    )
    my_match = None
    live_score = None
    if g.user and g.user.role == "charity":
        my_match = Match.query.filter_by(
            donation_id=donation.id, charity_id=g.user.charity.id
        ).first()
        live_score = score_match(donation, g.user.charity)
    allowed_contact = own or (
        g.user
        and g.user.role == "charity"
        and donation.accepted_charity_id == g.user.charity.id
    )
    recommendations = []
    rejected_ids = {m.charity_id for m in donation.matches if m.response == "Rejected"}
    # Recompute against current profiles, including newly registered charities.
    for charity in Charity.query.join(User).filter(User.active.is_(True)).all():
        result = score_match(donation, charity)
        if result and charity.id not in rejected_ids:
            recommendations.append((charity, result))
    recommendations.sort(key=lambda pair: pair[1]["score"], reverse=True)
    return render_template(
        "detail.html",
        donation=donation,
        own=own,
        my_match=my_match,
        live_score=live_score,
        allowed_contact=allowed_contact,
        recommendations=recommendations,
    )


@bp.post("/donations/<int:donation_id>/respond")
@login_required("charity")
def respond(donation_id):
    donation = db.get_or_404(FoodDonation, donation_id)
    action = request.form.get("action")
    if action not in ["accept", "reject"]:
        abort(400)
    if (
        donation.status not in ["Available", "Matched"]
        or donation.expired
        or not donation.donor.user.active
    ):
        flash("This donation is no longer available.", "error")
        return redirect(url_for("donations.detail", donation_id=donation_id))
    result = score_match(donation, g.user.charity)
    if not result:
        flash(
            "This donation does not meet your current requirements or collection window.",
            "error",
        )
        return redirect(url_for("donations.detail", donation_id=donation_id))
    match = Match.query.filter_by(
        donation_id=donation_id, charity_id=g.user.charity.id
    ).first()
    if action == "accept":
        # Atomic conditional update: two charities cannot claim the same donation.
        updated = (
            db.session.query(FoodDonation)
            .filter(
                FoodDonation.id == donation_id,
                FoodDonation.status.in_(["Available", "Matched"]),
                FoodDonation.expires_at > datetime.utcnow(),
            )
            .update(
                {"status": "Accepted", "accepted_charity_id": g.user.charity.id},
                synchronize_session=False,
            )
        )
        if updated != 1:
            db.session.rollback()
            flash("Another organization has already accepted this donation.", "error")
            return redirect(url_for("donations.detail", donation_id=donation_id))
        if donation.status == "Available":
            db.session.add(
                DonationStatus(
                    donation_id=donation_id, status="Matched", changed_by=g.user.id
                )
            )
        db.session.add(
            DonationStatus(
                donation_id=donation_id, status="Accepted", changed_by=g.user.id
            )
        )
    if not match:
        match = Match(
            donation_id=donation_id,
            charity_id=g.user.charity.id,
            score=result["score"],
            distance=result["distance"],
            explanation=result["explanation"],
        )
        db.session.add(match)
    match.response = "Accepted" if action == "accept" else "Rejected"
    db.session.commit()
    flash(
        "Donation accepted! Coordinate pickup with the donor."
        if action == "accept"
        else "Recommendation dismissed. It remains available to other organizations.",
        "success",
    )
    return redirect(
        url_for("donations.detail", donation_id=donation_id)
        if action == "accept"
        else url_for("main.dashboard")
    )


@bp.post("/donations/<int:donation_id>/status")
@login_required()
def update_status(donation_id):
    donation = db.get_or_404(FoodDonation, donation_id)
    if not (
        g.user.role == "admin"
        or (
            g.user.role == "charity"
            and donation.accepted_charity_id == g.user.charity.id
        )
    ):
        abort(403)
    new_status = request.form.get("status")
    allowed = {"Accepted": "Collected", "Collected": "Delivered"}
    if allowed.get(donation.status) != new_status or (
        donation.expired and new_status == "Collected"
    ):
        flash(
            "That status transition is not allowed. Expired food cannot be collected.",
            "error",
        )
    else:
        old = donation.status
        updated = (
            db.session.query(FoodDonation)
            .filter_by(id=donation_id, status=old)
            .update({"status": new_status}, synchronize_session=False)
        )
        if updated == 1:
            db.session.add(
                DonationStatus(
                    donation_id=donation.id, status=new_status, changed_by=g.user.id
                )
            )
            db.session.commit()
            flash(
                f"Donation marked as {new_status.lower()}. Thank you for making a difference!",
                "success",
            )
        else:
            db.session.rollback()
            flash("The donation changed. Please refresh and try again.", "error")
    return redirect(url_for("donations.detail", donation_id=donation_id))
