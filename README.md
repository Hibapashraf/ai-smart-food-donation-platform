# AI Smart Food Donation Platform

## FoodConnect AI — good food, greater good.

A complete, responsive college-project prototype connecting food donors with charities and food banks. Built with **Flask, HTML5, CSS3, vanilla JavaScript, SQLAlchemy, MySQL/PyMySQL**, and a small explainable recommendation model. Supports **SDG 2: Zero Hunger**.

The website is functional, not a static mockup. Registration, login, profile updates, donation creation, matching, charity acceptance/rejection, status changes, and admin actions persist to the database.

---

## 1. Quick start (no database server required)

Requires **Python 3.10+**. MySQL is the target deployment database; SQLite is a zero-configuration local fallback using the same models and routes.

```bash
python -m venv .venv
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1

pip install -r requirements.txt
cp .env.example .env
# Windows PowerShell: Copy-Item .env.example .env
```

Generate a secret and put it in `.env` as `SECRET_KEY`:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Leave `DATABASE_URL` commented out to use SQLite, then:

```bash
flask --app app init-db
flask --app app seed
python app.py
```

Open **http://localhost:5000**. The server binds to `0.0.0.0` and works behind preview proxies. All browser application links and requests are same-origin; no browser calls are hardcoded to localhost.

- `init-db` creates tables, without deleting data.
- `seed` inserts fictional demo data **only into an empty database**. It is safe to run again: non-empty databases are left unchanged.
- SQLite data is stored in `instance/foodconnect.db`, outside source control.
- To start without fictional accounts, run `init-db` and skip `seed`.
- No Node.js build step, API key, CDN, or external service is needed to use the app. Fonts, icons, and images are bundled.

## 2. Configure MySQL

Use **MySQL 8.0+**; the schema is also designed for MariaDB 10.6+. Start your database server before running Flask.

### A. Import the schema

```bash
mysql -u root -p < database/schema.sql
```

This creates the `foodconnect` database with UTF-8 support and the seven related tables. The schema uses `CREATE TABLE IF NOT EXISTS`; it does not drop existing tables. It does not migrate changed schemas.

### B. Create a dedicated application account

In an administrative MySQL session, replace the example password with a strong password you choose:

```sql
CREATE USER 'foodconnect_app'@'localhost' IDENTIFIED BY 'YOUR_STRONG_PASSWORD';
GRANT SELECT, INSERT, UPDATE, DELETE ON foodconnect.* TO 'foodconnect_app'@'localhost';
```

The runtime account does not need permission to administer MySQL. If you prefer to create tables with `flask init-db` rather than import the SQL file, use a separate setup account with `CREATE`, `INDEX`, and `REFERENCES` privileges.

### C. Set the connection URL

In `.env`:

```dotenv
DATABASE_URL=mysql+pymysql://foodconnect_app:YOUR_URL_ENCODED_PASSWORD@127.0.0.1:3306/foodconnect?charset=utf8mb4
```

Special characters in a connection-string password must be URL-encoded, for example `@` → `%40`. Generate the encoded value locally; do not share credentials in chat or commit `.env`.

Restart Flask after changing environment variables:

```bash
flask --app app seed
python app.py
```

Once `DATABASE_URL` is configured, **all writes, queries, profiles, matches, history, and statistics use MySQL**. SQLite is not used in parallel and data is not silently copied between databases. The seed command works with either database.

If you see `Access denied`, check the MySQL host-specific account and grants. If you see `Can't connect`, confirm MySQL is running on the configured port. If you see `Table doesn't exist`, import the schema or run `init-db` with a setup account.

## 3. Sample login credentials

Available only after running `flask --app app seed`:

| Role | Email | Password |
|---|---|---|
| Donor | `donor@foodconnect.demo` | `Demo@12345` |
| Charity / food bank | `charity@foodconnect.demo` | `Demo@12345` |
| Admin | `admin@foodconnect.demo` | `Demo@12345` |

