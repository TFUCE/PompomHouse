from django.conf import settings
from django.db import models


# A conversation only exists after a landlord approves a contact request.
class Conversation(models.Model):
    contact_request = models.OneToOneField(
        'apartments.ContactRequest',
        on_delete=models.CASCADE,
        related_name='conversation',
    )
    apartment = models.ForeignKey(
        'apartments.Apartment',
        on_delete=models.CASCADE,
        related_name='conversations',
    )
    tenant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='tenant_conversations',
    )
    landlord = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='landlord_conversations',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at', '-created_at']

    def __str__(self):
        return f'Conversation for request {self.contact_request_id}'

    def user_is_participant(self, user):
        return user.is_authenticated and user.id in {self.tenant_id, self.landlord_id}

    @property
    def other_participant_label_for_tenant(self):
        return self.landlord.get_full_name() or self.landlord.email

    @property
    def other_participant_label_for_landlord(self):
        return self.tenant.get_full_name() or self.tenant.email


# Messages are intentionally simple plain text for this prototype.
class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages',
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_messages',
    )
    body = models.TextField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)
    seen_by_recipient = models.BooleanField(default=False)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'Message {self.id} in conversation {self.conversation_id}'

