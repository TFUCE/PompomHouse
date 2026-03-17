from datetime import date

from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from apartments.forms import day_choices, month_choices, parse_date_parts, year_choices

from .models import Hobby, SeekerProfile, User, UserRole


# Login stays role-based so tenant and landlord accounts do not get mixed up.
class RoleAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(label='Email address')

    def __init__(self, *args, expected_role=None, **kwargs):
        self.expected_role = expected_role
        super().__init__(*args, **kwargs)

    def clean(self):
        email = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')

        if email and password:
            self.user_cache = authenticate(
                self.request,
                username=email,
                password=password,
                role=self.expected_role,
            )

            if self.user_cache is None:
                raise self.get_invalid_login_error()

            self.confirm_login_allowed(self.user_cache)

        return self.cleaned_data

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if self.expected_role and user.role != self.expected_role:
            role_label = dict(UserRole.choices).get(self.expected_role, self.expected_role)
            raise forms.ValidationError(
                f'This account is not registered as a {role_label.lower()} account.'
            )


# Reset also matches both email and role, so shared emails do not clash.
class PasswordResetByEmailForm(forms.Form):
    email = forms.EmailField(label='Email address')
    new_password1 = forms.CharField(label='New password', widget=forms.PasswordInput)
    new_password2 = forms.CharField(label='Confirm new password', widget=forms.PasswordInput)

    def __init__(self, *args, expected_role=None, **kwargs):
        self.expected_role = expected_role
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('new_password1')
        password2 = cleaned_data.get('new_password2')
        if password1 and password1 != password2:
            self.add_error('new_password2', 'The two passwords do not match.')

        email = cleaned_data.get('email')
        if not email:
            return cleaned_data

        filters = {'email': email}
        if self.expected_role:
            filters['role'] = self.expected_role

        try:
            user = User.objects.get(**filters)
        except User.DoesNotExist:
            if self.expected_role:
                role_label = dict(UserRole.choices).get(self.expected_role, self.expected_role)
                self.add_error(
                    'email',
                    f'No {role_label.lower()} account was found for this email address.',
                )
            else:
                self.add_error('email', 'No account was found for this email address.')
            return cleaned_data

        cleaned_data['user'] = user
        return cleaned_data

    def save(self):
        user = self.cleaned_data['user']
        user.set_password(self.cleaned_data['new_password1'])
        user.save(update_fields=['password'])
        return user


# Shared registration fields live here so tenant and landlord forms stay consistent.
class RegistrationBaseForm(UserCreationForm):
    account_role = None

    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].label = 'Email *'
        self.fields['first_name'].label = 'First name *'
        self.fields['last_name'].label = 'Last name *'
        self.fields['password1'].label = 'Password *'
        self.fields['password2'].label = 'Password confirmation *'

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip()
        if self.account_role and User.objects.filter(email=email, role=self.account_role).exists():
            role_label = dict(UserRole.choices).get(self.account_role, self.account_role)
            raise forms.ValidationError(
                f'This email address has already been registered for a {role_label.lower()} account.'
            )
        return email

    def save(self, commit=True, role=None):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.role = role or self.account_role
        user.username = User.build_username(user.email, user.role)
        if commit:
            user.save()
        return user


# Tenants get hobbies during sign-up because matching uses them later on.
class TenantRegistrationForm(RegistrationBaseForm):
    account_role = UserRole.TENANT

    hobbies = forms.ModelMultipleChoiceField(
        queryset=Hobby.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text='Choose any hobbies that describe your lifestyle.',
    )

    def save(self, commit=True, role=None):
        user = super().save(commit=commit, role=role)
        if commit:
            user.hobbies.set(self.cleaned_data.get('hobbies', []))
        return user


class LandlordRegistrationForm(RegistrationBaseForm):
    account_role = UserRole.LANDLORD


# Account details are split from housing preferences so the page feels easier to edit.
class ProfileDetailsForm(forms.ModelForm):
    age = forms.IntegerField(required=False, min_value=0)
    gender = forms.ChoiceField(required=False, choices=SeekerProfile.GENDER_CHOICES)
    hobbies = forms.ModelMultipleChoiceField(
        queryset=Hobby.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text='Pick hobbies and interests that match your lifestyle.',
    )

    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'bio', 'avatar']

    def __init__(self, *args, profile=None, **kwargs):
        self.profile = profile
        super().__init__(*args, **kwargs)
        self.fields['avatar'].label = 'Image'
        self.fields['avatar'].widget = forms.FileInput()

        if self.instance.is_tenant:
            self.fields['hobbies'].initial = self.instance.hobbies.all()
            self.fields['age'].initial = getattr(self.profile, 'age', None)
            self.fields['gender'].initial = getattr(self.profile, 'gender', '')
        else:
            self.fields.pop('hobbies', None)
            self.fields.pop('age', None)
            self.fields.pop('gender', None)

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip()
        if User.objects.exclude(pk=self.instance.pk).filter(email=email, role=self.instance.role).exists():
            role_label = dict(UserRole.choices).get(self.instance.role, self.instance.role)
            raise forms.ValidationError(
                f'This email address is already used by another {role_label.lower()} account.'
            )
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = User.build_username(self.cleaned_data['email'], user.role)

        if self.data.get('avatar-clear') and user.avatar:
            user.avatar.delete(save=False)
            user.avatar = None

        if commit:
            user.save()
            if user.is_tenant and self.profile is not None:
                self.profile.age = self.cleaned_data.get('age')
                self.profile.gender = self.cleaned_data.get('gender', '')
                self.profile.save(update_fields=['age', 'gender'])
                user.hobbies.set(self.cleaned_data.get('hobbies', []))
        return user


# Preference form used by tenants when they fill in matching details.
class SeekerProfileForm(forms.ModelForm):
    move_in_year = forms.ChoiceField(required=False, label='Year')
    move_in_month = forms.ChoiceField(required=False, label='Month')
    move_in_day = forms.ChoiceField(required=False, label='Day')

    class Meta:
        model = SeekerProfile
        fields = ['budget_min', 'budget_max', 'is_smoker', 'has_pet']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        current_year = date.today().year

        # These labels are kept short because they sit inside a compact account page.
        self.fields['budget_min'].label = 'Budget min'
        self.fields['budget_max'].label = 'Budget max'
        self.fields['is_smoker'].label = 'Allow smoking'
        self.fields['has_pet'].label = 'Allow pets'
        self.fields['move_in_year'].choices = year_choices(start_year=current_year)
        self.fields['move_in_month'].choices = month_choices()
        self.fields['move_in_day'].choices = day_choices()
        if self.instance.move_in_date:
            self.fields['move_in_year'].initial = str(self.instance.move_in_date.year)
            self.fields['move_in_month'].initial = str(self.instance.move_in_date.month)
            self.fields['move_in_day'].initial = str(self.instance.move_in_date.day)

    def clean(self):
        cleaned_data = super().clean()
        budget_min = cleaned_data.get('budget_min')
        budget_max = cleaned_data.get('budget_max')
        if budget_min is not None and budget_max is not None and budget_max < budget_min:
            self.add_error('budget_max', 'Maximum budget must be greater than or equal to minimum budget.')

        cleaned_data['move_in_date'] = parse_date_parts(cleaned_data, 'move_in', required=False)
        return cleaned_data

    def save(self, commit=True):
        profile = super().save(commit=False)
        profile.move_in_date = self.cleaned_data.get('move_in_date')
        if commit:
            profile.save()
        return profile