The login page has buttons that fill these credentials; logging in still uses the normal hashed-password authentication flow.

The seed contains **3 donors, 6 charities, 1 admin, 6 fresh active donations, 8 delivered donations, and generated matching results**, centered around Bengaluru. Initial food impact is **300 kg delivered / 600 estimated meals**. Everything is fictional, including contact details. Additional seeded accounts are listed in `database/seed.py` and share the development password.

Active expiry times are relative to the moment of seeding. They expire naturally: this is intentional. If demo food has expired, add new food through the donor dashboard. Do not rerun the seed expecting it to overwrite existing data.

**Do not seed a public or production database.** Never use these credentials outside a disposable demonstration. On a clean database, admin registration requires `ADMIN_REGISTRATION_CODE` configured privately in `.env`; without a code it is disabled. Normal donor and charity registration is open.

## 4. Features and pages

### Public pages
- **Home:** editorial green-and-cream design, real database statistics, live listings, four-step introduction, benefits, SDG section, and calls to action.
- **How It Works:** four steps and a transparent explanation of match weights.
- **About:** problem, purpose, solution, measurable impact, and SDG 2 contribution.
- **Find Food:** name search, category and urgency filters, newest/urgency/expiry/distance sorting, quantity, dietary type, and expiry indicators.
- **Charity directory:** organization search, food requirements, collection radius, and nearest-first sorting.
- **Login / Register:** separate donor, charity, and invitation-only admin roles.

### Donor
- Edit personal, organization, location, and contact information.
- Publish food name/category, quantity/unit, preparation and expiry timestamps, condition, dietary type, address/coordinates, contact, urgency, and notes.
- See active, matched, all, and historical donations.
- See ranked organizations, match scores, distance, required quantities, and explanations.
- Track the five-step status and timestamped activity history.

### Charity / food bank
- Maintain food categories, required quantity and unit, dietary restriction, collection radius, and organization description.
- See current AI recommendations ranked by score.
- Accept suitable available food or dismiss a recommendation.
- Dismissal hides a recommendation for that charity; it does not remove the donation for others. A charity can reconsider and accept from the detail page while it is still available.
- Access donor contact details after acceptance; mark food collected and delivered.
- See accepted donations and delivery history.
- New charities can immediately discover and accept suitable existing donations.

### Admin
- Database-backed donor, active-charity, donation, pending, accepted/collected, completed, distributed-food, and estimated-meal totals.
- JavaScript bar chart for all five donation statuses.
- View all accounts and activate/deactivate non-admin users.
- Deactivated accounts cannot log in; existing sessions are invalidated on their next request, and their active listings/recommendations are hidden.
- Inspect all donation details, contact information, matches, and activity; advance valid accepted donations through collection/delivery.
- Admin accounts cannot be deactivated through the public management interface. Donations and activity are retained for accountability rather than deleted.

All primary pages adapt to mobile, tablet, and desktop. Forms provide native and server validation, loading feedback, success/error notifications, and empty states. Phone location permission is optional; manual coordinates work everywhere.

## 5. Explainable matching model

**Implementation:** `ml/matching.py`.

This is an **explainable content-based recommendation system** using weighted features. It is not a trained predictive ML model, and it does not claim learned accuracy. This simple approach is suitable for a college project because every result can be reproduced and explained without a training dataset.

### Eligibility first

A candidate is excluded when:
1. The food has expired or there is not enough time to arrange collection.
2. The charity does not request the food category.
3. A vegetarian-only charity is offered non-vegetarian food.
4. The charity is outside its configured collection radius.
5. The charity account is inactive.

### Five components, up to 100 points

Let `d` be straight-line distance in km, `r` the charity collection radius, `q` the donation quantity, `n` the required quantity, and `h` hours until expiry.

