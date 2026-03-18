from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from apartments.models import Apartment, ContactRequest, ListingMode
from users.models import SeekerProfile, UserRole

from .models import Conversation, Message


User = get_user_model()


class MessagingWorkflowTests(TestCase):
    def login_as(self, user):
        self.client.force_login(user)

    def setUp(self):
        self.client = Client()
        self.tenant = User.objects.create_user(
            email='tenant@example.com',
            password='testpass123',
            first_name='Tenant',
            last_name='User',
            role=UserRole.TENANT,
        )
        SeekerProfile.objects.create(user=self.tenant)

        self.landlord = User.objects.create_user(
            email='landlord@example.com',
            password='testpass123',
            first_name='Landlord',
            last_name='User',
            role=UserRole.LANDLORD,
        )
        self.other_user = User.objects.create_user(
            email='other@example.com',
            password='testpass123',
            first_name='Other',
            last_name='User',
            role=UserRole.LANDLORD,
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
        self.contact_request = ContactRequest.objects.create(apartment=self.apartment, tenant=self.tenant)

    def test_approving_request_creates_conversation(self):
        self.login_as(self.landlord)
        response = self.client.get(reverse('apartments:update-request', args=[self.contact_request.id, 'approve']))
        self.assertRedirects(response, reverse('apartments:requests'))
        self.assertTrue(Conversation.objects.filter(contact_request=self.contact_request).exists())

    def test_non_participant_cannot_open_conversation(self):
        conversation = Conversation.objects.create(
            contact_request=self.contact_request,
            apartment=self.apartment,
            tenant=self.tenant,
            landlord=self.landlord,
        )
        self.login_as(self.other_user)
        response = self.client.get(reverse('messaging:detail', args=[conversation.id]))
        self.assertEqual(response.status_code, 404)

    def test_participant_can_send_message(self):
        conversation = Conversation.objects.create(
            contact_request=self.contact_request,
            apartment=self.apartment,
            tenant=self.tenant,
            landlord=self.landlord,
        )
        self.login_as(self.tenant)
        response = self.client.post(reverse('messaging:detail', args=[conversation.id]), {'body': 'Hello, is the room still available?'})
        self.assertRedirects(response, reverse('messaging:detail', args=[conversation.id]))
        self.assertEqual(Message.objects.filter(conversation=conversation).count(), 1)
        self.assertEqual(Message.objects.get(conversation=conversation).sender, self.tenant)


    def test_recipient_sees_message_alert_until_opening_conversation(self):
        conversation = Conversation.objects.create(
            contact_request=self.contact_request,
            apartment=self.apartment,
            tenant=self.tenant,
            landlord=self.landlord,
        )
        Message.objects.create(conversation=conversation, sender=self.tenant, body='Hello landlord')

        self.login_as(self.landlord)
        home_response = self.client.get(reverse('home'))
        self.assertTrue(home_response.context['has_message_alert'])

        self.client.get(reverse('messaging:detail', args=[conversation.id]))
        cleared_response = self.client.get(reverse('home'))
        self.assertFalse(cleared_response.context['has_message_alert'])


    def test_conversation_list_only_shows_threads_for_signed_in_user(self):
        own_conversation = Conversation.objects.create(
            contact_request=self.contact_request,
            apartment=self.apartment,
            tenant=self.tenant,
            landlord=self.landlord,
        )
        second_tenant = User.objects.create_user(
            email='tenant2@example.com',
            password='testpass123',
            first_name='Second',
            last_name='Tenant',
            role=UserRole.TENANT,
        )
        SeekerProfile.objects.create(user=second_tenant)
        other_apartment = Apartment.objects.create(
            owner=self.other_user,
            city='Leeds',
            address='2 Another Street',
            rent_price=650,
            room_count=1,
            available_from=date.today() + timedelta(days=12),
            smoking_allowed=False,
            pets_allowed=False,
            listing_mode=ListingMode.ENTIRE,
        )
        other_request = ContactRequest.objects.create(apartment=other_apartment, tenant=second_tenant)
        Conversation.objects.create(
            contact_request=other_request,
            apartment=other_apartment,
            tenant=second_tenant,
            landlord=self.other_user,
        )
        Message.objects.create(conversation=own_conversation, sender=self.landlord, body='Hello tenant')

        self.login_as(self.tenant)
        response = self.client.get(reverse('messaging:list'))

        conversations = list(response.context['conversations'])
        self.assertEqual(len(conversations), 1)
        self.assertEqual(conversations[0].id, own_conversation.id)
        self.assertTrue(conversations[0].has_unread_messages)

