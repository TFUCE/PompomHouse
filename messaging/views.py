from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from .models import Conversation, Message


# Short form used at the bottom of the conversation page.
class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ['body']
        widgets = {
            'body': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Write a message…'}),
        }
        labels = {
            'body': 'New message',
        }

    def clean_body(self):
        body = (self.cleaned_data.get('body') or '').strip()
        if not body:
            raise forms.ValidationError('Please enter a message before sending.')
        return body


@login_required
# Inbox view switches queryset depending on which side of the conversation the user is on.
def conversation_list(request):
    conversations = Conversation.objects.select_related(
        'apartment', 'tenant', 'landlord', 'contact_request'
    ).prefetch_related('messages')

    if request.user.is_tenant:
        conversations = conversations.filter(tenant=request.user)
    else:
        conversations = conversations.filter(landlord=request.user)

    for conversation in conversations:
        conversation.has_unread_messages = conversation.messages.exclude(
            sender=request.user
        ).filter(seen_by_recipient=False).exists()

    profile = None
    if getattr(request.user, 'is_tenant', False):
        profile = getattr(request.user, 'seeker_profile', None)

    return render(
        request,
        'messaging/list.html',
        {'conversations': conversations, 'profile': profile},
    )


@login_required
# Detail page keeps the permission check close to the object lookup.
def conversation_detail(request, conversation_id):
    conversation = get_object_or_404(
        Conversation.objects.select_related(
            'apartment', 'tenant', 'landlord', 'contact_request'
        ).prefetch_related('messages__sender'),
        id=conversation_id,
    )

    # Hide the thread completely if the signed-in user is not one of the two participants.
    if not conversation.user_is_participant(request.user):
        raise Http404('Conversation not found.')

    conversation.messages.exclude(sender=request.user).filter(seen_by_recipient=False).update(
        seen_by_recipient=True
    )

    form = MessageForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        message = form.save(commit=False)
        message.conversation = conversation
        message.sender = request.user
        message.save()
        messages.success(request, 'Message sent.')
        return redirect('messaging:detail', conversation_id=conversation.id)

    profile = None
    if getattr(request.user, 'is_tenant', False):
        profile = getattr(request.user, 'seeker_profile', None)

    context = {
        'conversation': conversation,
        'form': form,
        'profile': profile,
    }
    return render(request, 'messaging/detail.html', context)
