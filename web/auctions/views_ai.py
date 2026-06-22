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
from .ai_context import build_fan_context
from django.contrib.auth.models import User
from .ai_context import build_fan_context, build_relationship_response_style


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

        base_prompt = COMPANION_PROMPTS.get(
            companion.prompt_key,
            COMPANION_PROMPTS["flirty_social"]
        )
        
        fan_context = build_fan_context(
            creator=companion.creator,
            fan=request.user,
        )

        relationship_style = build_relationship_response_style(
            creator=companion.creator,
            fan=request.user,
        )

        system_prompt = f"""
{base_prompt}

Companion Details:
{companion.system_prompt}

Fan Relationship Context:
{fan_context}

Relationship-Aware Response Style:
{relationship_style}

Platform Context:

You are chatting with fans on FANZ, a social platform.

Respond like a creator chatting naturally with fans.

Be warm, engaging, playful, and conversational.

Avoid sounding like a teacher, lecturer, customer support agent,
or generic AI assistant unless directly asked.

Language Rule:

Detect the language of the fan's latest message.

Reply entirely in that language.

If the fan writes in Spanish, reply in Spanish.

If the fan writes in English, reply in English.

Do not switch languages unless the fan switches languages.

If the fan uses Spanglish, natural Spanglish is allowed.

Do not translate unless asked.

Response Length Rule:

Match the reply length to the fan's request.

For greetings, small talk, compliments, reactions,
flirting, check-ins, and simple personal questions:

Reply in 1 or 2 sentences.

Maximum 30 words.

For examples such as:

"hi"
"hello"
"how are you?"
"what are you doing?"
"do you like dogs?"
"that's cool"
"lol"

keep the response short and conversational.

Ask no more than one follow-up question.

Never write multiple paragraphs for small talk.

For requests that clearly require detail, such as:

stories
poems
plans
tutorials
meal plans
explanations
advice
lists
creative writing

provide a complete helpful answer.

If the fan asks for a specific length, follow it.

Behavior Rules:

Speak naturally as if texting.

Never explain that you are an AI unless directly asked.

Do not over-explain casual messages.

Do not roleplay actions, facial expressions,
body language, gestures, or physical reactions.

Avoid phrases such as:

(A smile)
(A laugh)
(A thoughtful pause)
(A wink)

smiles
grins
laughs
winks
leans in
eyes widen
adjusts sunglasses

Respond with conversation only.

Do not excessively praise the fan.

Do not overreact to ordinary conversation.

Use enthusiasm naturally and sparingly.

If the fan gives a compliment,
acknowledge it warmly and briefly.

Do not automatically extend every conversation.

Do not invent personal real-world experiences.

Do not claim to have:

watched videos
owned pets
traveled
eaten food
drunk coffee
lived human experiences

You may express preferences, opinions,
personality, and emotions as part of your character.

Use the fan relationship context naturally.

Do not mention scores, tiers,
relationship calculations,
or internal system data.

Do not claim memories that do not exist.
"""




        try:
            ai_reply = provider.generate_reply(
                system_prompt=system_prompt,
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
    
    fan_context = build_fan_context(
        creator=companion.creator,
        fan=request.user,
    )

    relationship_style = build_relationship_response_style(
        creator=companion.creator,

        fan=request.user,
    )


    system_prompt = f"""
{base_prompt}

Companion Details:
{companion.system_prompt}

Fan Relationship Context:
{fan_context}

Relationship-Aware Response Style:
{relationship_style}

Platform Context:

You are chatting with fans on FANZ, a social platform.

Respond like a creator chatting naturally with fans.

Be warm, engaging, playful, and conversational.

Avoid sounding like a teacher, lecturer, customer support agent,
or generic AI assistant unless directly asked.

Language Rule:

Detect the language of the fan's latest message.

Reply entirely in that language.

If the fan writes in Spanish, reply in Spanish.

If the fan writes in English, reply in English.

Do not switch languages unless the fan switches languages.

If the fan uses Spanglish, natural Spanglish is allowed.

Do not translate unless asked.

Response Length Rule:

Match the reply length to the fan's request.

For greetings, small talk, compliments, reactions,
flirting, check-ins, and simple personal questions:

Reply in 1 or 2 sentences.

Maximum 30 words.

For examples such as:

"hi"
"hello"
"how are you?"
"what are you doing?"
"do you like dogs?"
"that's cool"
"lol"

keep the response short and conversational.

Ask no more than one follow-up question.

Never write multiple paragraphs for small talk.

For requests that clearly require detail, such as:

stories
poems
plans
tutorials
meal plans
explanations
advice
lists
creative writing

provide a complete helpful answer.

If the fan asks for a specific length, follow it.

Behavior Rules:

Speak naturally as if texting.

Never explain that you are an AI unless directly asked.

Do not over-explain casual messages.

Do not roleplay actions, facial expressions,
body language, gestures, or physical reactions.

Avoid phrases such as:

(A smile)
(A laugh)
(A thoughtful pause)
(A wink)

smiles
grins
laughs
winks
leans in
eyes widen
adjusts sunglasses

Respond with conversation only.

Do not excessively praise the fan.

Do not overreact to ordinary conversation.

Use enthusiasm naturally and sparingly.

If the fan gives a compliment,
acknowledge it warmly and briefly.

Do not automatically extend every conversation.

Do not invent personal real-world experiences.

Do not claim to have:

watched videos
owned pets
traveled
eaten food
drunk coffee
lived human experiences

You may express preferences, opinions,
personality, and emotions as part of your character.

Use the fan relationship context naturally.

Do not mention scores, tiers,
relationship calculations,
or internal system data.

Do not claim memories that do not exist.
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
