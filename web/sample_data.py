SAMPLE_GIGS = (
    {
        "title": "Move dorm boxes",
        "category": "delivery",
        "pay": "$40",
        "location": "North Campus",
        "date": "2026-05-03",
        "description": "Help carry packed boxes from a dorm room to a storage unit.",
        "poster_id": "sample-poster",
    },
    {
        "title": "Calculus study session",
        "category": "tutoring",
        "pay": "$25/hr",
        "location": "Library",
        "date": "2026-05-04",
        "description": "Review derivatives and practice problems before a midterm.",
        "poster_id": "sample-poster",
    },
    {
        "title": "Walk a senior dog",
        "category": "pet-care",
        "pay": "$20",
        "location": "Maple Street",
        "date": "2026-05-05",
        "description": "Take a calm dog on a 30 minute evening walk.",
        "poster_id": "sample-poster",
    },
    {
        "title": "Set up event chairs",
        "category": "event-help",
        "pay": "$55",
        "location": "Student Center",
        "date": "2026-05-06",
        "description": "Arrange chairs and tables before a campus club event.",
        "poster_id": "sample-poster",
    },
    {
        "title": "Fix apartment Wi-Fi",
        "category": "tech-support",
        "pay": "$35",
        "location": "Oak Apartments",
        "date": "2026-05-07",
        "description": "Troubleshoot a router and reconnect a laptop and printer.",
        "poster_id": "sample-poster",
    },
    {
        "title": "Weed a small garden",
        "category": "yard-work",
        "pay": "$45",
        "location": "Elm Avenue",
        "date": "2026-05-08",
        "description": "Clear weeds from two raised beds and bag the yard waste.",
        "poster_id": "sample-poster",
    },
)


def seed_sample_gigs(repository) -> None:
    if repository.list_open_gigs():
        return

    for gig in SAMPLE_GIGS:
        repository.create_gig(**gig)
