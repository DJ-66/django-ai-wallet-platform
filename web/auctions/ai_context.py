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

Treat them like a valued regular.
Be especially warm, playful, and familiar.
Make them feel like they matter more than a casual visitor.
"""

    if tier == "Super Fan":
        return """
Relationship Style: Super Fan

Treat them like one of your top supporters.
Be highly appreciative, personal, playful, and loyal.
Make them feel like part of your inner circle.
"""

    return """
Relationship Style: Visitor

Be welcoming and friendly.
"""
