JOB_TAGS = (
    "tutoring",
    "delivery",
    "pet-care",
    "event-help",
    "tech-support",
    "yard-work",
)

TAG_LABELS = {
    "tutoring": "Tutoring",
    "delivery": "Delivery",
    "pet-care": "Pet care",
    "event-help": "Event help",
    "tech-support": "Tech support",
    "yard-work": "Yard work",
}


def normalize_tags(values):
    """Return known tags once, preserving the app's display order."""
    requested = {value.strip().lower() for value in values if value and value.strip()}
    return [tag for tag in JOB_TAGS if tag in requested]
