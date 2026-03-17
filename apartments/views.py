from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from messaging.models import Conversation

from .forms import ApartmentForm, ApartmentImageForm, ReviewForm, SearchForm
from .models import Apartment, ContactRequest, ContactStatus, Favourite, Review, save_match


# The same related data is needed in several listing pages, so keep the
# prefetch list in one place.
LISTING_PREFETCH = (
    'images',
    'contact_requests__tenant__hobbies',
    'reviews__reviewer',
    'favourites',
)


def apartment_queryset():
    # Base queryset for most apartment pages.
    return Apartment.objects.select_related('owner').prefetch_related(*LISTING_PREFETCH)


def refresh_apartment_batch(apartments):
    apartments = list(apartments)

    # Public visibility depends on runtime availability, so keep it fresh before rendering.
    for apartment in apartments:
        apartment.refresh_availability(save=True)

    return apartments


def favourite_ids_for(user):
    # Favourites only matter for tenant accounts.
    if not getattr(user, 'is_authenticated', False) or not getattr(user, 'is_tenant', False):
        return set()
    return set(user.favourites.values_list('apartment_id', flat=True))


def annotate_listing_flags(user, apartments):
    # Templates read apartment.is_saved directly, so attach the flag here once.
    saved_ids = favourite_ids_for(user)
    apartments = list(apartments)

    for apartment in apartments:
        apartment.is_saved = apartment.id in saved_ids

    return apartments


def visible_public_apartments(user=None):
    # Search/list pages only show listings that are still public after runtime
    # availability checks are applied.
    apartments = refresh_apartment_batch(apartment_queryset().filter(is_active=True))
    apartments = [apartment for apartment in apartments if apartment.public_visible]

    if user is None:
        return apartments

    return annotate_listing_flags(user, apartments)


def build_listing_pairs(user, apartments, include_match=True):
    # Keep the template input simple: each card gets one apartment and one match.
    apartments = list(apartments)
    pairs = []

    for apartment in apartments:
        match = None
        if include_match and getattr(user, 'is_authenticated', False) and getattr(user, 'is_tenant', False):
            match = save_match(user, apartment)
        pairs.append((apartment, match))

    return pairs


def filter_listing_search(apartments, data):
    # Search stays in Python because public visibility is partly calculated at runtime.
    if data.get('city'):
        city_term = data['city'].lower()
        apartments = [apartment for apartment in apartments if city_term in apartment.city.lower()]

    if data.get('available_from'):
        apartments = [
            apartment for apartment in apartments if apartment.available_from <= data['available_from']
        ]

    if data.get('min_rent') is not None:
        apartments = [
            apartment for apartment in apartments if apartment.rent_price >= data['min_rent']
        ]

    if data.get('max_rent') is not None:
        apartments = [
            apartment for apartment in apartments if apartment.rent_price <= data['max_rent']
        ]

    if data.get('room_count') is not None:
        apartments = [
            apartment for apartment in apartments if apartment.room_count >= data['room_count']
        ]

    if data.get('smoking_allowed'):
        apartments = [apartment for apartment in apartments if apartment.smoking_allowed]

    if data.get('pets_allowed'):
        apartments = [apartment for apartment in apartments if apartment.pets_allowed]

    return apartments


def visible_favourite_apartments(user):
    # Saved listings should still appear in favourites even if they later stop
    # being public, as long as the tenant saved them before.
    favourites = (
        Favourite.objects.filter(tenant=user)
        .select_related('apartment', 'apartment__owner')
        .prefetch_related('apartment__images', 'apartment__reviews', 'apartment__favourites')
    )

    favourite_ids = {item.apartment_id for item in favourites}
    apartments = refresh_apartment_batch(item.apartment for item in favourites)

    apartments = [
        apartment
        for apartment in apartments
        if apartment.public_visible or apartment.id in favourite_ids
    ]

    return annotate_listing_flags(user, apartments)


# A small helper keeps the detail page and invalid review POST using the same data.
def build_apartment_detail_context(request, apartment, review_form=None):
    match = None
    is_saved = False
    existing_review = None
    can_review = False

    if request.user.is_authenticated and request.user.is_tenant:
        match = save_match(request.user, apartment)
        is_saved = Favourite.objects.filter(tenant=request.user, apartment=apartment).exists()
        existing_review = Review.objects.filter(reviewer=request.user, apartment=apartment).first()
        can_review = apartment.can_review(request.user)
        if review_form is None:
            review_form = ReviewForm(instance=existing_review)

    apartment.is_saved = is_saved

    approved_roommates = apartment.approved_requests

    return {
        'apartment': apartment,
        'match': match,
        'approved_roommates': approved_roommates,
        'reviews': apartment.reviews.select_related('reviewer'),
        'review_form': review_form,
        'existing_review': existing_review,
        'can_review': can_review,
    }



