"""
Euromillions results fetcher.

Data source: web scraping of euro-millions.com/results
  - The main /results page returns the ~16 most recent draws
  - Individual date pages work for specific past draws (only if that date had a draw)

All public functions are synchronous for APScheduler compatibility.
"""

import logging
import re
from datetime import date, datetime

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

EURO_MILLIONS_BASE = "https://www.euro-millions.com"
SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
})


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_result_row(tr: BeautifulSoup) -> dict | None:
    """Parse a <tr class="resultRow"> from euro-millions.com into a draw dict."""
    try:
        # --- Date ---
        date_td = tr.find("td", class_="date")
        if not date_td:
            return None
        date_link = date_td.find("a")
        date_text = date_link.get_text(strip=True) if date_link else date_td.get_text(strip=True)
        # e.g. "Friday29thMay 2026" or "Friday 29th May 2026"
        m = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s*([A-Za-z]+)\s+(\d{4})", date_text)
        if not m:
            return None
        draw_date = datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", "%d %B %Y").date()

        # --- Numbers & Stars ---
        numbers: list[int] = []
        stars: list[int] = []
        for li in tr.find_all("li", class_="resultBall"):
            val = li.get_text(strip=True)
            if not val.isdigit():
                continue
            if "lucky-star" in li.get("class", []):
                stars.append(int(val))
            else:
                numbers.append(int(val))

        if len(numbers) != 5 or len(stars) != 2:
            logger.debug(f"Row for {date_text}: {len(numbers)} numbers, {len(stars)} stars – skip")
            return None

        # --- Jackpot ---
        jackpot = 0.0
        jackpot_td = tr.find("td", attrs={"data-title": "Jackpot"})
        if jackpot_td:
            jp_text = jackpot_td.get_text(strip=True)
            jp_clean = re.sub(r"[^\d.]", "", jp_text)
            if jp_clean:
                jackpot = float(jp_clean)

        return {
            "date": draw_date.isoformat(),
            "numbers": sorted(numbers),
            "stars": sorted(stars),
            "prize_total": jackpot,
        }
    except Exception as e:
        logger.debug(f"Failed to parse result row: {e}")
        return None


def _parse_pt_prize_breakdown(soup: BeautifulSoup) -> dict:
    """Parse the Portugal (#PrizePT) prize-per-winner breakdown table.

    Returns a dict keyed by "M+S" (e.g. "5+2") -> prize per winner (float).
    Euromillions prizes vary every draw, so this is the authoritative source
    for the real prize amounts of a given draw.
    """
    section = soup.find(id="PrizePT")
    if not section:
        return {}
    # The table sits inside the section div
    table = section.find("table")
    if not table:
        return {}

    prizes: dict[str, float] = {}
    for tr in table.find_all("tr"):
        name_span = tr.find("span", class_="prizeName")
        if not name_span:
            continue
        balls = [b.get_text(strip=True) for b in name_span.find_all("span", class_="ball")]
        stars = [s.get_text(strip=True) for s in name_span.find_all("span", class_="star")]
        if not balls:
            continue
        mn = int(balls[0])
        ms = int(stars[0]) if stars else 0
        key = f"{mn}+{ms}"

        prize_td = tr.find("td", attrs={"data-title": "Prize Per Winner"})
        if not prize_td:
            continue
        raw = prize_td.get_text(strip=True).replace("&euro;", "").replace("€", "")
        raw = re.sub(r"[^0-9.]", "", raw)
        try:
            prizes[key] = float(raw) if raw else 0.0
        except ValueError:
            prizes[key] = 0.0
    return prizes


def _scrape_draw_detail(url: str, retries: int = 3) -> dict:
    """Fetch a single draw detail page and return its Portugal prize breakdown.

    Retries with a short backoff because the source occasionally returns
    403 (rate-limiting / recaptcha challenge) on individual detail pages.
    Returns {} if the breakdown can't be fetched after retries.
    """
    for attempt in range(1, retries + 1):
        try:
            resp = SESSION.get(url, timeout=15)
            if resp.status_code == 403 and attempt < retries:
                logger.debug(f"403 on {url} (attempt {attempt}), retrying...")
                import time
                time.sleep(2 * attempt)
                continue
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            return _parse_pt_prize_breakdown(soup)
        except Exception as e:
            if attempt < retries:
                import time
                time.sleep(2 * attempt)
                continue
            logger.warning(f"Failed to fetch draw detail {url}: {e}")
            return {}
    return {}


