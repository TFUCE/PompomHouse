from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from users.models import Hobby, SeekerProfile, UserRole

from .models import (
    Apartment,
    ContactRequest,
    ContactStatus,
    Favourite,
    ListingMode,
    Review,
    calculate_match,
)


User = get_user_model()


TEST_GIF = (
    b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,'
    b'\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
)


def listing_image(name='listing.gif'):
    return SimpleUploadedFile(name, TEST_GIF, content_type='image/gif')


@override_settings(MEDIA_ROOT='/tmp/findmyroomie_test_media')
class ApartmentWorkflowTests(TestCase):
    def login_as(self, user):
        self.client.force_login(user)

    def setUp(self):
        self.client = Client()
        self.tenant = User.objects.create_user(
            email='tenant@example.com',
            password='testpass123',
            first_name='Test',
            last_name='Tenant',
            role=UserRole.TENANT,
        )
        self.landlord = User.objects.create_user(
            email='landlord@example.com',
            password='testpass123',
            first_name='Test',
            last_name='Landlord',
            role=UserRole.LANDLORD,
        )
        self.other_tenant = User.objects.create_user(
            email='tenant2@example.com',
            password='testpass123',
            first_name='Other',
            last_name='Tenant',
            role=UserRole.TENANT,
        )
        self.other_landlord = User.objects.create_user(
            email='otherlandlord@example.com',
            password='testpass123',
            first_name='Other',
            last_name='Landlord',
            role=UserRole.LANDLORD,
        )
        self.profile = SeekerProfile.objects.create(
            user=self.tenant,
            budget_min=500,
            budget_max=800,
            move_in_date=date.today() + timedelta(days=7),
            is_smoker=False,
            has_pet=False,
        )
        SeekerProfile.objects.create(
            user=self.other_tenant,
            budget_min=400,
            budget_max=900,
            move_in_date=date.today() + timedelta(days=14),
            is_smoker=False,
            has_pet=False,
        )
        self.apartment = Apartment.objects.create(
            owner=self.landlord,
            city='Glasgow',
            address='1 University Avenue',
            rent_price=700,
            room_count=1,
            available_from=date.today() + timedelta(days=10),
            smoking_allowed=True,
            pets_allowed=True,
            listing_mode=ListingMode.ENTIRE,
        )

    def test_calculate_match_rewards_budget_and_move_in_alignment(self):
        score, reasons = calculate_match(self.tenant, self.apartment)
        self.assertEqual(score, 80)
        self.assertIn('Rent is within your budget range.', reasons)
        self.assertIn('Move-in date is very close to your preferred date.', reasons)

    def test_calculate_match_adds_roommate_hobby_similarity_points(self):
        study = Hobby.objects.create(category='Leisure', name='Board Games')
        self.tenant.hobbies.add(study)
        self.other_tenant.hobbies.add(study)
        ContactRequest.objects.create(
            apartment=self.apartment,
            tenant=self.other_tenant,
            status=ContactStatus.APPROVED,
        )

        score, reasons = calculate_match(self.tenant, self.apartment)
        self.assertGreater(score, 80)
        self.assertIn('There is some hobby similarity with current roommates.', reasons)

    def test_duplicate_contact_request_is_not_created(self):
        self.login_as(self.tenant)
        url = reverse('apartments:create-request', args=[self.apartment.id])
        self.client.get(url)
        self.client.get(url)
        self.assertEqual(ContactRequest.objects.filter(apartment=self.apartment, tenant=self.tenant).count(), 1)

    def test_landlord_cannot_create_contact_request(self):
        self.login_as(self.landlord)
        response = self.client.get(reverse('apartments:create-request', args=[self.apartment.id]))
        self.assertRedirects(response, reverse('home'))
        self.assertEqual(ContactRequest.objects.count(), 0)

    def test_approving_entire_property_rejects_other_pending_requests(self):
        first_request = ContactRequest.objects.create(apartment=self.apartment, tenant=self.tenant)
        second_request = ContactRequest.objects.create(apartment=self.apartment, tenant=self.other_tenant)
        self.login_as(self.landlord)

        response = self.client.get(reverse('apartments:update-request', args=[first_request.id, 'approve']))
        self.assertRedirects(response, reverse('apartments:requests'))
        first_request.refresh_from_db()
        second_request.refresh_from_db()
        self.assertEqual(first_request.status, ContactStatus.APPROVED)
        self.assertEqual(second_request.status, ContactStatus.REJECTED)

    def test_non_owner_cannot_edit_apartment(self):
        self.login_as(self.other_landlord)
        response = self.client.get(reverse('apartments:edit', args=[self.apartment.id]))
        self.assertEqual(response.status_code, 404)

    def test_tenant_can_save_and_remove_favourite(self):
        self.login_as(self.tenant)
        url = reverse('apartments:toggle-favourite', args=[self.apartment.id])

        first_response = self.client.post(url, {'next': reverse('home')})
        self.assertRedirects(first_response, reverse('home'))
        self.assertTrue(Favourite.objects.filter(tenant=self.tenant, apartment=self.apartment).exists())

        second_response = self.client.post(url, {'next': reverse('home')})
        self.assertRedirects(second_response, reverse('home'))
        self.assertFalse(Favourite.objects.filter(tenant=self.tenant, apartment=self.apartment).exists())

    def test_landlord_cannot_save_favourite(self):
        self.login_as(self.landlord)
        response = self.client.post(reverse('apartments:toggle-favourite', args=[self.apartment.id]))
        self.assertRedirects(response, reverse('home'))
        self.assertEqual(Favourite.objects.count(), 0)

    def test_only_tenant_with_approved_contact_can_review(self):
        ContactRequest.objects.create(
            apartment=self.apartment,
            tenant=self.tenant,
            status=ContactStatus.APPROVED,
        )
        self.login_as(self.tenant)
        response = self.client.post(
            reverse('apartments:save-review', args=[self.apartment.id]),
            {'rating': 5, 'comment': 'Really clear communication and the flat matched the photos.'},
            follow=True,
        )
        self.assertRedirects(response, reverse('apartments:detail', args=[self.apartment.id]))
        self.assertTrue(Review.objects.filter(apartment=self.apartment, reviewer=self.tenant).exists())
        self.apartment.refresh_from_db()
        self.assertEqual(self.apartment.review_summary(), '5.0/5 (1 review)')

    def test_pending_contact_request_cannot_review(self):
        ContactRequest.objects.create(apartment=self.apartment, tenant=self.tenant)
        self.login_as(self.tenant)
        response = self.client.post(
            reverse('apartments:save-review', args=[self.apartment.id]),
            {'rating': 4, 'comment': 'Nice place and easy to communicate with the landlord.'},
            follow=True,
        )
        self.assertRedirects(response, reverse('apartments:detail', args=[self.apartment.id]))
        self.assertFalse(Review.objects.filter(apartment=self.apartment, reviewer=self.tenant).exists())

    def test_approved_tenant_can_still_open_hidden_listing_detail(self):
        ContactRequest.objects.create(
            apartment=self.apartment,
            tenant=self.tenant,
            status=ContactStatus.APPROVED,
        )
        self.apartment.is_active = False
        self.apartment.save(update_fields=['is_active'])

        self.login_as(self.tenant)
        response = self.client.get(reverse('apartments:detail', args=[self.apartment.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ratings &amp; reviews')

    def test_non_participant_cannot_open_hidden_listing_detail(self):
        self.apartment.is_active = False
        self.apartment.save(update_fields=['is_active'])

        response = self.client.get(reverse('apartments:detail', args=[self.apartment.id]))

        self.assertEqual(response.status_code, 404)


    def test_tenant_can_request_move_out_from_approved_stay(self):
        stay = ContactRequest.objects.create(
            apartment=self.apartment,
            tenant=self.tenant,
            status=ContactStatus.APPROVED,
        )
        self.login_as(self.tenant)

        response = self.client.get(reverse('apartments:request-move-out', args=[stay.id]))

        self.assertRedirects(response, reverse('apartments:requests'))
        stay.refresh_from_db()
        self.assertEqual(stay.status, ContactStatus.LEAVE_PENDING)

    def test_landlord_can_approve_move_out_and_relist_same_apartment(self):
        stay = ContactRequest.objects.create(
            apartment=self.apartment,
            tenant=self.tenant,
            status=ContactStatus.LEAVE_PENDING,
        )
        self.apartment.is_active = False
        self.apartment.save(update_fields=['is_active'])
        self.login_as(self.landlord)

        approve_response = self.client.get(reverse('apartments:approve-move-out', args=[stay.id]))
        self.assertRedirects(approve_response, reverse('apartments:requests'))
        stay.refresh_from_db()
        self.assertEqual(stay.status, ContactStatus.LEFT)

        relist_response = self.client.post(reverse('apartments:relist', args=[self.apartment.id]))
        self.assertRedirects(relist_response, reverse('apartments:detail', args=[self.apartment.id]))
        self.apartment.refresh_from_db()
        self.assertTrue(self.apartment.is_active)
        self.assertTrue(self.apartment.public_visible)


    def test_landlord_sees_booking_alert_after_new_request(self):
        ContactRequest.objects.create(apartment=self.apartment, tenant=self.tenant)
        self.login_as(self.landlord)

        response = self.client.get(reverse('home'))

        self.assertTrue(response.context['has_booking_alert'])
        self.assertContains(response, 'New booking update')

    def test_booking_alert_clears_after_landlord_opens_booking_page(self):
        ContactRequest.objects.create(apartment=self.apartment, tenant=self.tenant)
        self.login_as(self.landlord)

        self.client.get(reverse('apartments:requests'))
        response = self.client.get(reverse('home'))

        self.assertFalse(response.context['has_booking_alert'])

    def test_tenant_sees_booking_alert_after_landlord_response(self):
        contact_request = ContactRequest.objects.create(apartment=self.apartment, tenant=self.tenant)
        self.login_as(self.landlord)
        self.client.get(reverse('apartments:update-request', args=[contact_request.id, 'approve']))
        self.client.logout()

        self.login_as(self.tenant)
        response = self.client.get(reverse('home'))

        self.assertTrue(response.context['has_booking_alert'])

    def test_booking_alert_clears_after_tenant_opens_booking_page(self):
        contact_request = ContactRequest.objects.create(apartment=self.apartment, tenant=self.tenant)
        self.login_as(self.landlord)
        self.client.get(reverse('apartments:update-request', args=[contact_request.id, 'reject']))
        self.client.logout()

        self.login_as(self.tenant)
        self.client.get(reverse('apartments:requests'))
        response = self.client.get(reverse('home'))

        self.assertFalse(response.context['has_booking_alert'])

    def test_relisted_listing_keeps_past_reviews_visible_to_new_tenants(self):
        ContactRequest.objects.create(
            apartment=self.apartment,
            tenant=self.tenant,
            status=ContactStatus.LEFT,
        )
        Review.objects.create(
            apartment=self.apartment,
            reviewer=self.tenant,
            rating=5,
            comment='Stayed here before and the flat was clean, quiet, and easy to move into.',
        )
        self.apartment.is_active = False
        self.apartment.save(update_fields=['is_active'])

        self.login_as(self.landlord)
        self.client.post(reverse('apartments:relist', args=[self.apartment.id]))
        self.client.logout()

        self.login_as(self.other_tenant)
        response = self.client.get(reverse('apartments:detail', args=[self.apartment.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Stayed here before and the flat was clean, quiet, and easy to move into.')
        self.assertContains(response, 'Request contact')

    def test_former_tenant_can_still_review_after_move_out(self):
        ContactRequest.objects.create(
            apartment=self.apartment,
            tenant=self.tenant,
            status=ContactStatus.LEFT,
        )
        self.apartment.is_active = False
        self.apartment.save(update_fields=['is_active'])
        self.login_as(self.tenant)

        response = self.client.post(
            reverse('apartments:save-review', args=[self.apartment.id]),
            {'rating': 4, 'comment': 'I moved out later, but the stay itself was smooth and well managed.'},
            follow=True,
        )

        self.assertRedirects(response, reverse('apartments:detail', args=[self.apartment.id]))
        self.assertTrue(Review.objects.filter(apartment=self.apartment, reviewer=self.tenant).exists())

    def test_landlord_can_create_apartment_with_required_image(self):
        self.login_as(self.landlord)

        response = self.client.post(
            reverse('apartments:add'),
            {
                'city': 'Leicester',
                'address': '10 Student Road',
                'floor': '2',
                'rent_price': '850',
                'listing_mode': ListingMode.ENTIRE,
                'room_count': '',
                'smoking_allowed': '',
                'pets_allowed': 'on',
                'available_year': str(date.today().year + 1),
                'available_month': '9',
                'available_day': '1',
                'image': listing_image(),
                'about': 'Close to campus and bills are included.',
            },
            follow=True,
        )

        created = Apartment.objects.get(address='10 Student Road')
        self.assertRedirects(response, reverse('apartments:detail', args=[created.id]))
        self.assertEqual(created.owner, self.landlord)
        self.assertEqual(created.images.count(), 1)

    def test_create_apartment_requires_image_upload(self):
        self.login_as(self.landlord)

        response = self.client.post(
            reverse('apartments:add'),
            {
                'city': 'Leicester',
                'address': '11 Student Road',
                'floor': '1',
                'rent_price': '800',
                'listing_mode': ListingMode.ENTIRE,
                'room_count': '',
                'smoking_allowed': '',
                'pets_allowed': '',
                'available_year': str(date.today().year + 1),
                'available_month': '9',
                'available_day': '2',
                'about': 'No image yet.',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Apartment.objects.filter(address='11 Student Road').exists())
        self.assertContains(response, 'This field is required.')

    def test_room_share_listing_can_only_approve_up_to_room_limit(self):
        self.apartment.listing_mode = ListingMode.ROOMS
        self.apartment.room_count = 2
        self.apartment.save(update_fields=['listing_mode', 'room_count'])
        third_tenant = User.objects.create_user(
            email='tenant3@example.com',
            password='testpass123',
            first_name='Third',
            last_name='Tenant',
            role=UserRole.TENANT,
        )
        SeekerProfile.objects.create(user=third_tenant)

        first_request = ContactRequest.objects.create(apartment=self.apartment, tenant=self.tenant)
        second_request = ContactRequest.objects.create(apartment=self.apartment, tenant=self.other_tenant)
        third_request = ContactRequest.objects.create(apartment=self.apartment, tenant=third_tenant)
        self.login_as(self.landlord)

        self.client.get(reverse('apartments:update-request', args=[first_request.id, 'approve']))
        self.client.get(reverse('apartments:update-request', args=[second_request.id, 'approve']))
        full_response = self.client.get(reverse('apartments:update-request', args=[third_request.id, 'approve']))

        self.assertRedirects(full_response, reverse('apartments:requests'))
        first_request.refresh_from_db()
        second_request.refresh_from_db()
        third_request.refresh_from_db()
        self.assertEqual(first_request.status, ContactStatus.APPROVED)
        self.assertEqual(second_request.status, ContactStatus.APPROVED)
        self.assertEqual(third_request.status, ContactStatus.PENDING)
        self.assertTrue(self.apartment.is_fully_rented)

    def test_auto_unlisted_whole_property_rejects_new_requests(self):
        ContactRequest.objects.create(
            apartment=self.apartment,
            tenant=self.tenant,
            status=ContactStatus.APPROVED,
            approved_at=timezone.now() - timedelta(days=2),
        )
        self.login_as(self.other_tenant)

        response = self.client.get(reverse('apartments:create-request', args=[self.apartment.id]))

        self.assertRedirects(response, reverse('home'))
        self.apartment.refresh_from_db()
        self.assertFalse(self.apartment.is_active)
        self.assertFalse(ContactRequest.objects.filter(apartment=self.apartment, tenant=self.other_tenant).exists())

    def test_non_owner_cannot_relist_listing(self):
        self.apartment.is_active = False
        self.apartment.save(update_fields=['is_active'])
        self.login_as(self.other_landlord)

        response = self.client.post(reverse('apartments:relist', args=[self.apartment.id]))

        self.assertEqual(response.status_code, 404)
        self.apartment.refresh_from_db()
        self.assertFalse(self.apartment.is_active)


    def test_favourites_page_requires_tenant_account(self):
        self.login_as(self.landlord)
        response = self.client.get(reverse('apartments:favourites'))
        self.assertRedirects(response, reverse('home'))
