from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from apartments.views import build_listing_pairs, refresh_apartment_batch, visible_public_apartments

from .forms import (
    LandlordRegistrationForm,
    PasswordResetByEmailForm,
    ProfileDetailsForm,
    RoleAuthenticationForm,
    SeekerProfileForm,
    TenantRegistrationForm,
)
from .models import SeekerProfile, UserRole


# Tenant sign-up also creates an empty seeker profile for later preferences.
def register_tenant(request):
    if request.user.is_authenticated:
        return redirect('home')

    form = TenantRegistrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save(role=UserRole.TENANT)
        SeekerProfile.objects.create(user=user)
        messages.success(
            request,
            'Tenant account created. You can sign in now and complete your account settings later.',
        )
        return redirect('login-role', role='tenant')

    return render(
        request,
        'users/register.html',
        {
            'form': form,
            'page_title': 'Tenant registration',
            'page_intro': 'Create your account first. You can complete your budget, move-in date, and lifestyle preferences in Account after logging in.',
            'submit_label': 'Create tenant account',
        },
    )


# Landlords do not need a seeker profile, so this view stays shorter.
def register_landlord(request):
    if request.user.is_authenticated:
        return redirect('home')

    form = LandlordRegistrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save(role=UserRole.LANDLORD)
        messages.success(request, 'Landlord account created. You can sign in now.')
        return redirect('login-role', role='landlord')

    return render(
        request,
        'users/register.html',
        {
            'form': form,
            'page_title': 'Landlord registration',
            'page_intro': 'Create your account first. You can add profile details later in Account.',
            'submit_label': 'Create landlord account',
        },
    )


def landing(request):
    if request.user.is_authenticated:
        return redirect('home')
    return render(request, 'main/landing.html')


# Login and register use the same simple role chooser template.
def register_choice(request):
    return render(
        request,
        'main/role_choice.html',
        {
            'page_title': 'Choose your role',
            'page_intro': 'Select the account type that matches your purpose on the platform.',
            'left_title': 'Tenant',
            'left_text': 'Create a basic account now, then add budget, move-in date, hobbies, and lifestyle preferences later in Account.',
            'left_url': 'users:register-tenant',
            'left_button': 'Register as tenant',
            'right_title': 'Landlord',
            'right_text': 'Create an owner account, then add apartment listings and review contact requests.',
            'right_url': 'users:register-landlord',
            'right_button': 'Register as landlord',
        },
    )


def login_choice(request):
    return render(
        request,
        'main/role_choice.html',
        {
            'page_title': 'Choose how you want to log in',
            'left_title': 'Tenant login',
            'left_text': 'Use this if you are looking for housing.',
            'left_url': 'login-role',
            'left_url_arg': 'tenant',
            'left_button': 'Continue as tenant',
            'right_title': 'Landlord login',
            'right_text': 'Use this if you manage or post listings.',
            'right_url': 'login-role',
            'right_url_arg': 'landlord',
            'right_button': 'Continue as landlord',
        },
    )


def role_login(request, role):
    if role not in {UserRole.TENANT, UserRole.LANDLORD}:
        return redirect('login')

    role_label = dict(UserRole.choices)[role]
    if request.user.is_authenticated:
        if request.user.role == role:
            return redirect('home')
        messages.warning(request, 'You are already signed in with a different account role.')
        return redirect('home')

    form = RoleAuthenticationForm(
        request=request,
        data=request.POST or None,
        expected_role=role,
    )
    if request.method == 'POST' and form.is_valid():
        login(request, form.get_user())
        messages.success(request, f'{role_label} login successful.')
        return redirect('home')

    return render(
        request,
        'main/login_role.html',
        {
            'form': form,
            'role': role,
            'role_label': role_label,
        },
    )


def password_reset(request, role):
    if role not in {UserRole.TENANT, UserRole.LANDLORD}:
        return redirect('login')

    role_label = dict(UserRole.choices)[role]
    form = PasswordResetByEmailForm(request.POST or None, expected_role=role)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(
            request,
            f'Password updated for the {role_label.lower()} account. You can sign in now.',
        )
        return redirect('login-role', role=role)

    return render(
        request,
        'main/password_reset.html',
        {
            'form': form,
            'role': role,
            'role_label': role_label,
        },
    )


@login_required
def home(request):
    if request.user.is_tenant:
        profile = request.user.seeker_profile
        visible_apartments = visible_public_apartments(request.user)[:12]
        context = {
            'profile': profile,
            'profile_incomplete': any(
                value in {None, ''}
                for value in (profile.budget_min, profile.budget_max, profile.move_in_date)
            ),
            'listing_pairs': build_listing_pairs(request.user, visible_apartments),
        }
        return render(request, 'main/home.html', context)

    apartments = refresh_apartment_batch(
        request.user.apartments.select_related('owner').prefetch_related(
            'images',
            'contact_requests__tenant__hobbies',
            'reviews',
        )[:12]
    )

    for apartment in apartments:
        apartment.is_saved = False

    return render(
        request,
        'main/home.html',
        {'listing_pairs': build_listing_pairs(request.user, apartments, include_match=False)},
    )


@login_required
# Account page uses a small tab-like section switch between profile and preferences.
def account(request):
    profile = request.user.seeker_profile if request.user.is_tenant else None
    section = request.GET.get('section') or request.POST.get('section') or 'profile'
    if section not in {'profile', 'preferences'}:
        section = 'profile'
    if section == 'preferences' and request.user.is_landlord:
        section = 'profile'

    details_form = ProfileDetailsForm(instance=request.user, profile=profile)
    seeker_form = SeekerProfileForm(instance=profile) if profile else None

    if request.method == 'POST':
        if section == 'profile':
            details_form = ProfileDetailsForm(
                request.POST,
                request.FILES,
                instance=request.user,
                profile=profile,
            )
            if details_form.is_valid():
                details_form.save()
                messages.success(request, 'Profile details saved.')
                return redirect(f'{request.path}?section=profile')
        elif section == 'preferences' and seeker_form is not None:
            seeker_form = SeekerProfileForm(request.POST, instance=profile)
            if seeker_form.is_valid():
                seeker_form.save()
                messages.success(request, 'Preferences saved.')
                return redirect(f'{request.path}?section=preferences')

    context = {
        'section': section,
        'details_form': details_form,
        'seeker_form': seeker_form,
        'profile': profile,
    }
    return render(request, 'users/account.html', context)



def navigation_alerts(request):
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return {
            'has_booking_alert': False,
            'has_message_alert': False,
        }

    from django.db.models import Q

    from apartments.models import ContactRequest, ContactStatus
    from messaging.models import Message

    if request.user.is_tenant:
        has_booking_alert = ContactRequest.objects.filter(
            tenant=request.user,
            tenant_seen=False,
            status__in=[ContactStatus.APPROVED, ContactStatus.REJECTED, ContactStatus.LEFT],
        ).exists()
    else:
        has_booking_alert = ContactRequest.objects.filter(
            apartment__owner=request.user,
            landlord_seen=False,
            status__in=[ContactStatus.PENDING, ContactStatus.LEAVE_PENDING],
        ).exists()

    has_message_alert = Message.objects.filter(
        seen_by_recipient=False,
    ).exclude(sender=request.user).filter(
        Q(conversation__tenant=request.user) | Q(conversation__landlord=request.user)
    ).exists()

    return {
        'has_booking_alert': has_booking_alert,
        'has_message_alert': has_message_alert,
    }
