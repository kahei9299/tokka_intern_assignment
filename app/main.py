import asyncio
import random
import httpx

from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text, delete, select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert

from db import engine, run_migrations, get_db
from pokeapi_client import fetch_pokemon_list, fetch_pokemon_details, fetch_location_name_for_pokemon, fetch_all_natures
from models import Pokemon, PokemonType
from utils import parse_limit_offset

app = FastAPI(title="Tokka Intern Pokemon Service")


@app.on_event("startup")
async def on_startup():
    """
    Application startup hook.

    This runs before the app starts serving requests.
    use it to run simple database migrations.
    """
    await run_migrations()


@app.get("/health")
async def health_check():
    """
    Health endpoint.

    Checks:
    - App is running
    - Database is reachable (simple SELECT 1)
    """
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {e!s}"

    return {
        "status": "ok",
        "db": db_status,
    }
    
@app.get("/debug/pokemon/list")
async def debug_pokemon_list(
    limit: int = Query(5, ge=1, le=50),
    offset: int = Query(0, ge=0),
):
    """
    Debug endpoint to verify we can talk to PokeAPI.

    - Accepts limit & offset as query params
    - Calls PokeAPI's /pokemon endpoint
    - Returns a trimmed version of the JSON

    Does not touch our database yet.
    """
    try:
        data = await fetch_pokemon_list(limit=limit, offset=offset)
    except Exception as e:
        # PokeAPI failed or network issue
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch from PokeAPI: {e!s}",
        )

    # Return the important bits for inspection
    return {
        "count": data.get("count"),
        "next": data.get("next"),
        "previous": data.get("previous"),
        "results": data.get("results"),
    }
    
