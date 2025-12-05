import httpx

POKEAPI_BASE_URL = "https://pokeapi.co/api/v2"


async def fetch_pokemon_list(limit: int = 20, offset: int = 0) -> dict:
    """
    Fetch a page of Pokemon from PokeAPI.

    Calls:
        GET https://pokeapi.co/api/v2/pokemon?limit={limit}&offset={offset}

    Returns:
        Parsed JSON as a Python dict.
    """
    url = f"{POKEAPI_BASE_URL}/pokemon"
    params = {"limit": limit, "offset": offset}

    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params, timeout=10.0)
        resp.raise_for_status()  # raises if status is 4xx/5xx
        return resp.json()

async def fetch_pokemon_details(client: httpx.AsyncClient, url: str) -> dict | None:
    """
    Fetch detailed Pokemon info from a given PokeAPI URL.

    Returns:
        Parsed JSON dict, or None if the request fails.
    """
    try:
        resp = await client.get(url, timeout=10.0)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError:
        # In this assignment, we simply skip failed ones
        return None

async def fetch_location_name_for_pokemon(
    client: httpx.AsyncClient,
    encounters_url: str | None,
) -> str | None:
    """
    Given a location_area_encounters URL, fetch the encounter data and
    return the first location_area.name.

    If there are no encounters or any error occurs, return None.

    We intentionally pick the *first* location only, since the spec only
    requires a single 'location_name' per Pokemon.
    """
    if not encounters_url:
        return None

    try:
        resp = await client.get(encounters_url, timeout=10.0)
        resp.raise_for_status()
    except httpx.HTTPError:
        return None

    try:
        data = resp.json()
    except ValueError:
        return None

    if not isinstance(data, list) or not data:
        return None

    first = data[0]
    loc = first.get("location_area", {})
    name = loc.get("name")
    return name