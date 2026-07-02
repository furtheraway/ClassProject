from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .forms import ProfileForm, RegistrationForm
from .models import User


def register(request):
    if request.user.is_authenticated:
        return redirect("home")
    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Email verification arrives in Milestone 5; until then new
            # accounts are active immediately and signed in on the spot.
            login(request, user)
            messages.success(request, "Welcome! Your account has been created.")
            return redirect("home")
    else:
        form = RegistrationForm()
    return render(request, "accounts/register.html", {"form": form})


@login_required
def profile_detail(request, pk):
    profile_user = get_object_or_404(User, pk=pk)
    return render(request, "accounts/profile_detail.html", {"profile_user": profile_user})


@login_required
def profile_edit(request):
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated.")
            return redirect("profile-detail", pk=request.user.pk)
    else:
        form = ProfileForm(instance=request.user)
    return render(request, "accounts/profile_edit.html", {"form": form})
