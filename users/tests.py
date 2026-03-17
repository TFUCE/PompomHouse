from django.test import TestCase
from django.urls import reverse

from .models import User, UserRole


class SharedEmailRoleTests(TestCase):
    def test_same_email_can_register_once_per_role(self):
        tenant_response = self.client.post(
            reverse('users:register-tenant'),
            {
                'email': 'shared@example.com',
                'first_name': 'Shared',
                'last_name': 'Tenant',
                'password1': 'StrongPass123!',
                'password2': 'StrongPass123!',
            },
        )
        self.assertRedirects(tenant_response, reverse('login-role', args=[UserRole.TENANT]), fetch_redirect_response=False)

        landlord_response = self.client.post(
            reverse('users:register-landlord'),
            {
                'email': 'shared@example.com',
                'first_name': 'Shared',
                'last_name': 'Landlord',
                'password1': 'StrongPass123!',
                'password2': 'StrongPass123!',
            },
        )
        self.assertRedirects(landlord_response, reverse('login-role', args=[UserRole.LANDLORD]), fetch_redirect_response=False)

        self.assertEqual(User.objects.filter(email='shared@example.com').count(), 2)
        self.assertTrue(User.objects.filter(email='shared@example.com', role=UserRole.TENANT).exists())
        self.assertTrue(User.objects.filter(email='shared@example.com', role=UserRole.LANDLORD).exists())

    def test_same_email_cannot_register_twice_for_same_role(self):
        User.objects.create_user(
            email='shared@example.com',
            password='StrongPass123!',
            first_name='First',
            last_name='Tenant',
            role=UserRole.TENANT,
        )

        response = self.client.post(
            reverse('users:register-tenant'),
            {
                'email': 'shared@example.com',
                'first_name': 'Second',
                'last_name': 'Tenant',
                'password1': 'StrongPass123!',
                'password2': 'StrongPass123!',
            },
        )

        self.assertContains(
            response,
            'This email address has already been registered for a tenant account.',
            status_code=200,
        )
        self.assertEqual(User.objects.filter(email='shared@example.com', role=UserRole.TENANT).count(), 1)

    def test_shared_email_logs_into_correct_role_account(self):
        tenant = User.objects.create_user(
            email='shared@example.com',
            password='TenantPass123!',
            first_name='Shared',
            last_name='Tenant',
            role=UserRole.TENANT,
        )
        landlord = User.objects.create_user(
            email='shared@example.com',
            password='LandlordPass123!',
            first_name='Shared',
            last_name='Landlord',
            role=UserRole.LANDLORD,
        )

        tenant_response = self.client.post(
            reverse('login-role', args=[UserRole.TENANT]),
            {'username': 'shared@example.com', 'password': 'TenantPass123!'},
        )
        self.assertRedirects(tenant_response, reverse('home'), fetch_redirect_response=False)
        self.assertEqual(int(self.client.session['_auth_user_id']), tenant.id)

        self.client.logout()

        landlord_response = self.client.post(
            reverse('login-role', args=[UserRole.LANDLORD]),
            {'username': 'shared@example.com', 'password': 'LandlordPass123!'},
        )
        self.assertRedirects(landlord_response, reverse('home'), fetch_redirect_response=False)
        self.assertEqual(int(self.client.session['_auth_user_id']), landlord.id)

    def test_password_reset_only_resets_selected_role_account(self):
        tenant = User.objects.create_user(
            email='shared@example.com',
            password='TenantOld123!',
            first_name='Shared',
            last_name='Tenant',
            role=UserRole.TENANT,
        )
        landlord = User.objects.create_user(
            email='shared@example.com',
            password='LandlordOld123!',
            first_name='Shared',
            last_name='Landlord',
            role=UserRole.LANDLORD,
        )

        response = self.client.post(
            reverse('password-reset', args=[UserRole.TENANT]),
            {
                'email': 'shared@example.com',
                'new_password1': 'TenantNew123!',
                'new_password2': 'TenantNew123!',
            },
        )
        self.assertRedirects(response, reverse('login-role', args=[UserRole.TENANT]), fetch_redirect_response=False)

        tenant.refresh_from_db()
        landlord.refresh_from_db()
        self.assertTrue(tenant.check_password('TenantNew123!'))
        self.assertTrue(landlord.check_password('LandlordOld123!'))

    def test_tenant_registration_creates_seeker_profile(self):
        response = self.client.post(
            reverse('users:register-tenant'),
            {
                'email': 'newtenant@example.com',
                'first_name': 'New',
                'last_name': 'Tenant',
                'password1': 'StrongPass123!',
                'password2': 'StrongPass123!',
            },
        )

        self.assertRedirects(response, reverse('login-role', args=[UserRole.TENANT]), fetch_redirect_response=False)
        user = User.objects.get(email='newtenant@example.com', role=UserRole.TENANT)
        self.assertTrue(hasattr(user, 'seeker_profile'))
