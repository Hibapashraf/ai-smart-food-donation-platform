"""Opt-in, fictional Bengaluru demo data. Never run against production."""

from datetime import datetime, timedelta

from ml.matching import generate_matches
from models import Admin, Charity, DonationStatus, Donor, FoodDonation, User, db


def seed():
    if User.query.first():
        print("Database is not empty; seed skipped to preserve existing data.")
        return
    now = datetime.utcnow()

    def user(name, email, role):
        u = User(name=name, email=email, role=role)
        u.set_password("Demo@12345")
        db.session.add(u)
        db.session.flush()
        return u

    donor_specs = [
        (
            "Ananya Sharma",
            "donor@foodconnect.demo",
            "Green Basket Market",
            "Indiranagar, Bengaluru",
            12.9784,
            77.6408,
        ),
        (
            "Rahul Mehta",
            "bakery@foodconnect.demo",
            "The Good Loaf Bakery",
            "Domlur, Bengaluru",
            12.9609,
            77.6387,
        ),
        (
            "Priya Nair",
            "kitchen@foodconnect.demo",
            "Harvest Community Kitchen",
            "Koramangala, Bengaluru",
            12.9352,
            77.6245,
        ),
    ]
    donors = []
    for name, email, organization, location, lat, lon in donor_specs:
        u = user(name, email, "donor")
        d = Donor(
            user_id=u.id,
            organization=organization,
            phone="+91 90000 00000",
            location=location,
            latitude=lat,
            longitude=lon,
        )
        db.session.add(d)
        donors.append(d)
    charity_specs = [
        (
            "Hope Food Bank",
            "charity@foodconnect.demo",
            "Ulsoor, Bengaluru",
            12.981,
            77.625,
            "Vegetables,Fruits,Bakery,Pantry",
            30,
            "kg",
            False,
        ),
        (
            "Nourish Bengaluru",
            "nourish@foodconnect.demo",
            "Indiranagar, Bengaluru",
            12.973,
            77.647,
            "Vegetables,Fruits,Dairy,Pantry",
            25,
            "kg",
            True,
        ),
        (
            "A Plate of Hope",
            "plate@foodconnect.demo",
            "Koramangala, Bengaluru",
            12.941,
            77.621,
            "Cooked meals,Bakery",
            60,
            "portions",
            False,
        ),
        (
            "Robin Hood Community",
            "robin@foodconnect.demo",
            "MG Road, Bengaluru",
            12.975,
            77.610,
            "Vegetables,Fruits,Cooked meals,Bakery,Dairy,Pantry",
            40,
            "kg",
            False,
        ),
        (
            "The Kindness Kitchen",
            "kindness@foodconnect.demo",
            "HSR Layout, Bengaluru",
            12.914,
            77.638,
            "Cooked meals,Vegetables,Pantry",
            50,
            "portions",
            True,
        ),
        (
            "Community Care Collective",
            "care@foodconnect.demo",
            "Richmond Town, Bengaluru",
            12.962,
            77.600,
            "Vegetables,Fruits,Bakery,Dairy,Pantry",
            20,
            "kg",
            False,
        ),
    ]
    charities = []
    for org, email, location, lat, lon, categories, qty, unit, veg in charity_specs:
        u = user(org, email, "charity")
        c = Charity(
            user_id=u.id,
            organization=org,
            phone="+91 90000 00001",
            location=location,
            latitude=lat,
            longitude=lon,
            categories=categories,
            required_quantity=qty,
            unit=unit,
            vegetarian_only=veg,
            max_distance=25,
            description="Connecting good food with our neighbors in need. Together, every meal makes a difference.",
        )
        db.session.add(c)
        charities.append(c)
    admin = user("Platform Administrator", "admin@foodconnect.demo", "admin")
    db.session.add(Admin(user_id=admin.id))
    db.session.flush()
    foods = [
        ("Fresh seasonal vegetables", "Vegetables", 25, "kg", 0, 18, "High"),
        ("Artisan bread & pastries", "Bakery", 40, "items", 1, 10, "Urgent"),
        ("Wholesome vegetarian meals", "Cooked meals", 60, "portions", 2, 6, "Urgent"),
        ("Fresh orchard fruits", "Fruits", 20, "kg", 0, 36, "Normal"),
        ("Sealed milk & yogurt", "Dairy", 15, "litres", 0, 30, "High"),
        ("Rice, lentils & pantry essentials", "Pantry", 50, "kg", 2, 120, "Normal"),
    ]
    for i, (name, cat, qty, unit, donor_index, hours, urgency) in enumerate(foods):
        d = donors[donor_index]
        food = FoodDonation(
            donor_id=d.id,
            name=name,
            category=cat,
            quantity=qty,
            unit=unit,
            prepared_at=now - timedelta(hours=2),
            expires_at=now + timedelta(hours=hours),
            condition="Freshly cooked" if cat == "Cooked meals" else "Fresh",
            vegetarian=True,
            location=d.location,
            latitude=d.latitude,
            longitude=d.longitude,
            contact=d.phone,
            urgency=urgency,
            notes="Freshly prepared and carefully stored. Please bring reusable containers for pickup.",
            status="Available",
            created_at=now - timedelta(minutes=i * 12),
        )
        db.session.add(food)
        db.session.flush()
        db.session.add(
            DonationStatus(
                donation_id=food.id, status="Available", changed_by=d.user_id
            )
        )
        generate_matches(food, d.user_id)
    for i in range(8):
        d = donors[i % 3]
        c = charities[i % len(charities)]
        when = now - timedelta(days=i + 1)
        food = FoodDonation(
            donor_id=d.id,
            name=["Seasonal produce box", "Community lunch", "Fresh fruit box"][i % 3],
            category="Vegetables",
            quantity=20 + i * 5,
            unit="kg",
            prepared_at=when - timedelta(hours=2),
            expires_at=when + timedelta(hours=18),
            condition="Fresh",
            vegetarian=True,
            location=d.location,
            latitude=d.latitude,
            longitude=d.longitude,
            contact=d.phone,
            urgency="Normal",
            status="Delivered",
            accepted_charity_id=c.id,
            created_at=when,
        )
        db.session.add(food)
        db.session.flush()
        for j, status in enumerate(
            ["Available", "Matched", "Accepted", "Collected", "Delivered"]
        ):
            db.session.add(
                DonationStatus(
                    donation_id=food.id,
                    status=status,
                    changed_by=d.user_id if j < 2 else c.user_id,
                    created_at=when + timedelta(minutes=j * 30),
                )
            )
    db.session.commit()