def _scrape_results_page(url: str, retries: int = 3) -> list[dict]:
    """Fetch a results page and return parsed draw dicts (most recent first).
    Returns empty list on any error (404, timeout, parse failure, etc.).
    Retries on transient 403s (rate-limiting) with a short backoff.
    """
    for attempt in range(1, retries + 1):
        try:
            resp = SESSION.get(url, timeout=15)
            if resp.status_code == 403 and attempt < retries:
                logger.debug(f"403 on {url} (attempt {attempt}), retrying...")
                import time
                time.sleep(2 * attempt)
                continue
            if resp.status_code == 404:
                logger.debug(f"No results page at {url} (404)")
                return []
            resp.raise_for_status()
            break
        except requests.HTTPError as e:
            logger.warning(f"HTTP error fetching {url}: {e}")
            return []
        except Exception as e:
            if attempt < retries:
                import time
                time.sleep(2 * attempt)
                continue
            logger.warning(f"Failed to fetch {url}: {e}")
            return []
    else:
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table")
    if not table:
        logger.warning(f"No results table found at {url}")
        return []

    draws: list[dict] = []
    for tr in table.find_all("tr", class_="resultRow"):
        parsed = _parse_result_row(tr)
        if parsed:
            draws.append(parsed)

    logger.info(f"Scraped {len(draws)} draws from {url}")
    return draws


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_latest_draw() -> dict | None:
    """Fetch the most recent Euromillions draw."""
    draws = _scrape_results_page(f"{EURO_MILLIONS_BASE}/results")
    return draws[0] if draws else None


def fetch_draws_since(since: date) -> list[dict]:
    """Fetch draws from the main results page, filtering to dates >= since."""
    all_draws = _scrape_results_page(f"{EURO_MILLIONS_BASE}/results")
    return [d for d in all_draws if date.fromisoformat(d["date"]) >= since]


def fetch_all_draws_last_n_months(months: int = 6) -> list[dict]:
    """Fetch draws from the last N months using year history pages."""
    today = date.today()
    since = today
    for _ in range(months):
        if since.month == 1:
            since = since.replace(year=since.year - 1, month=12)
        else:
            since = since.replace(month=since.month - 1)

    # Determine which year pages we need
    years_needed = set()
    d = since
    while d <= today:
        years_needed.add(d.year)
        # advance to next month
        if d.month == 12:
            d = d.replace(year=d.year + 1, month=1)
        else:
            d = d.replace(month=d.month + 1)

    all_draws: list[dict] = []
    seen: set[str] = set()
    for year in sorted(years_needed):
        url = f"{EURO_MILLIONS_BASE}/results-history-{year}"
        for draw in _scrape_results_page(url):
            if draw["date"] >= since.isoformat() and draw["date"] not in seen:
                all_draws.append(draw)
                seen.add(draw["date"])

    all_draws.sort(key=lambda d: d["date"], reverse=True)
    return all_draws


def fetch_draws_for_date(date_str: str) -> dict | None:
    """Fetch a specific draw by date (YYYY-MM-DD)."""
    d = date.fromisoformat(date_str)
    url = f"{EURO_MILLIONS_BASE}/results/{d.strftime('%d-%m-%Y')}"
    draws = _scrape_results_page(url)
    return draws[0] if draws else None


def fetch_draw_prizes(date_str: str) -> dict:
    """Fetch the Portugal prize-per-winner breakdown for a specific draw date.

    Returns a dict keyed by "M+S" (e.g. "5+2") -> prize per winner (float).
    Empty dict if the breakdown page is unavailable.
    """
    d = date.fromisoformat(date_str)
    url = f"{EURO_MILLIONS_BASE}/results/{d.strftime('%d-%m-%Y')}"
    return _scrape_draw_detail(url)


# Backwards-compatibility alias
async def fetch_latest_draw_async() -> dict | None:
    return fetch_latest_draw()