| Feature | Points | Rule |
|---|---:|---|
| Location | 30 | `30 × max(0, 1 − d/r)` |
| Category | 25 | 25 for a requested category; incompatible categories are excluded |
| Quantity | 20 | `20 × min(q,n)/max(q,n)` for the **same unit**, otherwise 0 |
| Urgency | 10 | Normal = 6, High = 8, Urgent = 10 |
| Expiry | 15 | `15 × min(1, (h − travel_hours)/4)` |

`travel_hours = d/20 + 0.5`: an explicit estimate of 20 km/h plus 30 minutes for coordination. Food is excluded if it cannot be collected before expiry. These assumptions are educational approximations, **not live traffic or logistics guarantees**.

Component values are rounded to one decimal; the displayed percentage is rounded for readability. Recommendations are ordered from highest to lowest. No unsupported conversions are made between kg, items, litres, and portions.

**Example:** 25 kg of vegetables, a charity requiring 30 kg, 2.4 km away within a 30 km radius, high urgency, and enough remaining freshness:

```text
Location: 27.6 + Category: 25 + Quantity: 16.7 + Urgency: 8 + Expiry: 15
= 92.3 / 100 → displayed as 92%
```

Initial match snapshots and explanations are stored in `matches` in the same transaction as the donation. Current dashboard/detail recommendations recompute scores using current time and requirements. Responses persist as Pending, Rejected, or Accepted. Acceptance checks suitability again, not just the saved score.

### Distance and Maps

Distance uses the **Haversine formula** over stored latitude/longitude coordinates. It returns approximate straight-line distance and needs no API key.

To enable Google Maps:
1. Create a Google Cloud project, configure billing if required, and enable **Maps JavaScript API**.
2. Create a browser API key restricted to the Maps JavaScript API and your exact website/preview HTTP referrers.
3. Add `GOOGLE_MAPS_API_KEY=your_key` to `.env` and restart Flask.
4. Open a donation detail page to see a map and pickup marker.

Browser keys are necessarily visible to the browser: restrict them by origin/API and set quotas. We do not require Directions, Geocoding, or Distance Matrix APIs. On missing script/network access or Google authentication failure, the coordinate preview remains available; acceptance and matching continue to work. The fallback is clearly labeled as a coordinate preview, not a geographic map.

## 6. Database explanation

`database/schema.sql` is the MySQL DDL. `models/__init__.py` defines the same schema via SQLAlchemy.

| Table | Purpose and relationships |
|---|---|
| `users` | Unique email, password hash, name, role, active flag, creation time |
| `donors` | One-to-one `user_id`; donor organization, contact, location, coordinates |
| `charities` | One-to-one `user_id`; organization, location, needed categories, quantity/unit, dietary flag, radius |
| `food_donations` | Many-to-one donor; complete food details, current status, optional accepting charity |
| `matches` | Unique donation–charity pair; initial score, distance, explanation, response |
| `donation_status` | Append-only status activity with donation, actor, and timestamp |
| `admin` | One-to-one admin account link |

Relationships:

```text
users ──1:1── donors ──1:N── food_donations ──1:N── donation_status
  │                              │
  ├─────1:1── charities ──1:N── matches ──N:1──────┘
  │                 └─────1:N── food_donations (accepted_charity_id)
  └─────1:1── admin
```

For simplicity, the small fixed charity category vocabulary is stored as a comma-separated field and validated against the application list. A larger project could normalize this into a join table. Food category/status/unit choices are validated by the application. Foreign keys, unique emails, unique profile links, and unique donation–charity matches protect relationships; food expiry and status have indexes.

All datetimes are **UTC**. Forms label this explicitly. Schema defaults are handled by the ORM; use the app/seed command to insert records rather than omitting required fields in manual SQL.

### Donation status and safety

```text
Available → Matched → Accepted → Collected → Delivered
```