@app.get("/pokemon/save")
async def save_pokemon(
    limit: str | None = None,
    offset: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Fetches Pokemon data from PokeAPI and saves them to the PostgreSQL database.

    Query params:
      - limit: optional, default 20, must be 1–100
      - offset: optional, default 0, must be >= 0

    On invalid limit/offset:
      - returns 400 with { "error": "Invalid limit or offset parameter" }

    On failure to fetch or save:
      - returns 500 with { "error": "Failed to fetch or save Pokemon data" }
    """
    # ---- Parse & validate query params using shared helper ----
    try:
        limit_value, offset_value = parse_limit_offset(
            limit_str=limit,
            offset_str=offset,
            default_limit=20,
            max_limit=100,
        )
    except ValueError:
        return JSONResponse(
            status_code=400,
            content={"error": "Invalid limit or offset parameter"},
        )
    # -----------------------------------------------------------

    try:
        # Step 1: fetch list from PokeAPI
        list_data = await fetch_pokemon_list(limit=limit_value, offset=offset_value)
        results = list_data.get("results", [])

        if not results:
            return {
                "message": "Successfully saved Pokemon to database",
                "saved_count": 0,
                "offset": offset_value,
                "limit": limit_value,
            }

        # Step 2: fetch details concurrently
        async with httpx.AsyncClient() as client:
            tasks = [
                fetch_pokemon_details(client, item["url"])
                for item in results
                if "url" in item
            ]
            details_list = await asyncio.gather(*tasks)

        saved_count = 0

        # Step 3: upsert Pokemon + types
        for details in details_list:
            if details is None:
                continue

            pokemon_id = details.get("id")
            name = details.get("name")
            base_experience = details.get("base_experience")
            height = details.get("height")
            order_value = details.get("order")
            weight = details.get("weight")
            location_area_encounters = details.get("location_area_encounters")
            types = details.get("types", [])

            if pokemon_id is None or name is None:
                continue

            stmt = pg_insert(Pokemon).values(
                pokemon_id=pokemon_id,
                name=name,
                base_experience=base_experience,
                height=height,
                order=order_value,
                weight=weight,
                location_area_encounters=location_area_encounters,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=[Pokemon.pokemon_id],
                set_={
                    "name": name,
                    "base_experience": base_experience,
                    "height": height,
                    "order": order_value,
                    "weight": weight,
                    "location_area_encounters": location_area_encounters,
                },
            )
            await db.execute(stmt)

            # Replace types for this Pokemon
            await db.execute(
                delete(PokemonType).where(PokemonType.pokemon_id == pokemon_id)
            )
            for entry in types:
                t = entry.get("type", {})
                type_name = t.get("name")
                type_url = t.get("url")
                if type_name and type_url:
                    await db.execute(
                        PokemonType.__table__.insert().values(
                            pokemon_id=pokemon_id,
                            type_name=type_name,
                            type_url=type_url,
                        )
                    )

            saved_count += 1

        # Step 4: commit once for the whole batch
        await db.commit()

        return {
            "message": "Successfully saved Pokemon to database",
            "saved_count": saved_count,
            "offset": offset_value,
            "limit": limit_value,
        }

    except Exception:
        # If anything failed during fetch or save, rollback and return spec-compliant 500
        try:
            await db.rollback()
        except Exception:
            pass

        return JSONResponse(
            status_code=500,
            content={"error": "Failed to fetch or save Pokemon data"},
        )

@app.get("/pokemon/locations/enrich")
async def enrich_pokemon_locations(
    db: AsyncSession = Depends(get_db),
):
    """
    Fetches location area encounter data for all Pokemon in the database
    by resolving their location_area_encounters URLs.

    Updates the 'location_name' column with the actual location area names
    from PokeAPI.

    Success:
      200, { "message": "Successfully enriched Pokemon location data",
             "updated_count": N }

    Failure:
      500, { "error": "Failed to fetch or update Pokemon location data" }
    """
    try:
        # 1) Get all Pokémon that have a non-null encounters URL.
        #    (Optionally restrict to those with NULL location_name to avoid redoing work.)
        result = await db.execute(
            select(Pokemon).where(
                Pokemon.location_area_encounters.is_not(None)
            )
        )
        pokemons: list[Pokemon] = result.scalars().all()

        if not pokemons:
            return {
                "message": "Successfully enriched Pokemon location data",
                "updated_count": 0,
            }

        # 2) Fetch locations concurrently
        async with httpx.AsyncClient() as client:
            tasks = [
                fetch_location_name_for_pokemon(
                    client, p.location_area_encounters
                )
                for p in pokemons
            ]
            location_names = await asyncio.gather(*tasks)

        # 3) Update DB
        updated_count = 0

        for p, loc_name in zip(pokemons, location_names):
            if not loc_name:
                # No encounters or fetch failure -> leave location_name as is
                continue

            if p.location_name == loc_name:
                # Already up-to-date
                continue

            await db.execute(
                update(Pokemon)
                .where(Pokemon.pokemon_id == p.pokemon_id)
                .values(location_name=loc_name)
            )
            updated_count += 1

        await db.commit()

        return {
            "message": "Successfully enriched Pokemon location data",
            "updated_count": updated_count,
        }

    except Exception:
        try:
            await db.rollback()
        except Exception:
            pass

        return JSONResponse(
            status_code=500,
            content={"error": "Failed to fetch or update Pokemon location data"},
        )

@app.get("/pokemon/generate-natures")
async def generate_pokemon_natures(
    db: AsyncSession = Depends(get_db),
):
    """
    Fetches all available natures from PokeAPI and randomly assigns one
    to each Pokemon in the database.

    Success:
      200, { "message": "Successfully assigned natures", "count": N }

    Failure:
      500, { "error": "Failed to assign natures" }
    """
    try:
        # 1) Load all Pokemon from DB
        result = await db.execute(select(Pokemon))
        pokemons: list[Pokemon] = result.scalars().all()

        if not pokemons:
            return {
                "message": "Successfully assigned natures",
                "count": 0,
            }

        # 2) Fetch all natures from PokeAPI
        async with httpx.AsyncClient() as client:
            natures = await fetch_all_natures(client)

        if not natures:
            # If we couldn't get any natures, treat as failure
            return JSONResponse(
                status_code=500,
                content={"error": "Failed to assign natures"},
            )

        # 3) Randomly assign one nature to each Pokemon
        assigned_count = 0

        for p in pokemons:
            random_nature = random.choice(natures)

            # Optionally skip if already assigned and you don't want to change
            # but the spec doesn't say to preserve old values, so we overwrite.
            await db.execute(
                update(Pokemon)
                .where(Pokemon.pokemon_id == p.pokemon_id)
                .values(nature=random_nature)
            )
            assigned_count += 1

        await db.commit()

        return {
            "message": "Successfully assigned natures",
            "count": assigned_count,
        }

    except Exception:
        try:
            await db.rollback()
        except Exception:
            pass

        return JSONResponse(
            status_code=500,
            content={"error": "Failed to assign natures"},
        )

@app.get("/pokemon/locations/by-type/{type}")
async def get_locations_by_type(
    type: str,
    limit: str | None = None,
    offset: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Returns location areas ranked by the number of Pokemon of the specified type
    that can be encountered there.

    Path params:
      - type: Pokemon type (e.g. 'fairy', 'water'), case-insensitive.

    Query params:
      - limit: optional, default 10, must be 1–50
      - offset: optional, default 0, must be >= 0

    Error 400:
      { "error": "Invalid Pokemon type, limit, or offset parameter" }

    Error 500:
      { "error": "Failed to fetch location data" }
    """
    # ---- Validate type and parse limit/offset ----
    try:
        type_value = type.strip().lower()
        if not type_value:
            # empty or whitespace-only type
            raise ValueError("empty type")

        # Reuse the same helper pattern as /pokemon/save
        limit_value, offset_value = parse_limit_offset(
            limit_str=limit,
            offset_str=offset,
            default_limit=10,
            max_limit=50,
        )
    except ValueError:
        return JSONResponse(
            status_code=400,
            content={"error": "Invalid Pokemon type, limit, or offset parameter"},
        )
    # ------------------------------------------------

    try:
        # 1) Validate that this type exists in our data at all.
        #    If no rows in pokemon_types with this type_name, treat as invalid type.
        exists_stmt = select(func.count()).select_from(PokemonType).where(
            PokemonType.type_name == type_value
        )
        exists_result = await db.execute(exists_stmt)
        type_count = exists_result.scalar_one() or 0
        if type_count == 0:
            return JSONResponse(
                status_code=400,
                content={"error": "Invalid Pokemon type, limit, or offset parameter"},
            )

        # 2) Compute total_locations = number of distinct location_name
        total_stmt = (
            select(func.count(func.distinct(Pokemon.location_name)))
            .join(PokemonType, PokemonType.pokemon_id == Pokemon.pokemon_id)
            .where(
                PokemonType.type_name == type_value,
                Pokemon.location_name.is_not(None),
            )
        )
        total_result = await db.execute(total_stmt)
        total_locations = total_result.scalar_one() or 0

        # 3) Fetch paginated locations with aggregated pokemon_count
        locations_stmt = (
            select(
                Pokemon.location_name.label("location_name"),
                func.count().label("pokemon_count"),
            )
            .join(PokemonType, PokemonType.pokemon_id == Pokemon.pokemon_id)
            .where(
                PokemonType.type_name == type_value,
                Pokemon.location_name.is_not(None),
            )
            .group_by(Pokemon.location_name)
            .order_by(
                func.count().desc(),        # most Pokémon first
                Pokemon.location_name.asc() # tie-breaker by name
            )
            .limit(limit_value)
            .offset(offset_value)
        )
        locations_result = await db.execute(locations_stmt)
        rows = locations_result.all()

        locations = [
            {
                "location_name": row.location_name,
                "pokemon_count": row.pokemon_count,
            }
            for row in rows
        ]

        # 4) Spec-compliant 200 response
        return {
            "type": type_value,
            "total_locations": total_locations,
            "limit": limit_value,
            "offset": offset_value,
            "locations": locations,
        }

    except Exception:
        # Any unexpected DB failure → spec-compliant 500
        return JSONResponse(
            status_code=500,
            content={"error": "Failed to fetch location data"},
        )
