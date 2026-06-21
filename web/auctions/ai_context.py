from .models import AICreatorMemory


def build_fan_context(creator, fan):

    memory = (
        AICreatorMemory.objects
        .filter(
            creator=creator,
            fan=fan
        )
        .first()
    )

    if not memory:
        return "First time visitor."

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
