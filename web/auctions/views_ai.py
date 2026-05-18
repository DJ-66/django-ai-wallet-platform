from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import StreamingHttpResponse, JsonResponse
from .models import AICompanion, AIConversation, AIMessage, BidWallet
from .ai_services.ai_wallet import charge_wallet_for_ai_message, refund_wallet_for_ai_message
from .ai_services.ai_providers import get_ai_provider
from datetime import timedelta
from django.utils import timezone
from .ai_services.prompts import COMPANION_PROMPTS

def cleanup_old_unpinned_chats(user, days=7):
    cutoff = timezone.now() - timedelta(days=days)

    old_chats = AIConversation.objects.filter(
        user=user,
        is_pinned=False,
        updated_at__lt=cutoff,
    )

    old_chats.delete()

@login_required
def companion_list(request):
    cleanup_old_unpinned_chats(request.user, days=7)
    companions = AICompanion.objects.filter(is_active=True)

    return render(request, "auctions/ai/companion_list.html", {
        "companions": companions,
    })


@login_required
def start_companion_chat(request, slug):
    companion = get_object_or_404(
        AICompanion,
        slug=slug,
        is_active=True
    )

    conversation = AIConversation.objects.create(
        user=request.user,
        companion=companion,
        title=f"Chat with {companion.name}"
    )

    return redirect("ai_conversation", conversation_id=conversation.id)


@login_required
def ai_conversation(request, conversation_id):
    cleanup_old_unpinned_chats(request.user, days=7)
    conversation = get_object_or_404(
        AIConversation,
        id=conversation_id,
        user=request.user,
    )

    companion = conversation.companion

    if request.method == "POST":
        user_text = request.POST.get("message", "").strip()

        if not user_text:
            messages.error(request, "Empty message.")
            return redirect("ai_conversation", conversation_id=conversation.id)

        try:
            wallet, tx = charge_wallet_for_ai_message(
                user=request.user,
                companion=companion,
                conversation=conversation,
            )
        except ValidationError:
            messages.error(request, "Not enough credits.")
            return redirect("wallet")

        AIMessage.objects.create(
            conversation=conversation,
            role="user",
            content=user_text,
            credits_charged=companion.cost_per_message,
            provider_used=companion.provider,
        )
        # 👇 Set title if empty (first message)
        if not conversation.title or conversation.title.startswith("Chat with"):
            conversation.title = user_text.strip().replace("\n", " ")[:60]
            conversation.save(update_fields=["title"])

        recent = conversation.messages.order_by("-created_at")[:10]
        history = [
            {"role": m.role, "content": m.content}
            for m in reversed(recent)
            if m.role in ["user", "assistant"]
        ]

        provider = get_ai_provider(companion.provider)

        try:
            ai_reply = provider.generate_reply(
                system_prompt=companion.system_prompt,
                history=history,
            )
        except Exception as e:
            refund_wallet_for_ai_message(request.user, companion)
            messages.error(request, f"AI error. Credits refunded. Details: {e}")
            return redirect("ai_conversation", conversation_id=conversation.id)

        AIMessage.objects.create(
            conversation=conversation,
            role="assistant",
            content=ai_reply,
            provider_used=companion.provider,
        )

        return redirect("ai_conversation", conversation_id=conversation.id)

    wallet = BidWallet.objects.get(user=request.user)

    conversations = AIConversation.objects.filter(
        user=request.user
    ).select_related("companion").order_by("-is_pinned", "-updated_at")

    return render(request, "auctions/ai/conversation.html", {
        "conversation": conversation,
        "companion": companion,
        "messages_list": conversation.messages.all(),
        "wallet": wallet,
        "conversations": conversations,
    })
@login_required
def delete_conversation(request, conversation_id):
    conversation = get_object_or_404(
        AIConversation,
        id=conversation_id,
        user=request.user,
    )

    user = request.user

    conversation.delete()

    messages.success(request, "Chat deleted.")

    next_conversation = AIConversation.objects.filter(
        user=user
    ).order_by("-is_pinned", "-updated_at").first()

    if next_conversation:
        return redirect(
            "ai_conversation",
            conversation_id=next_conversation.id
    )

    return redirect("companion_list")


@login_required
def toggle_pin_conversation(request, conversation_id):
    conversation = get_object_or_404(
        AIConversation,
        id=conversation_id,
        user=request.user,
    )

    conversation.is_pinned = not conversation.is_pinned
    conversation.save(update_fields=["is_pinned"])

    return redirect("ai_conversation", conversation_id=conversation.id)

@login_required
def stream_ai_message(request, conversation_id):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    conversation = get_object_or_404(
        AIConversation,
        id=conversation_id,
        user=request.user,
    )

    companion = conversation.companion
    user_text = request.POST.get("message", "").strip()

    if not user_text:
        return JsonResponse({"error": "Empty message"}, status=400)

    try:
        wallet, tx = charge_wallet_for_ai_message(
            user=request.user,
            companion=companion,
            conversation=conversation,
        )
    except ValidationError:
        return JsonResponse({"error": "Not enough credits"}, status=402)

    AIMessage.objects.create(
        conversation=conversation,
        role="user",
        content=user_text,
        credits_charged=companion.cost_per_message,
        provider_used=companion.provider,
    )

    if not conversation.title or conversation.title.startswith("Chat with"):
        conversation.title = user_text.strip().replace("\n", " ")[:60]
        conversation.save(update_fields=["title"])

    recent = conversation.messages.order_by("-created_at")[:10]
    history = [
        {"role": m.role, "content": m.content}
        for m in reversed(recent)
        if m.role in ["user", "assistant"]
    ]

    provider = get_ai_provider(companion.provider)
    base_prompt = COMPANION_PROMPTS.get(
        companion.prompt_key,
        COMPANION_PROMPTS["flirty_social"]
)

    system_prompt = f"""
    {base_prompt}

    Companion Details:
    {companion.system_prompt}
    """

    def event_stream():
        full_reply = ""

        try:
            for chunk in provider.stream_reply(
                system_prompt=system_prompt,
                history=history,
            ):
                full_reply += chunk
                yield chunk

            AIMessage.objects.create(
                conversation=conversation,
                role="assistant",
                content=full_reply,
                provider_used=companion.provider,
            )

        except Exception as e:
            refund_wallet_for_ai_message(request.user, companion)
            yield f"\n\n[AI error. Credits refunded. Details: {e}]"

    return StreamingHttpResponse(event_stream(), content_type="text/plain")
