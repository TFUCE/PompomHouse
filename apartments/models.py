from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import Truncator


class ListingMode(models.TextChoices):
    ENTIRE = 'entire', 'Entire property'
    ROOMS = 'rooms', 'Several bedrooms'


class ContactStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    APPROVED = 'approved', 'Approved'
    LEAVE_PENDING = 'leave_pending', 'Move-out requested'
    LEFT = 'left', 'Moved out'
    REJECTED = 'rejected', 'Rejected'


class Apartment(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='apartments')

    # These two groups are reused in several places, so it is easier to keep
    # the booking / review rules consistent from one spot.
    CURRENT_TENANT_STATUSES = (ContactStatus.APPROVED, ContactStatus.LEAVE_PENDING)
    REVIEWABLE_TENANT_STATUSES = (ContactStatus.APPROVED, ContactStatus.LEAVE_PENDING, ContactStatus.LEFT)
    city = models.CharField(max_length=100)
    address = models.CharField(max_length=255)
    floor = models.PositiveIntegerField(blank=True, null=True)
    rent_price = models.PositiveIntegerField()
    room_count = models.PositiveIntegerField(default=1)
    available_from = models.DateField()
    smoking_allowed = models.BooleanField(default=False)
    pets_allowed = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    listing_mode = models.CharField(max_length=20, choices=ListingMode.choices, default=ListingMode.ENTIRE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.display_title

    @property
    def display_title(self):
        city = self.city.strip() if self.city else ''
        address = self.address.strip() if self.address else ''
        if city and address:
            return f'{city} · {address}'
        return city or address or 'Apartment listing'

    @property
    def short_address(self):
        return Truncator(self.display_title).chars(48)

    @property
    def primary_image(self):
        return self.images.first()

    @property
    def about_text(self):
        primary = self.primary_image
        if primary and primary.about:
            return primary.about
        return 'No about details provided yet.'

    @property
    def approved_requests(self):
        # Use one queryset for current tenants so detail pages and cards do not
        # keep rebuilding the same joins.
        return (
            self.contact_requests.filter(status__in=self.CURRENT_TENANT_STATUSES)
            .select_related('tenant', 'tenant__seeker_profile')
            .prefetch_related('tenant__hobbies')
        )

    @property
    def approved_requests_count(self):
        return self.contact_requests.filter(status__in=self.CURRENT_TENANT_STATUSES).count()

    @property
    def approved_roommate_cards(self):
        # The template only needs a light summary for each current roommate.
        return [
            {
                'tenant': item.tenant,
                'profile': getattr(item.tenant, 'seeker_profile', None),
                'hobbies': list(item.tenant.hobbies.all()[:4]),
                'approved_at': item.approved_at,
            }
            for item in self.approved_requests
        ]

    @property
    def is_room_share(self):
        return self.listing_mode == ListingMode.ROOMS

    @property
    def is_fully_rented(self):
        # Whole-property listings stop after one approved tenant. Room-share
        # listings can keep taking approved tenants until the room limit is hit.
        if not self.is_room_share:
            return self.contact_requests.filter(status__in=self.CURRENT_TENANT_STATUSES).exists()

        total_rooms = self.room_count or 0
        return total_rooms > 0 and self.approved_requests_count >= total_rooms

    @property
    def first_approved_at(self):
        approved = self.contact_requests.filter(status__in=self.CURRENT_TENANT_STATUSES)
        approved = approved.order_by('approved_at', 'created_at').first()
        return approved.approved_at if approved else None

    @property
    def should_auto_unlist(self):
        # Whole-property listings automatically disappear a day after approval.
        # That still leaves the detail page available to people already involved.
        if self.is_room_share:
            return False

        first_approved = self.first_approved_at
        return bool(first_approved and timezone.now() >= first_approved + timedelta(days=1))

    @property
    def public_visible(self):
        # Public search results only show active, not-yet-full listings.
        return self.is_active and not self.should_auto_unlist and not self.is_fully_rented

    @property
    def status_label(self):
        return 'Rented' if self.is_fully_rented else 'Available'

    @property
    def remaining_rooms(self):
        if not self.is_room_share:
            return 0
        total_rooms = self.room_count or 0
        return max(0, total_rooms - self.approved_requests_count)

    @property
    def review_count(self):
        return self.reviews.count()

    @property
    def average_rating(self):
        value = self.reviews.aggregate(avg=models.Avg('rating'))['avg']
        if value is None:
            return None
        return round(value, 1)

    def review_summary(self):
        average = self.average_rating
        if average is None:
            return 'No reviews yet'
        label = 'review' if self.review_count == 1 else 'reviews'
        return f'{average}/5 ({self.review_count} {label})'

    def has_approved_contact(self, user):
        if not getattr(user, 'is_authenticated', False) or not getattr(user, 'is_tenant', False):
            return False

        return self.contact_requests.filter(tenant=user, status__in=self.CURRENT_TENANT_STATUSES).exists()

    def has_rental_history(self, user):
        # Reviews stay available after move-out, so past tenants still count.
        if not getattr(user, 'is_authenticated', False) or not getattr(user, 'is_tenant', False):
            return False

        return self.contact_requests.filter(tenant=user, status__in=self.REVIEWABLE_TENANT_STATUSES).exists()

    def has_review_from(self, user):
        if not getattr(user, 'is_authenticated', False):
            return False
        return self.reviews.filter(reviewer=user).exists()

    def can_view_detail(self, user):
        # Once a listing is no longer public, keep the detail page available for
        # people who are already part of the listing lifecycle.
        if self.public_visible:
            return True

        if not getattr(user, 'is_authenticated', False):
            return False

        if user == self.owner:
            return True

        return self.has_rental_history(user) or self.has_review_from(user)

    def can_review(self, user):
        # Existing reviewers can come back and edit what they wrote later.
        return self.has_rental_history(user) or self.has_review_from(user)

    @property
    def can_relist(self):
        return not self.is_active and not self.is_fully_rented

    def refresh_availability(self, save=True):
        # Some availability rules depend on time, so this is called before pages
        # render instead of only when someone edits the listing.
        if self.should_auto_unlist and self.is_active:
            self.is_active = False
            if save:
                self.save(update_fields=['is_active'])
            return True
        return False


class ApartmentImage(models.Model):
    apartment = models.ForeignKey(Apartment, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='listings/')
    about = models.CharField(max_length=150, blank=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f'Image for apartment {self.apartment_id}'


class Match(models.Model):
    tenant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tenant_matches')
    apartment = models.ForeignKey(Apartment, on_delete=models.CASCADE, related_name='apartment_matches')
    score = models.PositiveIntegerField(default=0)
    reasons = models.JSONField(default=list, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-score', '-updated_at']
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'apartment'], name='unique_tenant_apartment_match'),
        ]

    def __str__(self):
        return f'{self.tenant.email} ↔ {self.apartment_id}: {self.score}'


