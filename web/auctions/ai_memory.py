from django.contrib.auth.models import User

from .models import AICreatorMemory


def touch_ai_creator_memory(
    *,
    creator: User,
    fan: User,
    event_type: str,
    credits: int = 0,
) -> AICreatorMemory | None:
    """
    Create/update lightweight AI creator memory for a creator/fan relationship.
    """

    if not creator or not fan:
        return None

    if creator == fan:
        return None

    memory, _created = AICreatorMemory.objects.get_or_create(
        creator=creator,
        fan=fan,
    )

    if event_type == "tip":
        memory.total_tips += 1
        memory.total_tip_credits += max(credits, 0)

    elif event_type == "unlock":
        memory.total_unlocks += 1
        memory.total_unlock_credits += max(credits, 0)

    elif event_type == "fan":
        memory.fan_status = True

    elif event_type == "dm":
        memory.conversation_count += 1

    memory.save()
    return memory
