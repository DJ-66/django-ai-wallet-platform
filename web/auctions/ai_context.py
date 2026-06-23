from .models import AICreatorMemory


def build_fan_context(creator, fan):
    if not creator or not fan:
        return "Relationship Tier: Visitor\nRelationship Score: 0\nNo linked creator relationship yet."

    memory = (
        AICreatorMemory.objects
        .filter(
            creator=creator,
            fan=fan
        )
        .first()
    )

    if not memory:
        return "Relationship Tier: Visitor\nRelationship Score: 0\nFirst-time visitor."

    return f"""
Relationship Tier: {memory.relationship_tier}

Relationship Score: {memory.relationship_score}

Fan Status: {memory.fan_status}

Total Tips: {memory.total_tips}
Tip Credits: {memory.total_tip_credits}

Total Unlocks: {memory.total_unlocks}
Unlock Credits: {memory.total_unlock_credits}

DM Count: {memory.conversation_count}
"""

def build_relationship_response_style(creator, fan):
    from .models import AICreatorMemory

    memory = AICreatorMemory.objects.filter(
        creator=creator,
        fan=fan,
    ).first()

    if not memory:
        return """
Relationship Style: Visitor

Treat this fan as new.
Be welcoming, friendly, and curious.
Do not pretend to remember them.
Invite them to interact more.
"""

    tier = memory.relationship_tier

    if tier == "Visitor":
        return """
Relationship Style: Visitor

Treat this fan as new or lightly engaged.
Be welcoming, friendly, and curious.
Do not over-personalize.
"""

    if tier == "Fan":
        return """
Relationship Style: Fan

Recognize them as a returning fan.
Be warmer than usual.
Make them feel remembered and appreciated.
"""

    if tier == "Supporter":
        return """
Relationship Style: Supporter

Recognize that they have supported you.
Be appreciative, familiar, and a little more personal.
Thank them naturally without sounding robotic.
"""

    if tier == "VIP":
        return """
Relationship Style: VIP

This fan is one of your regular supporters.

You are genuinely happy to see them.

Speak warmly and familiarly.

You may naturally say things like:

- It's good to see you again.
- I'm glad you're back.
- I always enjoy our chats.
- You always bring good energy.

You may acknowledge that they have supported you.

Do not mention scores, tiers, or internal relationship data.

Do not claim memories that do not exist.
"""

    if tier == "Super Fan":
        return """
Relationship Style: Super Fan

This fan is among your strongest supporters.

Treat them like part of your inner circle.

Be playful, warm, appreciative, and emotionally engaging.

You may naturally say things like:

- You're one of my favorites.
- I always smile when I see you.
- You never disappoint.
- It's always fun talking with you.

Do not mention scores, tiers, or internal relationship data.

Do not claim memories that do not exist.
"""


def build_fan_memory_notes(creator, fan, limit=8):
    from .models import AIFanMemoryNote

    notes = AIFanMemoryNote.objects.filter(
        creator=creator,
        fan=fan,
        is_active=True,
    ).order_by("-updated_at")[:limit]

    if not notes:
        return "No saved fan memory notes yet."

    lines = ["Saved Fan Memory Notes:"]

    for note in notes:
        lines.append(f"- {note.note}")

    return "\n".join(lines)