def listings(request):
    # Landlords manage their own listings on the home page, so the search page
    # is kept tenant-only.
    if request.user.is_authenticated and request.user.is_landlord:
        messages.warning(request, 'Search is only available for tenant accounts.')
        return redirect('home')

    submitted = request.GET.get('search') == '1'
    form = SearchForm(request.GET or None)
    results = None

    if submitted and form.is_valid():
        apartments = visible_public_apartments(request.user)
        apartments = filter_listing_search(apartments, form.cleaned_data)
        results = build_listing_pairs(request.user, apartments)

    profile = None
    if request.user.is_authenticated and request.user.is_tenant:
        profile = getattr(request.user, 'seeker_profile', None)

    return render(
        request,
        'apartments/listings.html',
        {
            'form': form,
            'results': results,
            'submitted': submitted,
            'profile': profile,
        },
    )


@login_required
def favourites_page(request):
    if not request.user.is_tenant:
        messages.warning(request, 'Saved favourites are only available for tenant accounts.')
        return redirect('home')

    apartments = visible_favourite_apartments(request.user)
    context = {
        'listing_pairs': build_listing_pairs(request.user, apartments),
        'profile': getattr(request.user, 'seeker_profile', None),
    }
    return render(request, 'apartments/favourites.html', context)


@login_required
def toggle_favourite(request, apartment_id):
    if request.method != 'POST':
        return redirect('apartments:detail', apartment_id=apartment_id)

    if not request.user.is_tenant:
        messages.warning(request, 'Only tenant accounts can save favourites.')
        return redirect('home')

    apartment = get_object_or_404(Apartment, id=apartment_id)
    favourite, created = Favourite.objects.get_or_create(tenant=request.user, apartment=apartment)

    if created:
        messages.success(request, 'Listing saved to favourites.')
    else:
        favourite.delete()
        messages.success(request, 'Listing removed from favourites.')

    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER')
    if next_url:
        return redirect(next_url)
    return redirect('apartments:detail', apartment_id=apartment.id)


@login_required
def create_apartment(request):
    # A listing needs both the apartment record and one image before it is useful
    # on the site, so both forms are handled together.
    if not request.user.is_landlord:
        return redirect('home')

    form = ApartmentForm(request.POST or None)
    image_form = ApartmentImageForm(request.POST or None, request.FILES or None)

    if request.method == 'POST' and form.is_valid() and image_form.is_valid():
        apartment = form.save(commit=False)
        apartment.owner = request.user
        apartment.save()

        image = image_form.save(commit=False)
        if not image.image:
            image_form.add_error('image', 'Please upload one image for the listing.')
            apartment.delete()
        else:
            image.apartment = apartment
            image.save()
            messages.success(request, 'Apartment listing created.')
            return redirect('apartments:detail', apartment_id=apartment.id)

    return render(
        request,
        'apartments/apartment_form.html',
        {
            'form': form,
            'image_form': image_form,
            'page_title': 'Add apartment',
        },
    )


@login_required
def edit_apartment(request, apartment_id):
    # Editing keeps the same single-image setup as the create flow.
    apartment = get_object_or_404(Apartment, id=apartment_id, owner=request.user)
    apartment.refresh_availability(save=True)
    image_instance = apartment.primary_image

    form = ApartmentForm(request.POST or None, instance=apartment)
    image_form = ApartmentImageForm(request.POST or None, request.FILES or None, instance=image_instance)

    if request.method == 'POST' and form.is_valid() and image_form.is_valid():
        apartment = form.save()
        image = image_form.save(commit=False)
        image.apartment = apartment
        if not image.image and not image_instance:
            image_form.add_error('image', 'Please upload one image for the listing.')
        else:
            image.save()
            apartment.images.exclude(id=image.id).delete()
            messages.success(request, 'Apartment listing updated.')
            return redirect('apartments:detail', apartment_id=apartment.id)

    return render(
        request,
        'apartments/apartment_form.html',
        {
            'form': form,
            'image_form': image_form,
            'page_title': 'Edit apartment',
        },
    )


@login_required
def delete_apartment(request, apartment_id):
    apartment = get_object_or_404(Apartment, id=apartment_id, owner=request.user)
    if request.method != 'POST':
        return redirect('home')
    apartment.delete()
    messages.success(request, 'Listing deleted.')
    return redirect('home')



