from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .forms import SignupForm
from .models import Message, User


def splash(request):
    return render(request, 'chat/splash.html')


def signup(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = SignupForm(request.POST)

        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('home')
    else:
        form = SignupForm()

    return render(request, 'registration/signup.html', {'form': form})


@login_required
def home(request):
    users = (
        User.objects.exclude(id=request.user.id)
        .annotate(
            unread=Count(
                'sent_messages',
                filter=Q(
                    sent_messages__receiver=request.user,
                    sent_messages__is_read=False,
                ),
            )
        )
        .order_by('username')
    )

    return render(request, 'chat/home.html', {'users': users})


@login_required
def chat_room(request, username):
    other = get_object_or_404(User, username=username)

    if other == request.user:
        return redirect('home')

    updated = Message.objects.filter(
        sender=other,
        receiver=request.user,
        is_read=False
    ).update(is_read=True)

    if updated:
        channel_layer = get_channel_layer()

        # home page ka unread badge update karo
        async_to_sync(channel_layer.group_send)(
            f'notifications_{request.user.id}',
            {
                'type': 'unread_update'
            }
        )

        # sender ke khule room mein ✓✓ dikhao
        a, b = sorted([request.user.id, other.id])
        async_to_sync(channel_layer.group_send)(
            f'chat_{a}_{b}',
            {
                'type': 'messages_read',
                'reader': request.user.username,
            }
        )

    messages = Message.objects.filter(
        Q(sender=request.user, receiver=other) |
        Q(sender=other, receiver=request.user)
    )

    return render(request, 'chat/room.html', {
        'other': other,
        'messages': messages,
    })