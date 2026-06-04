import httpx
import json
import logging
from datetime import date, datetime
from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def fetch_latest_draw() -> dict | None:
    """Fetch the latest Euromillions draw from external API. Returns None on failure."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            # Try euromillions-api.com
            try:
                url = f"{settings.EUROMILLIONS_API_URL}/draws/latest"
                response = await client.get(url)
                if response.status_code == 200:
                    data = response.json()
                    return _parse_response(data)
            except Exception as e:
                logger.warning(f"Primary API failed: {e}")

            # Fallback: try alternative API format
            try:
                url = f"{settings.EUROMILLIONS_API_URL}/latest"
                response = await client.get(url)
                if response.status_code == 200:
                    data = response.json()
                    return _parse_response(data)
            except Exception as e:
                logger.warning(f"Secondary API failed: {e}")

            # Fallback: try another known API
            try:
                url = "https://api.*******.com/api/v1/euromillions/latest"
                response = await client.get(url)
                if response.status_code == 200:
                    data = response.json()
                    return _parse_response(data)
            except Exception as e:
                logger.warning(f"Tertiary API failed: {e}")

    except Exception as e:
        logger.error(f"All API attempts failed: {e}")

    return None


async def fetch_draws_since(since_date: date) -> list[dict]:
    """Fetch all draws since a given date. Returns list of parsed draw dicts."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            url = f"{settings.EUROMILLIONS_API_URL}/draws"
            params = {"since": since_date.isoformat()}
            response = await client.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    return [_parse_response(d) for d in data if _parse_response(d)]
                elif isinstance(data, dict) and "draws" in data:
                    return [_parse_response(d) for d in data["draws"] if _parse_response(d)]
    except Exception as e:
        logger.error(f"Failed to fetch draws since {since_date}: {e}")

    return []


def _parse_response(data: dict) -> dict | None:
    """Parse API response into our draw format. Handles various API formats."""
    try:
        # Format 1: euromillions-api.com style
        if "numbers" in data and "stars" in data:
            return {
                "date": _parse_date(data.get("date", data.get("draw_date", ""))),
                "numbers": sorted(data["numbers"][:5]),
                "stars": sorted(data["stars"][:2]),
                "prize_total": float(data.get("jackpot", data.get("prize_total", 0))),
            }

        # Format 2: alternative format with "results" key
        if "results" in data:
            r = data["results"]
            return {
                "date": _parse_date(data.get("date", "")),
                "numbers": sorted(r.get("numbers", [])[:5]),
                "stars": sorted(r.get("stars", [])[:2]),
                "prize_total": float(data.get("jackpot", 0)),
            }

        # Format 3: direct number fields
        nums = data.get("n", data.get("nums", data.get("numbers", [])))
        strs = data.get("s", data.get("star", data.get("stars", [])))
        if len(nums) >= 5 and len(strs) >= 2:
            return {
                "date": _parse_date(str(data.get("date", data.get("draw_date", "")))),
                "numbers": sorted(nums[:5]),
                "stars": sorted(strs[:2]),
                "prize_total": float(data.get("jackpot", 0)),
            }

        logger.warning(f"Unrecognised API format: {json.dumps(data)[:200]}")
        return None
    except Exception as e:
        logger.error(f"Error parsing response: {e}")
        return None


def _parse_date(date_str: str) -> date:
    """Parse date string in various formats."""
    if not date_str:
        return date.today()
    for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y%m%d"]:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return date.today()