def apartment_detail(request, apartment_id):
    # Even when a listing is no longer public, related users may still need this
    # page for chat history, reviews, or move-out / relist flows.
    apartment = get_object_or_404(apartment_queryset(), id=apartment_id)
    apartment.refresh_availability(save=True)

    if not apartment.can_view_detail(request.user):
        raise Http404('Apartment not found.')

    return render(
        request,
        'apartments/detail.html',
        build_apartment_detail_context(request, apartment),
    )


@login_required
def save_review(request, apartment_id):
    # Reviews are tied to real stays only; the detail page remains visible to
    # past tenants so they can still edit their review later.
    if request.method != 'POST':
        return redirect('apartments:detail', apartment_id=apartment_id)

    if not request.user.is_tenant:
        messages.warning(request, 'Only tenants can post reviews.')
        return redirect('home')

    apartment = get_object_or_404(apartment_queryset(), id=apartment_id)
    apartment.refresh_availability(save=True)

    if apartment.owner_id == request.user.id:
        messages.warning(request, 'You cannot review your own listing.')
        return redirect('apartments:detail', apartment_id=apartment_id)

    if not apartment.can_view_detail(request.user):
        raise Http404('Apartment not found.')

    existing_review = Review.objects.filter(apartment=apartment, reviewer=request.user).first()
    if not apartment.can_review(request.user):
        messages.warning(request, 'Only tenants who have stayed in this listing can review it.')
        return redirect('apartments:detail', apartment_id=apartment_id)

    form = ReviewForm(request.POST, instance=existing_review)
    if form.is_valid():
        review = form.save(commit=False)
        review.apartment = apartment
        review.reviewer = request.user
        review.save()
        messages.success(request, 'Review saved.')
        return redirect('apartments:detail', apartment_id=apartment_id)

    context = build_apartment_detail_context(request, apartment, review_form=form)
    context['existing_review'] = existing_review
    context['can_review'] = True
    return render(request, 'apartments/detail.html', context, status=200)


@login_required
def requests_page(request):
    # Both roles share the same booking page, but they see opposite sides of the
    # same request records. Opening the page also clears the booking badge.
    base_queryset = ContactRequest.objects.select_related(
        'apartment',
        'apartment__owner',
        'tenant',
        'conversation',
    )

    if request.user.is_tenant:
        queryset = base_queryset.filter(tenant=request.user)
    else:
        queryset = base_queryset.filter(apartment__owner=request.user)

    if request.user.is_tenant:
        queryset.filter(tenant_seen=False).update(tenant_seen=True)
    else:
        queryset.filter(landlord_seen=False).update(landlord_seen=True)

    return render(
        request,
        'apartments/requests.html',
        {
            'pending': queryset.filter(status=ContactStatus.PENDING),
            'approved': queryset.filter(status__in=Apartment.CURRENT_TENANT_STATUSES),
            'former': queryset.filter(status=ContactStatus.LEFT),
            'rejected': queryset.filter(status=ContactStatus.REJECTED),
            'profile': getattr(request.user, 'seeker_profile', None) if request.user.is_tenant else None,
        },
    )


@login_required
def create_request(request, apartment_id):
    # New requests are only allowed while the listing is still publicly open.
    if not request.user.is_tenant:
        return redirect('home')

    apartment = get_object_or_404(apartment_queryset().filter(is_active=True), id=apartment_id)
    apartment.refresh_availability(save=True)
    if not apartment.public_visible:
        messages.warning(request, 'This listing is no longer available for new requests.')
        return redirect('home')

    contact_request, created = ContactRequest.objects.get_or_create(
        apartment=apartment,
        tenant=request.user,
    )
    if created:
        messages.success(request, 'Contact request sent to the landlord.')
    else:
        messages.warning(request, 'You have already created a contact request for this listing.')
    return redirect('apartments:requests')



@login_required
def request_move_out(request, request_id):
    # Tenants start the move-out flow from their approved stay row.
    contact_request = get_object_or_404(
        ContactRequest.objects.select_related('apartment', 'tenant'),
        id=request_id,
        tenant=request.user,
    )

    if contact_request.status != ContactStatus.APPROVED:
        messages.warning(request, 'Move-out can only be requested for an active approved stay.')
        return redirect('apartments:requests')

    contact_request.status = ContactStatus.LEAVE_PENDING
    contact_request.landlord_seen = False
    contact_request.tenant_seen = True
    contact_request.save(update_fields=['status', 'landlord_seen', 'tenant_seen'])
    messages.success(request, 'Move-out request sent to the landlord.')
    return redirect('apartments:requests')


