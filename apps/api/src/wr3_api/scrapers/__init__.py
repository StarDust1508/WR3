"""Real-world security-incident scrapers.

Each `*_scrape()` function returns `list[ScrapedIncident]` and does ONLY
fetching + parsing — it does NOT touch the DB, does NOT embed, does NOT
dedup. Persistence happens in incident_repository.

All sources are public, free, and require no API key. URLs are pinned in
each scraper module so swapping them is one commit.
"""

from wr3_api.scrapers.defillama import scrape_defillama_hacks
from wr3_api.scrapers.rekt import scrape_rekt
from wr3_api.scrapers.shared import ScrapedIncident
from wr3_api.scrapers.slowmist import scrape_slowmist

__all__ = [
    "ScrapedIncident",
    "scrape_defillama_hacks",
    "scrape_rekt",
    "scrape_slowmist",
]