- Creation records Available; finding eligible charities records Matched.
- An eligible charity can accept; first acceptance wins through an atomic conditional database update.
- If an initially unmatched donation becomes suitable for a new charity, acceptance adds the Matched step before Accepted.
- Only the assigned charity or an administrator can advance Accepted → Collected → Delivered.
- Skipping/reversing states and unassigned status changes are blocked.
- Expired donations are hidden from the marketplace, cannot be accepted, and cannot newly be marked collected. Expired is a display condition, not an additional workflow status.
- Already-collected donations can still have delivery completion recorded. The platform cannot certify safety after pickup; handlers must apply food-safety guidance.
- Contact details are private to the donor, assigned charity, and admin; organization location is public.

### Impact calculations

- Donation count: all persisted donations.
- Organizations: active charity profiles.
- Food distributed / estimated waste avoided: delivered quantities in **kg only**.
- Estimated meals: **2 meals per delivered kg + delivered portions**.
- Litres and items are not converted to kg or meals.

These are clearly labeled estimates, not verified nutritional or environmental measurements. No hardcoded totals replace database values.

## 7. Security

Implemented:
- Werkzeug salted **scrypt password hashing**.
- Signed session cookies; HttpOnly and SameSite=Lax.
- Global CSRF protection for all state-changing POST forms.
- Authentication and role checks on protected routes, with ownership checks for donation status.
- Backend bounds, category/unit/status, email, numeric, coordinate, and timestamp validation.
- Parameterized SQLAlchemy queries; no string-interpolated user SQL.
- Default Jinja HTML escaping and safe JSON chart encoding.
- Atomic donation claim and status updates to avoid duplicate claims/transitions.
- Inactive-user checks on every request.
- `nosniff` and referrer-policy headers; authenticated responses are not cached.
- Body-size limit and no arbitrary file uploads.
- Admin registration disabled unless a private invitation code is set.

Before a real deployment: replace the secret, do not seed demo accounts, enable HTTPS and `COOKIE_SECURE=true`, use a production WSGI server, add login rate limiting, email verification, password recovery, organization verification, migrations/backups, operational monitoring, and formal food-safety policies. The bundled Flask development server and open demo credentials are **not production hardened**.

## 8. Testing

### Backend suite

```bash
pytest -q
```

The suite uses temporary isolated SQLite databases and leaves your demo database untouched. **27 tests pass**, covering:
- Donor registration, hashed passwords, login, and protected dashboards.
- Charity and invitation-only admin registration.
- Donation persistence, ranked match scores, and explanatory output.
- Charity acceptance/rejection and second-claim prevention.
- Collected/delivered updates, history, and updated impact statistics.
- Input validation, expired food, restricted transitions, role access, and contact privacy.
- Admin deactivation, live profile requirements, filtering/sorting, CSRF, safe headers, and repeat-safe seeding.

You can run the same integration tests on MySQL using a **new, empty, disposable test database**:

```bash
# WARNING: the test fixture drops its tables after EACH test.
# Never point TEST_DATABASE_URL at your demo or production database.
TEST_DATABASE_URL='mysql+pymysql://test_user:encoded_password@127.0.0.1/foodconnect_test' pytest -q
```

The test account needs create/drop privileges on that dedicated test database. The test fixture imports models and creates tables before seeding.

**Verification environment:** backend and browser flows were executed using SQLite. The MySQL driver, URI support, and schema are included, but a live MySQL service was unavailable in the build sandbox; a MySQL integration run is not claimed. Google Maps without a key was exercised; a live, billed Google API was not available for testing.

### Optional real-browser test

With the Flask app running and an initially seeded **development-only** database:

```bash
npm install --no-save playwright
npx playwright install chromium
node tests/browser_smoke.cjs
```

If the machine needs browser system libraries, use `npx playwright install --with-deps chromium` with the appropriate local permissions. Node is used only for this optional test, never for running the website.

`BASE_URL` can target a different local test server. The script creates two development accounts and a donation, exercises real CSRF-protected forms and JavaScript, then tests acceptance through delivery and admin charts. **It leaves those test records in the configured development database.** Screenshots go into ignored `test-results/`.