@login_required
def approve_move_out(request, request_id):
    # Landlords confirm the move-out, which turns the stay into history and lets
    # the same listing be relisted later.
    contact_request = get_object_or_404(
        ContactRequest.objects.select_related('apartment', 'tenant'),
        id=request_id,
    )
    apartment = contact_request.apartment

    if apartment.owner != request.user:
        messages.warning(request, 'You are not allowed to update this request.')
        return redirect('apartments:requests')

    if contact_request.status != ContactStatus.LEAVE_PENDING:
        messages.warning(request, 'This stay does not have a pending move-out request.')
        return redirect('apartments:requests')

    contact_request.status = ContactStatus.LEFT
    contact_request.landlord_seen = True
    contact_request.tenant_seen = False
    contact_request.save(update_fields=['status', 'landlord_seen', 'tenant_seen'])

    if not apartment.is_room_share and apartment.is_active:
        apartment.is_active = False
        apartment.save(update_fields=['is_active'])

    messages.success(request, 'Tenant marked as moved out. You can relist this apartment now.')
    return redirect('apartments:requests')


@login_required
def relist_apartment(request, apartment_id):
    # Relisting reuses the same apartment record so old reviews stay attached.
    apartment = get_object_or_404(Apartment, id=apartment_id, owner=request.user)

    if request.method != 'POST':
        return redirect('apartments:detail', apartment_id=apartment.id)

    apartment.refresh_availability(save=True)
    if apartment.is_fully_rented:
        messages.warning(request, 'This listing still has a current tenant, so it cannot be relisted yet.')
        return redirect('apartments:detail', apartment_id=apartment.id)

    if apartment.is_active:
        messages.warning(request, 'This listing is already public.')
        return redirect('apartments:detail', apartment_id=apartment.id)

    apartment.is_active = True
    apartment.save(update_fields=['is_active'])
    messages.success(request, 'Listing relisted. Past reviews stay visible on the same apartment page.')
    return redirect('apartments:detail', apartment_id=apartment.id)


@login_required
def update_request(request, request_id, action):
    # This view handles the landlord decision on the first booking request.
    queryset = ContactRequest.objects.select_related('apartment', 'tenant')
    contact_request = get_object_or_404(queryset, id=request_id)
    apartment = contact_request.apartment
    apartment.refresh_availability(save=True)

    if apartment.owner != request.user:
        messages.warning(request, 'You are not allowed to update this request.')
        return redirect('apartments:requests')

    approved_count = apartment.contact_requests.filter(status__in=Apartment.CURRENT_TENANT_STATUSES)
    approved_count = approved_count.exclude(id=contact_request.id).count()

    if action == 'approve':
        # For whole-property listings, one approval ends the competition and the
        # remaining pending requests get rejected automatically.
        if not apartment.is_room_share and approved_count >= 1:
            messages.warning(request, 'This whole-property listing has already been rented out.')
            return redirect('apartments:requests')

        if apartment.is_room_share:
            max_rooms = apartment.room_count or 1
            if approved_count >= max_rooms:
                messages.warning(request, 'All available bedrooms in this listing have already been rented out.')
                return redirect('apartments:requests')

        contact_request.status = ContactStatus.APPROVED
        contact_request.approved_at = timezone.now()
        contact_request.landlord_seen = True
        contact_request.tenant_seen = False
        contact_request.save(update_fields=['status', 'approved_at', 'landlord_seen', 'tenant_seen'])

        Conversation.objects.get_or_create(
            contact_request=contact_request,
            defaults={
                'apartment': apartment,
                'tenant': contact_request.tenant,
                'landlord': apartment.owner,
            },
        )

        if not apartment.is_room_share:
            apartment.contact_requests.filter(status=ContactStatus.PENDING).exclude(
                id=contact_request.id
            ).update(status=ContactStatus.REJECTED, landlord_seen=True, tenant_seen=False)
        messages.success(request, 'Request approved and conversation opened.')
    elif action == 'reject':
        contact_request.status = ContactStatus.REJECTED
        contact_request.landlord_seen = True
        contact_request.tenant_seen = False
        contact_request.save(update_fields=['status', 'landlord_seen', 'tenant_seen'])
        messages.success(request, 'Request rejected.')
    else:
        messages.warning(request, 'Unknown action.')
        return redirect('apartments:requests')

    apartment.refresh_availability(save=True)
    return redirect('apartments:requests')
