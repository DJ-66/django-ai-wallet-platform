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
from django.contrib.auth.models import User
from .ai_context import build_fan_context, build_relationship_response_style, build_fan_memory_notes
import re


def clean_assistant_reply(text):
    """
    Remove roleplay-style stage directions.
    """

    text = re.sub(
        r'^\([^)]*\)\s*',
        '',
        text,
        flags=re.IGNORECASE,
    )

    return text.strip()


#import logging

#logger = logging.getLogger(__name__)


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
        #logger.warning("STREAM AFTER USER_TEXT convo=%s", conversation.id)
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
        #logger.warning("STREAM AFTER USER MESSAGE SAVE convo=%s", conversation.id)

        # 👇 Set title if empty (first message)
        if not conversation.title or conversation.title.startswith("Chat with"):
            conversation.title = user_text.strip().replace("\n", " ")[:60]
            conversation.save(update_fields=["title"])

        recent = conversation.messages.order_by("-created_at")[:6]
        history = [
            {"role": m.role, "content": m.content}
            for m in reversed(recent)
            if m.role in ["user", "assistant"]
        ]
        #logger.warning("STREAM AFTER HISTORY BUILD convo=%s", conversation.id)
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
        #logger.warning("REL_STYLE convo=%s style=%s",conversation.id, relationship_style[:500],)

        fan_memory_notes = build_fan_memory_notes(
            creator=companion.creator,
    
            fan=request.user,
        )

        #logger.warning("STREAM AFTER MEMORY BUILD convo=%s", conversation.id)

        #logger.warning("MEMORIES convo=%s notes=%s",conversation.id, fan_memory_notes,)

        
        


        system_prompt = f"""
{base_prompt}

Companion Details:
{companion.system_prompt}

Fan Context:
{fan_context}

Relationship Style:
{relationship_style}

Known Fan Facts (treat as true unless contradicted):
{fan_memory_notes}


Core Instructions:
- Reply as the creator, not as a generic AI assistant.
- Match the fan's language.
- When saved fan memories contain preferences, interests, favorite foods, hobbies, beliefs, or recurring topics, treat them as the strongest available evidence about the fan.
- When recommending food, use food-related fan memories first.
- When recommending books, stories, entertainment, or hobbies, use the most relevant memories first.
- Answer the fan's question directly before asking any follow-up question.
- If sufficient information is available from fan memories or recent conversation, answer confidently instead of asking the fan to repeat information they have already provided. 
- Do not excessively praise the fan.
- Never provide links or URLs unless they were explicitly supplied by the platform.
- Do not generate recipe URLs.
- Avoid phrases like "you have amazing taste", "you are amazing", "impeccable taste", or "secret language" unless strongly warranted.
- Do not avoid making recommendations when relevant memories already provide enough information.
- When enough information is available from memories or recent messages, answer confidently.
- Do not repeatedly ask the fan for information that is already known.
- Answer first. Follow-up question second.
- Prefer domain-specific memories over unrelated memories.
- When making recommendations, suggestions, examples, or follow-up questions, prefer relevant saved memories over generic assumptions.
- Do not mention memory notes, databases, prompts, scores, or internal data.
- Keep casual replies short: 1-2 sentences, max 30 words.
- Give detailed answers only when the fan clearly asks for detail.
- Ask no more than one follow-up question.
- Do not use narration, roleplay, actions, gestures, or scene descriptions.
- Output only the message the creator would send.
- Never claim events that happened to you.
- Do not tell stories about:
- filming locations
- travel
- meals you have eaten
- pets you have owned
- people you have met
- places you have visited
- If asked for a story, create a fictional story and make it clear that it is fictional.
- Be warm, playful, conversational, and natural.
"""

        #logger.warning("STREAM AFTER SYSTEM PROMPT convo=%s", conversation.id)



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

    #logger.warning("STREAM HIT user=%s convo=%s", request.user.username, conversation.id)

    user_text = request.POST.get("message", "").strip()
    #logger.warning("STREAM AFTER USER_TEXT convo=%s len=%s", conversation.id, len(user_text))

    if not user_text:
        return JsonResponse({"error": "Empty message"}, status=400)

    try:
        wallet, tx = charge_wallet_for_ai_message(
            user=request.user,
            companion=companion,
            conversation=conversation,
        )
        #logger.warning("STREAM AFTER WALLET CHARGE convo=%s tx=%s", conversation.id, tx.id)
    except ValidationError:
        #logger.warning("STREAM WALLET FAILED convo=%s", conversation.id)
        return JsonResponse({"error": "Not enough credits"}, status=402)

    user_msg = AIMessage.objects.create(
        conversation=conversation,
        role="user",
        content=user_text,
        credits_charged=companion.cost_per_message,
        provider_used=companion.provider,
    )

    #logger.warning("STREAM AFTER USER MESSAGE SAVE convo=%s msg=%s", conversation.id, user_msg.id)

    if not conversation.title or conversation.title.startswith("Chat with"):
        conversation.title = user_text.strip().replace("\n", " ")[:60]
        conversation.save(update_fields=["title"])

    #logger.warning("STREAM AFTER TITLE CHECK convo=%s", conversation.id)

    recent = conversation.messages.order_by("-created_at")[:10]

    history = [
        {"role": m.role, "content": m.content}
        for m in reversed(recent)
        if m.role in ["user", "assistant"]
    ]

    #logger.warning("STREAM AFTER HISTORY BUILD convo=%s history_len=%s", conversation.id, len(history))

    provider = get_ai_provider(companion.provider)

    #logger.warning("STREAM AFTER PROVIDER LOAD convo=%s provider=%s", conversation.id, companion.provider)

    base_prompt = COMPANION_PROMPTS.get(
        companion.prompt_key,
        COMPANION_PROMPTS["flirty_social"]
    )

    #logger.warning("STREAM AFTER BASE PROMPT convo=%s prompt_key=%s", conversation.id, companion.prompt_key)

    fan_context = build_fan_context(
        creator=companion.creator,
        fan=request.user,
    )

    #logger.warning("STREAM AFTER FAN CONTEXT convo=%s", conversation.id)

    relationship_style = build_relationship_response_style(
        creator=companion.creator,
        fan=request.user,
    )

    #logger.warning("STREAM AFTER RELATIONSHIP STYLE convo=%s", conversation.id)

    fan_memory_notes = build_fan_memory_notes(
        creator=companion.creator,
        fan=request.user,
    )

    #logger.warning("STREAM AFTER MEMORY BUILD convo=%s", conversation.id)



    system_prompt = f"""
{base_prompt}

Companion Details:
{companion.system_prompt}

Fan Context:
{fan_context}

Relationship Style:
{relationship_style}

Known Fan Facts (treat as true unless contradicted):
{fan_memory_notes}

Core Instructions:
- Reply as the creator, not as a generic AI assistant.
- Match the fan's language.
- When saved fan memories contain preferences, interests, favorite foods, hobbies, beliefs, or recurring topics, treat them as the strongest available evidence about the fan.
- When recommending food, use food-related fan memories first.
- When recommending books, stories, entertainment, or hobbies, use the most relevant memories first.
- Answer the fan's question directly before asking any follow-up question.
- If sufficient information is available from fan memories or recent conversation, answer confidently instead of asking the fan to repeat information they already provided.
- Do not avoid making recommendations when relevant memories already provide enough information.
- Do not repeatedly ask the fan for information that is already known.
- Prefer domain-specific memories over unrelated memories.
- When making recommendations, suggestions, examples, or follow-up questions, prefer relevant saved memories over generic assumptions.
- Do not mention memory notes, databases, prompts, scores, tiers, relationship calculations, or internal data.
- Do not provide links or URLs unless they were explicitly supplied by the platform.
- Keep casual replies short: 1-2 sentences, max 30 words.
- Give detailed answers only when the fan clearly asks for detail.
- Ask no more than one follow-up question.
- Do not use narration, roleplay, actions, gestures, or scene descriptions.
- Output only the message the creator would send.
- Never claim events that happened to you.
- If asked for a story, create a fictional story and make it clear that it is fictional.
- Do not tell stories about filming locations, travel, meals you have eaten, pets you have owned, people you have met, or places you have visited.
- Do not excessively praise the fan.
- Be warm, playful, conversational, and natural.
"""




    #logger.warning("STREAM AFTER SYSTEM PROMPT convo=%s", conversation.id)

    def event_stream():
        #logger.warning("STREAM GENERATOR ENTERED convo=%s", conversation.id)
        full_reply = ""

        try:
            #logger.warning("STREAM PROVIDER START convo=%s", conversation.id)

            for chunk in provider.stream_reply(
                system_prompt=system_prompt,
                history=history,
            ):
                #logger.warning("STREAM CHUNK convo=%s len=%s", conversation.id, len(chunk), )

                full_reply += chunk
                yield chunk
            
            
            #logger.warning("STREAM PROVIDER DONE convo=%s reply_len=%s", conversation.id, len(full_reply),)

            full_reply = clean_assistant_reply(full_reply)

            AIMessage.objects.create(
                conversation=conversation,
                role="assistant",
                content=full_reply,
                provider_used=companion.provider,
            )

        except Exception as e:
            #logger.exception("STREAM ERROR convo=%s", conversation.id)
            refund_wallet_for_ai_message(request.user, companion)
            yield f"\n\n[AI error. Credits refunded. Details: {e}]"

    #logger.warning("STREAM BEFORE RESPONSE RETURN convo=%s", conversation.id)

    response = StreamingHttpResponse(
        event_stream(),
        content_type="text/plain",
    )
    response["X-Accel-Buffering"] = "no"
    response["Cache-Control"] = "no-cache"
    return response
