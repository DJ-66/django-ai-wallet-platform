from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .capabilities import can_create_events
from .forms import EventForm
from .models import Event


def event_list(request):
    events = (
        Event.objects.filter(
            is_published=True,
            is_cancelled=False,
        )
        .select_related(
            "creator",
            "business",
        )
        .order_by("start_at")
    )

    return render(
        request,
        "auctions/events/event_list.html",
        {
            "events": events,
        },
    )


def event_detail(request, event_id):
    event = get_object_or_404(
        Event.objects.select_related(
            "creator",
            "business",
        ),
        id=event_id,
        is_published=True,
        is_cancelled=False,
    )

    return render(
        request,
        "auctions/events/event_detail.html",
        {
            "event": event,
        },
    )


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

