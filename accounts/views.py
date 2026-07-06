from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .emails import notify_admin_new_user, read_verification_token, send_verification_email
from .forms import ProfileForm, RegistrationForm, ResendVerificationForm
from .models import User


def register(request):
    if request.user.is_authenticated:
        return redirect("home")
    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            # commit=False builds the model without saving — like mapping a
            # DTO to an entity before SaveChanges in EF Core.
            user = form.save(commit=False)
            user.is_active = False  # activated by the emailed link (SPEC §3.1)
            user.save()
            send_verification_email(request, user)
            notify_admin_new_user(user)
            return render(request, "accounts/verification_sent.html", {"email": user.email})
    else:
        form = RegistrationForm()
    return render(request, "accounts/register.html", {"form": form})


def verify_email(request, token):
    pk = read_verification_token(token)
    user = User.objects.filter(pk=pk).first() if pk is not None else None
    if user is None:
        messages.error(
            request, "That verification link is invalid or has expired — request a new one below."
        )
        return redirect("resend-verification")
    if not user.is_active:
        user.is_active = True
        user.save(update_fields=["is_active"])
    messages.success(request, "Your email is verified — you can sign in now.")
    return redirect("login")


def resend_verification(request):
    if request.method == "POST":
        form = ResendVerificationForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            user = User.objects.filter(email__iexact=email, is_active=False).first()
            if user is not None:
                send_verification_email(request, user)
            # Same message whether or not the account exists, so this form
            # can't be used to probe which emails are registered.
            messages.success(
                request,
                "If an unverified account exists for that address, a new link is on its way.",
            )
            return redirect("login")
    else:
        form = ResendVerificationForm()
    return render(request, "accounts/resend_verification.html", {"form": form})


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
