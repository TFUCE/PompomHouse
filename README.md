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
