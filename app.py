from datetime import datetime
from pathlib import Path

import click
from flask import Flask, g, render_template, session
from flask_wtf.csrf import CSRFError, CSRFProtect

from config import Config
from models import CATEGORIES, STATUSES, UNITS, User, db

csrf = CSRFProtect()


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    Path(app.instance_path).mkdir(exist_ok=True)
    db.init_app(app)
    csrf.init_app(app)
    from routes import auth, donations, main

    app.register_blueprint(auth.bp)
    app.register_blueprint(main.bp)
    app.register_blueprint(donations.bp)

    @app.before_request
    def load_user():
        user = (
            db.session.get(User, session.get("user_id"))
            if session.get("user_id")
            else None
        )
        g.user = user if user and user.active else None
        if user and not user.active:
            session.clear()

    @app.context_processor
    def shared():
        return dict(
            categories=CATEGORIES,
            units=UNITS,
            statuses=STATUSES,
            current_year=datetime.utcnow().year,
        )

    @app.after_request
    def headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if g.get("user"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(403)
    @app.errorhandler(404)
    @app.errorhandler(400)
    @app.errorhandler(413)
    def error(error):
        return render_template(
            "error.html",
            code=error.code,
            message={
                403: "This page is not available for your account role.",
                404: "We couldn’t find that page.",
                400: "The request could not be completed. Please try again.",
                413: "The submitted content is too large.",
            }.get(error.code),
        ), error.code

    @app.errorhandler(CSRFError)
    def csrf_error(error):
        return render_template(
            "error.html",
            code=400,
            message="Your form session expired. Reload the page and try again.",
        ), 400

    @app.cli.command("init-db")
    def init_db():
        """Create the schema in the configured MySQL or SQLite database."""
        db.create_all()
        click.echo("Database tables created.")

    @app.cli.command("seed")
    def seed_db():
        """Insert development-only demo accounts and sample donations once."""
        from database.seed import seed

        db.create_all()
        seed()
        click.echo("Demo data is ready. See README for development login credentials.")

    return app


app = create_app()
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