class ContactRequest(models.Model):
    # One row here covers the full lifecycle: request, approval, move-out, and
    # past stay history. Keeping it in one model keeps the project smaller.
    apartment = models.ForeignKey(Apartment, on_delete=models.CASCADE, related_name='contact_requests')
    tenant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='contact_requests')
    status = models.CharField(max_length=20, choices=ContactStatus.choices, default=ContactStatus.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(blank=True, null=True)
    landlord_seen = models.BooleanField(default=False)
    tenant_seen = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['apartment', 'tenant'], name='unique_apartment_tenant_request'),
        ]

    def __str__(self):
        return f'{self.tenant.email} → {self.apartment.display_title} ({self.status})'

    @property
    def has_conversation(self):
        return hasattr(self, 'conversation')


class Favourite(models.Model):
    tenant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='favourites')
    apartment = models.ForeignKey(Apartment, on_delete=models.CASCADE, related_name='favourites')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'apartment'], name='unique_tenant_apartment_favourite'),
        ]

    def __str__(self):
        return f'{self.tenant.email} ♥ {self.apartment.display_title}'


class Review(models.Model):
    RATING_CHOICES = [(score, f'{score} / 5') for score in range(1, 6)]

    apartment = models.ForeignKey(Apartment, on_delete=models.CASCADE, related_name='reviews')
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='apartment_reviews')
    rating = models.PositiveSmallIntegerField(choices=RATING_CHOICES)
    comment = models.TextField(max_length=800)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at', '-created_at']
        constraints = [
            models.UniqueConstraint(fields=['apartment', 'reviewer'], name='unique_apartment_reviewer_review'),
        ]

    def __str__(self):
        return f'{self.reviewer.email} rated apartment {self.apartment_id} {self.rating}/5'


def calculate_match(tenant, apartment):
    # The score is intentionally simple and explainable, because it is shown to
    # users with short text reasons rather than being a hidden recommendation.
    if not getattr(tenant, 'is_tenant', False):
        return 0, ['Match Score is only available for tenant accounts.']

    profile = tenant.seeker_profile
    reasons = []
    score = 0.0

    rent = apartment.rent_price
    if profile.budget_min is None or profile.budget_max is None:
        reasons.append('Add your budget in Account settings to improve this Match Score.')
    elif profile.budget_min <= rent <= profile.budget_max:
        score += 35
        reasons.append('Rent is within your budget range.')
    elif rent <= int(profile.budget_max * 1.1):
        score += 18
        reasons.append('Rent is slightly above your target budget.')
    else:
        reasons.append('Rent is outside your preferred budget range.')

    if profile.move_in_date is None:
        reasons.append('Add your preferred move-in date in Account settings to improve this Match Score.')
    else:
        delta_days = abs((apartment.available_from - profile.move_in_date).days)
        if delta_days <= 7:
            score += 20
            reasons.append('Move-in date is very close to your preferred date.')
        elif delta_days <= 30:
            score += 10
            reasons.append('Move-in date is reasonably close to your preferred date.')
        else:
            reasons.append('Move-in date is not very close to your preferred date.')

    if profile.is_smoker and not apartment.smoking_allowed:
        reasons.append('Smoking is not allowed in this listing.')
    else:
        score += 12.5
        reasons.append('Smoking rule is compatible.')

    if profile.has_pet and not apartment.pets_allowed:
        reasons.append('Pets are not allowed in this listing.')
    else:
        score += 12.5
        reasons.append('Pet rule is compatible.')

    tenant_hobby_ids = set(tenant.hobbies.values_list('id', flat=True))
    roommate_hobby_ids = set(
        apartment.contact_requests.filter(status__in=Apartment.CURRENT_TENANT_STATUSES)
        .values_list('tenant__hobbies__id', flat=True)
    )
    roommate_hobby_ids.discard(None)
    hobby_union = tenant_hobby_ids | roommate_hobby_ids

    if roommate_hobby_ids and hobby_union:
        similarity = len(tenant_hobby_ids & roommate_hobby_ids) / len(hobby_union)
        hobby_points = round(similarity * 20, 1)
        score += hobby_points
        if hobby_points > 0:
            reasons.append('There is some hobby similarity with current roommates.')
        else:
            reasons.append('Current roommates have different hobbies from yours.')
    else:
        reasons.append('No roommate hobby data is available yet.')

    return round(min(score, 100)), reasons


def save_match(tenant, apartment):
    score, reasons = calculate_match(tenant, apartment)
    match, _ = Match.objects.update_or_create(
        tenant=tenant,
        apartment=apartment,
        defaults={'score': score, 'reasons': reasons},
    )
    return match
