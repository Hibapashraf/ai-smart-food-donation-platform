"""An explainable, content-based recommendation model (no opaque training step).

Hard constraints remove expired/unsafe, out-of-range, incompatible food and diets.
The remaining candidates get five weighted features, totaling 100 points.
Distances use Haversine: no network or map API is required.
"""

from datetime import datetime
from math import atan2, cos, radians, sin, sqrt

from models import Charity, DonationStatus, Match, User, db


def distance_km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    a = (
        sin((lat2 - lat1) / 2) ** 2
        + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    )
    a = min(1, max(0, a))
    return 6371 * 2 * atan2(sqrt(a), sqrt(1 - a))


def score_match(donation, charity, now=None):
    now = now or datetime.utcnow()
    hours = (donation.expires_at - now).total_seconds() / 3600
    distance = distance_km(
        donation.latitude, donation.longitude, charity.latitude, charity.longitude
    )
    # Approximate travel at 20 km/h plus 30 minutes for coordination.
    travel_hours = distance / 20 + 0.5
    if (
        hours <= travel_hours
        or distance > charity.max_distance
        or donation.category not in charity.categories.split(",")
        or (charity.vegetarian_only and not donation.vegetarian)
    ):
        return None
    location = 30 * max(0, 1 - distance / charity.max_distance)
    category = 25
    same_unit = donation.unit == charity.unit
    quantity = (
        20
        * min(donation.quantity, charity.required_quantity)
        / max(donation.quantity, charity.required_quantity)
        if same_unit
        else 0
    )
    urgency = {"Normal": 6, "High": 8, "Urgent": 10}[donation.urgency]
    expiry = 15 * min(1, (hours - travel_hours) / 4)
    components = {
        "Location": round(location, 1),
        "Category": category,
        "Quantity": round(quantity, 1),
        "Urgency": urgency,
        "Expiry": round(expiry, 1),
    }
    reason = (
        f"{distance:.1f} km away, within the {charity.max_distance:g} km collection radius. "
        f"Needs {donation.category.lower()}. "
        + (
            f"{donation.quantity:g} {donation.unit} available against a {charity.required_quantity:g} {charity.unit} requirement. "
            if same_unit
            else "Different quantity units; quantity points not awarded. "
        )
        + f"{hours:.1f} hours until expiry; estimated coordination and travel {travel_hours:.1f} hours. "
        + f"{donation.urgency} pickup priority. "
        + " · ".join(f"{k}: {v:g}" for k, v in components.items())
    )
    return {
        "score": round(sum(components.values()), 1),
        "distance": round(distance, 2),
        "explanation": reason,
        "components": components,
    }


def generate_matches(donation, actor_id):
    """Persist recommendations in the same transaction as donation creation."""
    charities = Charity.query.join(User).filter(User.active.is_(True)).all()
    for charity in charities:
        result = score_match(donation, charity)
        if result:
            db.session.add(
                Match(
                    donation_id=donation.id,
                    charity_id=charity.id,
                    score=result["score"],
                    distance=result["distance"],
                    explanation=result["explanation"],
                )
            )
    db.session.flush()
    if donation.matches and donation.status == "Available":
        donation.status = "Matched"
        db.session.add(
            DonationStatus(
                donation_id=donation.id, status="Matched", changed_by=actor_id
            )
        )
    return donation.matches
