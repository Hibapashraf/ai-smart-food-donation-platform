from datetime import datetime, timedelta

import pytest

from ml.matching import distance_km, score_match
from models import FoodDonation, Match, User, db


def registration(email="new@donor.test", role="donor", **overrides):
    data = dict(
        name="New Community Member",
        email=email,
        role=role,
        password="Testing@123",
        confirm_password="Testing@123",
        organization="The Sharing Table",
        phone="+91 90000 12345",
        location="Indiranagar, Bengaluru",
        latitude="12.9784",
        longitude="77.6408",
        categories=["Vegetables", "Fruits"],
        required_quantity="30",
        unit="kg",
        max_distance="30",
    )
    return dict(data, **overrides)


def food_data(**overrides):
    now = datetime.utcnow()
    return dict(
        dict(
            name="Test fresh produce",
            category="Vegetables",
            quantity="25",
            unit="kg",
            prepared_at=(now - timedelta(hours=1)).isoformat(timespec="minutes"),
            expires_at=(now + timedelta(hours=12)).isoformat(timespec="minutes"),
            condition="Fresh",
            diet="vegetarian",
            location="Indiranagar, Bengaluru",
            latitude="12.9784",
            longitude="77.6408",
            contact="9000012345",
            urgency="High",
            notes="Kept cool.",
        ),
        **overrides,
    )