The browser test passed at **1440px desktop and 390px mobile** with no JavaScript errors or horizontal page overflow. It covers navigation, donor and charity signup, donation publication, matches, acceptance, collection, delivery, history, and admin charts. In the sandbox only, a packaged Chromium binary was used because standard browser download endpoints were unavailable.

### Suggested manual presentation flow

1. Show the homepage and live statistics.
2. Register a donor near Bengaluru (e.g. `12.9784, 77.6408`) or sign in with the donor demo.
3. Donate 25 kg of vegetarian vegetables, prepared earlier, expiring 12 hours from now (UTC).
4. Open the best-match explanation and explain the five weighted features.
5. Log out; sign in as `charity@foodconnect.demo`.
6. Open the new donation and accept it. Show the disclosed contact details.
7. Mark it collected, then delivered.
8. Open donation history; show that the food is no longer in available listings.
9. Log in as admin to show the updated chart and totals.
10. Return to the homepage to show updated food/meal impact.

## 9. Project structure

```text
ai-smart-food-donation-platform/
├── app.py                     # Flask factory, middleware, error pages, CLI
├── config.py                  # Environment-driven settings
├── requirements.txt           # Python dependencies
├── .env.example               # MySQL/secret/Maps configuration template
├── models/
│   └── __init__.py            # Seven ORM models and fixed vocabularies
├── routes/
│   ├── auth.py                # Registration, sessions, profiles, role guards
│   ├── main.py                # Public pages, search, dashboards, admin, stats
│   └── donations.py           # Creation, detail, acceptance/rejection, status
├── ml/
│   └── matching.py            # Haversine distance and weighted recommender
├── database/
│   ├── schema.sql             # Importable MySQL schema and relationships
│   └── seed.py                # Fictional, relative-time sample data
├── templates/
│   ├── base.html              # Shared navigation, footer, icon symbols
│   ├── components.html        # Food cards, progress, empty states, CSRF
│   ├── home.html, about.html, how.html
│   ├── auth.html, profile.html, profile_fields.html
│   ├── donate.html, detail.html, dashboard.html
│   ├── find_food.html, charities.html, error.html
├── static/
│   ├── css/style.css          # Responsive design and local font definitions
│   ├── js/app.js              # Form UX, geolocation, menu, chart, notifications
│   ├── fonts/                 # Self-hosted fonts and OFL licenses
│   └── images/                # Illustrative imagery and SVG avatars/favicon
├── tests/
│   ├── conftest.py            # Isolated test DB and fixtures
│   ├── test_platform.py       # Functional and security integration tests
│   └── browser_smoke.cjs      # Optional browser end-to-end test
└── instance/                  # Local SQLite data (generated, ignored)
```

## 10. Presentation / viva summary

> “Our project, FoodConnect AI, reduces food waste by connecting donors with nearby charities. Donors register and publish surplus food, including quantity, expiry, and pickup location. A content-based recommendation model checks eligibility and calculates a match score from distance, food compatibility, quantity, urgency, and expiry suitability. Each score is explained, making the system transparent. Charities accept food and track its journey through collection and delivery. Flask handles application logic, MySQL stores linked records, and responsive HTML, CSS, and JavaScript provide the interface. Haversine distance keeps matching functional without Google Maps. Role checks, password hashing, CSRF protection, and parameterized queries protect the system. Our goal is practical local action toward SDG 2: Zero Hunger.”

**Why this model?** It needs no private training dataset, is easy to audit, has understandable limitations, and reflects real collection constraints.

**What makes it AI-based?** It is a content-based recommendation/ranking system using structured features. It is intentionally not presented as a neural network or a trained model.

**Why MySQL?** Relational links preserve users, food, recommendations, accepting organizations, and the donation timeline, while unique keys and transactions protect consistency.

**Future scope:** verified organizations, allergen/temperature handling, push notifications, delivery-volunteer coordination, route-based travel times, unit-standardized demand, donation photos, cancellation/dispute workflows, and learning weights from consented historical outcomes.
