from datetime import date

from django import forms

from .models import Apartment, ApartmentImage, ListingMode, Review

UK_CITY_CHOICES = [
    ('', 'Select a city'),
    ('London', 'London'),
    ('Birmingham', 'Birmingham'),
    ('Manchester', 'Manchester'),
    ('Leeds', 'Leeds'),
    ('Glasgow', 'Glasgow'),
    ('Liverpool', 'Liverpool'),
    ('Bristol', 'Bristol'),
    ('Sheffield', 'Sheffield'),
    ('Edinburgh', 'Edinburgh'),
    ('Cardiff', 'Cardiff'),
    ('Leicester', 'Leicester'),
    ('Coventry', 'Coventry'),
    ('Nottingham', 'Nottingham'),
    ('Newcastle upon Tyne', 'Newcastle upon Tyne'),
    ('Belfast', 'Belfast'),
    ('Southampton', 'Southampton'),
    ('Portsmouth', 'Portsmouth'),
    ('Oxford', 'Oxford'),
    ('Cambridge', 'Cambridge'),
    ('York', 'York'),
    ('Bath', 'Bath'),
    ('Brighton', 'Brighton'),
    ('Aberdeen', 'Aberdeen'),
]


def year_choices(start_year=None, years=6):
    # The project uses separate select boxes instead of one browser date widget
    # so the form stays consistent across devices.
    start = start_year or date.today().year
    return [('', 'Year')] + [(str(year), str(year)) for year in range(start, start + years)]


def month_choices():
    return [('', 'Month')] + [(str(month), f'{month:02d}') for month in range(1, 13)]


def day_choices():
    return [('', 'Day')] + [(str(day), f'{day:02d}') for day in range(1, 32)]


def parse_date_parts(cleaned_data, prefix, required=False):
    # Rebuild one date from the three small select boxes used in the UI.
    year = cleaned_data.get(f'{prefix}_year')
    month = cleaned_data.get(f'{prefix}_month')
    day = cleaned_data.get(f'{prefix}_day')
    provided = any([year, month, day])

    if not provided:
        if required:
            raise forms.ValidationError(
                f'Select year, month, and day for {prefix.replace("_", " ")}.'
            )
        return None

    if not all([year, month, day]):
        raise forms.ValidationError(
            f'Select year, month, and day for {prefix.replace("_", " ")}.'
        )

    try:
        return date(int(year), int(month), int(day))
    except ValueError as exc:
        raise forms.ValidationError(
            f'Enter a valid {prefix.replace("_", " ")} date.'
        ) from exc


class DatePartsMixin:
    def setup_date_parts(self, prefix, selected_date=None, start_year=None):
        self.fields[f'{prefix}_year'].choices = year_choices(start_year=start_year)
        self.fields[f'{prefix}_month'].choices = month_choices()
        self.fields[f'{prefix}_day'].choices = day_choices()
        if selected_date:
            self.fields[f'{prefix}_year'].initial = str(selected_date.year)
            self.fields[f'{prefix}_month'].initial = str(selected_date.month)
            self.fields[f'{prefix}_day'].initial = str(selected_date.day)


class ApartmentForm(DatePartsMixin, forms.ModelForm):
    # The add/edit page keeps dates split into year / month / day selects to
    # match the visual style used elsewhere in the project.
    city = forms.ChoiceField(choices=UK_CITY_CHOICES, label='City *')
    available_year = forms.ChoiceField(required=False, label='Year')
    available_month = forms.ChoiceField(required=False, label='Month')
    available_day = forms.ChoiceField(required=False, label='Day')

    class Meta:
        model = Apartment
        fields = [
            'city',
            'address',
            'floor',
            'rent_price',
            'listing_mode',
            'room_count',
            'smoking_allowed',
            'pets_allowed',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['address'].label = 'Address *'
        self.fields['rent_price'].label = 'Rent price *'
        self.fields['listing_mode'].label = 'Rental option *'
        self.fields['available_year'].label = 'Year *'
        self.fields['room_count'].label = 'Bedrooms available'
        self.fields['room_count'].required = False
        self.fields['room_count'].help_text = 'Only needed when you are renting out several bedrooms.'
        self.fields['smoking_allowed'].label = 'Allow smoking'
        self.fields['pets_allowed'].label = 'Allow pets'

        selected_date = self.instance.available_from if getattr(self.instance, 'pk', None) else None
        self.setup_date_parts('available', selected_date=selected_date)
        if selected_date and self.instance.listing_mode == ListingMode.ROOMS:
            self.fields['room_count'].initial = self.instance.room_count

    def clean_address(self):
        value = (self.cleaned_data.get('address') or '').strip()
        if not value:
            raise forms.ValidationError('Address is required.')
        return value

    def clean(self):
        cleaned_data = super().clean()
        cleaned_data['available_from'] = parse_date_parts(cleaned_data, 'available', required=True)

        listing_mode = cleaned_data.get('listing_mode')
        room_count = cleaned_data.get('room_count')
        if listing_mode == ListingMode.ROOMS and (room_count is None or room_count < 1):
            self.add_error('room_count', 'Enter how many bedrooms are available for rent.')
        return cleaned_data

    def save(self, commit=True):
        apartment = super().save(commit=False)
        apartment.available_from = self.cleaned_data['available_from']
        apartment.is_active = True

        if apartment.listing_mode == ListingMode.ROOMS:
            rooms = self.cleaned_data.get('room_count') or 1
            apartment.room_count = rooms
        else:
            apartment.room_count = 1

        if commit:
            apartment.save()
        return apartment


class ApartmentImageForm(forms.ModelForm):
    class Meta:
        model = ApartmentImage
        fields = ['image', 'about']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['about'].label = 'About'


class SearchForm(DatePartsMixin, forms.Form):
    city = forms.CharField(required=False)
    available_year = forms.ChoiceField(required=False, label='Year')
    available_month = forms.ChoiceField(required=False, label='Month')
    available_day = forms.ChoiceField(required=False, label='Day')
    min_rent = forms.IntegerField(required=False, min_value=0)
    max_rent = forms.IntegerField(required=False, min_value=0)
    room_count = forms.IntegerField(required=False, min_value=1)
    smoking_allowed = forms.BooleanField(required=False)
    pets_allowed = forms.BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setup_date_parts('available')

    def clean(self):
        cleaned_data = super().clean()
        min_rent = cleaned_data.get('min_rent')
        max_rent = cleaned_data.get('max_rent')
        if min_rent is not None and max_rent is not None and max_rent < min_rent:
            self.add_error('max_rent', 'Maximum rent must be greater than or equal to minimum rent.')
        cleaned_data['available_from'] = parse_date_parts(cleaned_data, 'available', required=False)
        return cleaned_data


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['rating', 'comment']
        widgets = {
            'comment': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Share your experience with this listing.'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['rating'].label = 'Rating'
        self.fields['comment'].label = 'Review'

    def clean_comment(self):
        comment = (self.cleaned_data.get('comment') or '').strip()
        if len(comment) < 10:
            raise forms.ValidationError('Write at least a short sentence for the review.')
        return comment
