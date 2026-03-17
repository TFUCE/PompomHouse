# PompomHouse

PompomHouse is a Django-based student housing platform prototype designed for two user roles: **tenants** and **landlords**.  
The project focuses on helping students find accommodation more clearly and helping landlords manage listings, requests, and communication in one place.

Unlike a generic rental board, this prototype includes a simple **Match Score** system that explains why a listing may suit a tenant based on profile preferences such as budget, move-in date, house rules, and hobbies.

---

## Project overview

This project was built as a prototype for a student housing finder and matcher system.  
It supports the basic housing journey from account creation to listing discovery, request approval, messaging, move-out tracking, and post-stay reviews.

There are two account roles:

- **Tenant**: can create a seeker profile, browse listings, save favourites, request contact, view match scores, send messages after approval, and leave reviews after a real stay.
- **Landlord**: can create and manage apartment listings, review incoming requests, approve or reject tenants, manage move-out status, relist properties, and message approved tenants.

---

## Main features

### 1. Dual-role authentication
- Separate **tenant** and **landlord** registration flows
- Role-based login pages
- One email address can be used once per role, so the same email can exist as both a tenant account and a landlord account

### 2. Tenant profile and preferences
Tenants can complete a seeker profile with:
- age and gender
- hobbies
- budget range
- preferred move-in date
- smoking preference
- pet preference
- personal bio and avatar

This information is used to improve the Match Score shown on listings.

### 3. Apartment listings
Landlords can:
- add a new listing
- upload a required property image
- write a short description
- edit or delete their listing
- choose between:
  - **Entire property**
  - **Several bedrooms**

Each listing includes:
- city
- address
- floor
- monthly rent
- available date
- smoking / pet rules
- image and short “about” text

### 4. Match Score
For tenant users, the system calculates a simple explainable **Match Score** for each visible listing.

The score is based on:
- budget fit
- move-in date fit
- smoking compatibility
- pet compatibility
- hobby similarity with current roommates

The score is not hidden: the system also shows short text reasons so users can understand the result.

### 5. Contact request workflow
Tenants can send a request to contact the landlord for a listing.  
Landlords can then:
- approve the request
- reject the request

This creates a clearer booking-style flow instead of open anonymous messaging.

### 6. Messaging after approval
A conversation becomes available **only after a landlord approves a request**.  
This helps keep messaging relevant and tied to a real housing interaction.

Users can:
- open their conversation list
- view a conversation detail page
- send plain text messages
- see unread message alerts in the navigation

### 7. Favourites
Tenant users can:
- save listings to favourites
- remove listings from favourites later

### 8. Move-out and relisting flow
The project also models part of the post-approval housing lifecycle:

- a tenant can request move-out
- a landlord can approve the move-out
- the stay is then moved into history
- the landlord can relist the same apartment again

This keeps past reviews attached to the same apartment record instead of creating a completely separate listing every time.

### 9. Reviews from real stays only
Only tenants with actual rental history for a listing can leave a review.  
This reduces fake or irrelevant reviews and makes the review section more believable.

### 10. Availability rules
The system includes a few practical listing rules:
- full-property listings stop accepting new tenants after approval
- room-share listings can approve multiple tenants up to the room limit
- some listings are automatically hidden from public search when they are no longer available
- hidden listings can still remain visible to relevant users involved in the stay lifecycle

---

## Tech stack

- **Python 3**
- **Django 5**
- **SQLite** for the default database
- **HTML templates** with Django Template Language
- **CSS** and small JavaScript enhancements for the frontend
- **Pillow** for image handling

---

## Project structure

```text
PompomHouse/
├── manage.py
├── requirements.txt
├── db.sqlite3
├── pompom_house/        # project settings, urls, wsgi/asgi
├── users/               # custom user model, role-based auth, profile forms/views
├── apartments/          # listings, favourites, requests, reviews, match logic
├── messaging/           # approval-based conversations and messages
├── templates/           # HTML templates
├── static/              # CSS and JavaScript
└── media/               # uploaded avatars / listing images (generated locally)
```

---

## How to run the project locally

### 1. Clone the repository
```bash
git clone <your-repository-url>
cd PompomHouse
```

### 2. Create and activate a virtual environment
**Windows**
```bash
python -m venv venv
venv\Scripts\activate
```

**macOS / Linux**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Apply migrations
```bash
python manage.py migrate
```

### 5. Create a superuser (optional)
```bash
python manage.py createsuperuser
```

### 6. Run the development server
```bash
python manage.py runserver
```

Then open:
```text
http://127.0.0.1:8000/
```

---

## Default development setup

This project currently uses:
- **SQLite** as the default database
- local **media/** storage for uploaded images
- Django **DEBUG=True** by default in local development unless changed by environment variables

Relevant environment variables supported in `settings.py` include:
- `DJANGO_SECRET_KEY`
- `DEBUG`
- `ALLOWED_HOSTS`

---

## Running tests

The repository includes automated test files for the main apps:
- `users/tests.py`
- `apartments/tests.py`
- `messaging/tests.py`

Run them with:

```bash
python manage.py test
```

You can also run a general project check with:

```bash
python manage.py check
```

---

## Example user flow

### Tenant flow
1. Register as a tenant  
2. Complete account details and housing preferences  
3. Browse public listings  
4. View Match Score explanations  
5. Save favourites  
6. Request contact for a listing  
7. Receive approval or rejection  
8. Chat with the landlord after approval  
9. Request move-out later if needed  
10. Leave a review after the stay

### Landlord flow
1. Register as a landlord  
2. Create a listing with an image  
3. Receive contact requests  
4. Approve or reject tenants  
5. Chat with approved tenants  
6. Confirm move-out  
7. Relist the apartment if it becomes available again

---

## Notes and prototype limitations

This is a **prototype project**, so some features are intentionally simplified:

- The password reset flow is simplified and does **not** use a real email verification service.
- Payments are **not** included.
- Real-time chat is **not** implemented; messaging works through normal page requests.
- Advanced search, maps, and external housing APIs are **not** included.
- The Match Score is a simple explainable scoring model, not a machine learning recommender.
- Media files are stored locally, which is suitable for development but not ideal for large-scale production deployment.

---

## Possible future improvements

- email verification and secure password recovery
- real-time messaging with WebSockets
- stronger search and filtering
- location / map integration
- better recommendation logic
- landlord dashboards with analytics
- deployment improvements such as PostgreSQL, cloud media storage, and HTTPS-ready production settings

---

## Author

Developed as a student housing platform prototype using Django.

You can replace this section with your own name, module, course, or GitHub profile before submission.
