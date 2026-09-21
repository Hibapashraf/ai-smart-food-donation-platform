import sqlite3
from datetime import datetime

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.engine import Engine
from werkzeug.security import check_password_hash, generate_password_hash


@event.listens_for(Engine, "connect")
def sqlite_foreign_keys(connection, record):
    if isinstance(connection, sqlite3.Connection):
        connection.execute("PRAGMA foreign_keys=ON")


db = SQLAlchemy()
CATEGORIES = ["Vegetables", "Fruits", "Bakery", "Cooked meals", "Dairy", "Pantry"]
UNITS = ["kg", "portions", "items", "litres"]
STATUSES = ["Available", "Matched", "Accepted", "Collected", "Delivered"]


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(180), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    donor = db.relationship(
        "Donor", backref="user", uselist=False, cascade="all, delete-orphan"
    )
    charity = db.relationship(
        "Charity", backref="user", uselist=False, cascade="all, delete-orphan"
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Donor(db.Model):
    __tablename__ = "donors"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True
    )
    organization = db.Column(db.String(160), nullable=False)
    phone = db.Column(db.String(40), nullable=False)
    location = db.Column(db.String(255), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)


class Charity(db.Model):
    __tablename__ = "charities"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True
    )
    organization = db.Column(db.String(160), nullable=False)
    phone = db.Column(db.String(40), nullable=False)
    location = db.Column(db.String(255), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    categories = db.Column(db.String(255), nullable=False)
    required_quantity = db.Column(db.Float, nullable=False, default=30)
    unit = db.Column(db.String(20), nullable=False, default="kg")
    vegetarian_only = db.Column(db.Boolean, nullable=False, default=False)
    max_distance = db.Column(db.Float, nullable=False, default=30)
    description = db.Column(
        db.Text, default="Working together for a hunger-free community."
    )


class FoodDonation(db.Model):
    __tablename__ = "food_donations"
    id = db.Column(db.Integer, primary_key=True)
    donor_id = db.Column(db.Integer, db.ForeignKey("donors.id"), nullable=False)
    name = db.Column(db.String(160), nullable=False)
    category = db.Column(db.String(40), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(20), nullable=False)
    prepared_at = db.Column(db.DateTime, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    condition = db.Column(db.String(40), nullable=False)
    vegetarian = db.Column(db.Boolean, nullable=False, default=True)
    location = db.Column(db.String(255), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    contact = db.Column(db.String(80), nullable=False)
    urgency = db.Column(db.String(20), nullable=False, default="Normal")
    notes = db.Column(db.Text, default="")
    status = db.Column(db.String(20), nullable=False, default="Available", index=True)
    accepted_charity_id = db.Column(
        db.Integer, db.ForeignKey("charities.id"), nullable=True
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    donor = db.relationship("Donor", backref="donations")
    accepted_charity = db.relationship("Charity")
    matches = db.relationship(
        "Match",
        backref="donation",
        cascade="all, delete-orphan",
        order_by="Match.score.desc()",
    )
    history = db.relationship(
        "DonationStatus",
        backref="donation",
        cascade="all, delete-orphan",
        order_by="DonationStatus.created_at",
    )

    @property
    def expired(self):
        return self.expires_at <= datetime.utcnow()

    @property
    def hours_left(self):
        return max(
            0, round((self.expires_at - datetime.utcnow()).total_seconds() / 3600)
        )

    @property
    def image(self):
        return {
            "Vegetables": "vegetables",
            "Fruits": "fruits",
            "Bakery": "bread",
            "Cooked meals": "meals",
            "Dairy": "dairy",
            "Pantry": "pantry",
        }.get(self.category, "vegetables") + ".jpg"


class Match(db.Model):
    __tablename__ = "matches"
    id = db.Column(db.Integer, primary_key=True)
    donation_id = db.Column(
        db.Integer, db.ForeignKey("food_donations.id"), nullable=False
    )
    charity_id = db.Column(db.Integer, db.ForeignKey("charities.id"), nullable=False)
    score = db.Column(db.Float, nullable=False)
    distance = db.Column(db.Float, nullable=False)
    explanation = db.Column(db.Text, nullable=False)
    response = db.Column(db.String(20), nullable=False, default="Pending")
    charity = db.relationship("Charity", backref="matches")
    __table_args__ = (
        db.UniqueConstraint("donation_id", "charity_id", name="uq_donation_charity"),
    )


class DonationStatus(db.Model):
    __tablename__ = "donation_status"
    id = db.Column(db.Integer, primary_key=True)
    donation_id = db.Column(
        db.Integer, db.ForeignKey("food_donations.id"), nullable=False
    )
    status = db.Column(db.String(20), nullable=False)
    changed_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class Admin(db.Model):
    __tablename__ = "admin"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False
    )
