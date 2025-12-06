# app/schemas.py
from typing import List
from pydantic import BaseModel


# ---- Shared error model (for docs / consistency) ----
class ErrorResponse(BaseModel):
    error: str


# ---- /pokemon/save ----
class SavePokemonResponse(BaseModel):
    message: str
    saved_count: int
    offset: int
    limit: int


# ---- /pokemon/locations/enrich ----
class EnrichLocationsResponse(BaseModel):
    message: str
    updated_count: int


# ---- /pokemon/generate-natures ----
class GenerateNaturesResponse(BaseModel):
    message: str
    count: int


# ---- /pokemon/locations/by-type/{type} ----
class LocationEntry(BaseModel):
    location_name: str
    pokemon_count: int


class LocationsByTypeResponse(BaseModel):
    type: str
    total_locations: int
    limit: int
    offset: int
    locations: List[LocationEntry]
