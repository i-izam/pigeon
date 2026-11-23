from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .forms import SignupForm
from .models import Message, User


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
    users = User.objects.exclude(id=request.user.id).order_by('username')
    return render(request, 'chat/home.html', {'users': users})


@login_required
def chat_room(request, username):
    other = get_object_or_404(User, username=username)
    messages = Message.objects.filter(
        Q(sender=request.user, receiver=other) |
        Q(sender=other, receiver=request.user)
    )
    return render(request, 'chat/room.html', {
        'other': other,
        'messages': messages,
    })