def test_complete_registration_to_delivery_flow(app, client, login):
    response = client.post("/register", data=registration(), follow_redirects=True)
    assert response.status_code == 200
    assert b"Your account is ready" in response.data
    with app.app_context():
        user = User.query.filter_by(email="new@donor.test").one()
        assert user.password_hash != "Testing@123"
        assert user.check_password("Testing@123")
        assert user.donor is not None
    client.post("/logout")
    response = client.post(
        "/login",
        data={"email": "new@donor.test", "password": "Testing@123"},
        follow_redirects=True,
    )
    assert b"Good to see you" in response.data
    response = client.post("/donate", data=food_data())
    assert response.status_code == 302
    with app.app_context():
        donation = FoodDonation.query.filter_by(name="Test fresh produce").one()
        donation_id = donation.id
        assert donation.status == "Matched"
        assert len(donation.matches) >= 2
        scores = [m.score for m in donation.matches]
        assert scores == sorted(scores, reverse=True)
        assert all(0 <= score <= 100 for score in scores)
        assert "km away" in donation.matches[0].explanation
        assert [h.status for h in donation.history] == ["Available", "Matched"]
    login("charity")
    dashboard = client.get("/dashboard")
    assert b"Test fresh produce" in dashboard.data
    response = client.post(
        f"/donations/{donation_id}/respond",
        data={"action": "accept"},
        follow_redirects=True,
    )
    assert b"Donation accepted!" in response.data
    # No other charity can claim the accepted donation.
    other = app.test_client()
    other.post(
        "/login", data={"email": "nourish@foodconnect.demo", "password": "Demo@12345"}
    )
    response = other.post(
        f"/donations/{donation_id}/respond",
        data={"action": "accept"},
        follow_redirects=True,
    )
    assert b"no longer available" in response.data
    for status in ["Collected", "Delivered"]:
        response = client.post(
            f"/donations/{donation_id}/status",
            data={"status": status},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert f"marked as {status.lower()}".encode() in response.data
    with app.app_context():
        donation = db.session.get(FoodDonation, donation_id)
        assert donation.status == "Delivered"
        assert donation.accepted_charity.organization == "Hope Food Bank"
        assert [h.status for h in donation.history] == [
            "Available",
            "Matched",
            "Accepted",
            "Collected",
            "Delivered",
        ]
    stats = client.get("/api/stats").json
    assert stats["distributed"] == 325
    assert stats["meals"] == 650
    assert b"Test fresh produce" in client.get("/dashboard?tab=history").data
    assert b"Test fresh produce" not in client.get("/find-food").data


@pytest.mark.parametrize(
    "path",
    [
        "/",
        "/about",
        "/how-it-works",
        "/register",
        "/login",
        "/find-food",
        "/charities",
        "/donations/1",
    ],
)
def test_public_pages(client, path):
    assert client.get(path).status_code == 200


@pytest.mark.parametrize("role", ["donor", "charity", "admin"])
def test_dashboards_and_profiles(client, login, role):
    login(role)
    for path in [
        "/dashboard",
        "/profile",
        "/donations/1",
        "/dashboard?tab=all",
        "/dashboard?tab=history",
    ]:
        assert client.get(path).status_code == 200


def test_access_controls(client, login):
    assert client.get("/dashboard").status_code == 302
    assert client.post("/donate", data=food_data()).status_code == 302
    login("charity")
    assert client.get("/donate").status_code == 403
    login("donor")
    assert (
        client.post("/donations/1/respond", data={"action": "accept"}).status_code
        == 403
    )
    assert (
        client.post("/donations/1/status", data={"status": "Delivered"}).status_code
        == 403
    )
    assert client.post("/admin/users/2/toggle").status_code == 403


def test_registration_validation(app, client):
    cases = [
        registration(password="short", confirm_password="short"),
        registration(confirm_password="different"),
        registration(email="bad address"),
        registration(latitude="999"),
        registration(role="owner"),
        registration(role="admin", admin_code="incorrect"),
        registration(role="charity", categories=[]),
        registration(role="charity", required_quantity="-3"),
        registration(longitude="nan"),
    ]
    with app.app_context():
        count = User.query.count()
    for data in cases:
        response = client.post("/register", data=data)
        assert response.status_code == 200
        assert b"alert-error" in response.data
        with app.app_context():
            assert User.query.count() == count
    response = client.post(
        "/register", data=registration(email="donor@foodconnect.demo")
    )
    assert b"already exists" in response.data


def test_charity_and_invited_admin_registration(app, client):
    response = client.post(
        "/register",
        data=registration("new@charity.test", "charity"),
        follow_redirects=True,
    )
    assert b"Your account is ready" in response.data
    with app.app_context():
        charity = User.query.filter_by(email="new@charity.test").one().charity
        assert charity.categories == "Vegetables,Fruits"
        assert charity.required_quantity == 30
    # Newly registered charities can immediately discover and accept live matches.
    assert b"Fresh seasonal vegetables" in client.get("/dashboard").data
    response = client.post(
        "/donations/1/respond", data={"action": "accept"}, follow_redirects=True
    )
    assert b"Donation accepted!" in response.data
    client.post("/logout")
    response = client.post(
        "/register",
        data=registration("new@admin.test", "admin", admin_code="test-invite"),
        follow_redirects=True,
    )
    assert b"PLATFORM OVERVIEW" in response.data


def test_food_validation(app, client, login):
    login()
    with app.app_context():
        count = FoodDonation.query.count()
    invalid = [
        food_data(quantity="-1"),
        food_data(quantity="nan"),
        food_data(category="Not food"),
        food_data(latitude="91"),
        food_data(expires_at="2020-01-01T12:00"),
        food_data(urgency="Unknown"),
        food_data(
            prepared_at=(datetime.utcnow() + timedelta(days=10)).isoformat(
                timespec="minutes"
            )
        ),
        food_data(expires_at="invalid"),
        food_data(unit="tonnes"),
        food_data(diet="invalid"),
        food_data(contact=""),
    ]
    for data in invalid:
        response = client.post("/donate", data=data)
        assert b"alert-error" in response.data
        with app.app_context():
            assert FoodDonation.query.count() == count


def test_reject_donation_keeps_food_available(app, client, login):
    login("charity")
    response = client.post(
        "/donations/1/respond", data={"action": "reject"}, follow_redirects=True
    )
    assert b"Recommendation dismissed" in response.data
    with app.app_context():
        assert db.session.get(FoodDonation, 1).status == "Matched"
        charity = User.query.filter_by(email="charity@foodconnect.demo").one().charity
        assert (
            Match.query.filter_by(donation_id=1, charity_id=charity.id).one().response
            == "Rejected"
        )
    assert b"Fresh seasonal vegetables" not in client.get("/dashboard").data
    assert b"Fresh seasonal vegetables" in client.get("/find-food").data


def test_transition_guards(app, client, login):
    login("charity")
    client.post("/donations/1/respond", data={"action": "accept"})
    assert (
        b"not allowed"
        in client.post(
            "/donations/1/status", data={"status": "Delivered"}, follow_redirects=True
        ).data
    )
    with app.app_context():
        assert db.session.get(FoodDonation, 1).status == "Accepted"
    other = app.test_client()
    other.post(
        "/login", data={"email": "nourish@foodconnect.demo", "password": "Demo@12345"}
    )
    assert (
        other.post("/donations/1/status", data={"status": "Collected"}).status_code
        == 403
    )
    with app.app_context():
        db.session.get(FoodDonation, 1).expires_at = datetime.utcnow() - timedelta(
            minutes=1
        )
        db.session.commit()
    assert (
        b"not allowed"
        in client.post(
            "/donations/1/status", data={"status": "Collected"}, follow_redirects=True
        ).data
    )


def test_expiry_blocks_acceptance_and_browsing(app, client, login):
    with app.app_context():
        db.session.get(FoodDonation, 1).expires_at = datetime.utcnow() - timedelta(
            hours=1
        )
        db.session.commit()
    assert b"Fresh seasonal vegetables" not in client.get("/find-food").data
    login("charity")
    assert (
        b"no longer available"
        in client.post(
            "/donations/1/respond", data={"action": "accept"}, follow_redirects=True
        ).data
    )


def test_admin_deactivation(app, client, login):
    with app.app_context():
        donor_id = User.query.filter_by(email="donor@foodconnect.demo").one().id
        admin_id = User.query.filter_by(role="admin").one().id
    donor_client = app.test_client()
    donor_client.post(
        "/login", data={"email": "donor@foodconnect.demo", "password": "Demo@12345"}
    )
    login("admin")
    assert (
        b"deactivated"
        in client.post(f"/admin/users/{donor_id}/toggle", follow_redirects=True).data
    )
    assert donor_client.get("/dashboard").status_code == 302
    assert b"Fresh seasonal vegetables" not in client.get("/find-food").data
    assert client.post(f"/admin/users/{admin_id}/toggle").status_code == 403
    client.post(f"/admin/users/{donor_id}/toggle")
    assert b"Fresh seasonal vegetables" in client.get("/find-food").data


def test_matching_math_and_hard_constraints(app):
    assert distance_km(0, 0, 0, 0) == 0
    assert 111 < distance_km(0, 0, 0, 1) < 112
    with app.app_context():
        food = db.session.get(FoodDonation, 1)
        charity = User.query.filter_by(email="charity@foodconnect.demo").one().charity
        result = score_match(food, charity)
        assert result and 70 < result["score"] <= 100
        assert sum(result["components"].values()) == pytest.approx(
            result["score"], abs=0.1
        )
        charity.unit = "portions"
        assert score_match(food, charity)["components"]["Quantity"] == 0
        charity.latitude = 0
        assert score_match(food, charity) is None
        charity.latitude = food.latitude
        charity.vegetarian_only = True
        food.vegetarian = False
        assert score_match(food, charity) is None
        food.vegetarian = True
        charity.categories = "Dairy"
        assert score_match(food, charity) is None
        charity.categories = food.category
        food.expires_at = datetime.utcnow() + timedelta(minutes=1)
        assert score_match(food, charity) is None


def test_profile_changes_recommendations(app, client, login):
    login("charity")
    data = registration(role="charity")
    data["categories"] = ["Pantry"]
    response = client.post("/profile", data=data, follow_redirects=True)
    assert b"profile has been updated" in response.data
    with app.app_context():
        assert (
            User.query.filter_by(email="charity@foodconnect.demo")
            .one()
            .charity.categories
            == "Pantry"
        )
    assert b"Fresh seasonal vegetables" not in client.get("/dashboard").data


def test_search_filters_and_sorts(client, login):
    result = client.get("/find-food?category=Vegetables&q=seasonal")
    assert b"Fresh seasonal vegetables" in result.data
    assert b"Artisan bread" not in result.data
    assert b"No donations found" in client.get("/find-food?q=notfound").data
    assert b"No organizations found" in client.get("/charities?q=notfound").data
    assert client.get("/find-food?q=%27%20OR%201=1--").status_code == 200
    login("charity")
    for sort in ["distance", "urgency", "expiry", "newest"]:
        assert client.get("/find-food?sort=" + sort).status_code == 200
    assert client.get("/charities?sort=distance").status_code == 200


def test_contact_privacy(client, login):
    # Contact block is absent for visitors and unassigned charities.
    assert b"Donor contact" not in client.get("/donations/1").data
    login("charity")
    assert b"Donor contact" not in client.get("/donations/1").data
    client.post("/donations/1/respond", data={"action": "accept"})
    assert b"Donor contact" in client.get("/donations/1").data


def test_csrf_and_safe_headers(app, client):
    app.config["WTF_CSRF_ENABLED"] = True
    assert (
        client.post(
            "/login", data={"email": "donor@foodconnect.demo", "password": "Demo@12345"}
        ).status_code
        == 400
    )
    response = client.get("/")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"


def test_seed_is_idempotent(app):
    from database.seed import seed

    with app.app_context():
        counts = (User.query.count(), FoodDonation.query.count(), Match.query.count())
        seed()
        assert counts == (
            User.query.count(),
            FoodDonation.query.count(),
            Match.query.count(),
        )


def test_invalid_login(client):
    response = client.post(
        "/login",
        data={"email": "donor@foodconnect.demo", "password": "incorrect"},
        follow_redirects=True,
    )
    assert b"Email or password is incorrect" in response.data
    assert client.get("/dashboard").status_code == 302
    assert client.get("/does-not-exist").status_code == 404
