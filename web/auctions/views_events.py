from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .capabilities import can_create_events
from .forms import EventForm


@login_required
def create_event(request):
    if not can_create_events(request.user):
        messages.error(
            request,
            "You need at least 1000 credits to create new events.",
        )
        return redirect("wallet")

    if request.method == "POST":
        form = EventForm(
            request.POST,
            request.FILES,
            user=request.user,
        )

        if form.is_valid():
            event = form.save(commit=False)
            event.creator = request.user
            event.save()

            messages.success(
                request,
                "Your event was created successfully.",
            )
            return redirect(
                "public_profile",
                username=request.user.username,
            )
    else:
        form = EventForm(user=request.user)

    return render(
        request,
        "auctions/events/event_form.html",
        {
            "form": form,
        },
    )

