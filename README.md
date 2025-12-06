# Tokka Labs Internship Assignment — Pokémon Data Service

A fully asynchronous, Docker-based Pokémon data ingestion and analytics service built with **FastAPI**, **PostgreSQL**, and **SQLAlchemy**.

This project integrates with the public **PokeAPI**, performs data ingestion, normalization, enrichment, and exposes REST endpoints that satisfy all four tasks specified in the assignment.

---

# Tech Stack

### Backend Framework
- **FastAPI** — high-performance async Python API framework  
- **Uvicorn** — ASGI server  

### Database
- **PostgreSQL 16** — exposed at port **5433**  
- **asyncpg** — async PostgreSQL driver  
- **SQLAlchemy 2.0** — async ORM + query builder  

### HTTP Client
- **httpx** — async HTTP client for PokeAPI requests  

### Containerization
- **Docker & Docker Compose**  
- automatic database healthcheck  
- auto-migrations on startup  

---

# How to Run

## 1. Clone the repository

```bash
git clone <your_repo_url>
cd tokka_intern_assignment
```

## 2. Start the application

```bash
docker-compose up --build
```

### Service Ports

| Service | Port | Description |
|---------|------|-------------|
| pokemon_service | 8080 | FastAPI backend |
| pokemon_db | 5433 | PostgreSQL database |

**API root:**
- http://localhost:8080

**Swagger UI:**
- http://localhost:8080/docs

---

# 🗄️ Database Schema

## `pokemon`

Main Pokémon table storing cleaned data.

| Column | Type | Description |
|--------|------|-------------|
| pokemon_id | INTEGER PK | Pokémon ID from PokeAPI |
| name | TEXT | Name |
| base_experience | INTEGER | XP |
| height | INTEGER | Height |
| "order" | INTEGER | PokeAPI order |
| weight | INTEGER | Weight |
| location_area_encounters | TEXT | URL from PokeAPI |
| location_name | TEXT | Enriched location name |
| nature | TEXT | Randomly assigned nature |

## `pokemon_types`

Normalized mapping of Pokémon → Types.

| Column | Type | Description |
|--------|------|-------------|
| pokemon_id | INTEGER FK | references pokemon |
| type_name | TEXT | e.g., "fairy" |
| type_url | TEXT | PokeAPI URL |

**Composite PK:** `(pokemon_id, type_name)`

---

# API Endpoints (Assignment Tasks)

## Task 1 — Save Pokémon

**GET** `/pokemon/save`

Fetches Pokémon from PokeAPI and saves/upserts them into PostgreSQL.

**Query Parameters:**
- `limit` (default 20, max 100)
- `offset` (default 0)

### Example Successful Response

```json
{
  "message": "Successfully saved Pokemon to database",
  "saved_count": 20,
  "offset": 0,
  "limit": 20
}
```

### Errors

```json
{ "error": "Invalid limit or offset parameter" }
```

```json
{ "error": "Failed to fetch or save Pokemon data" }
```

### Sample cURL Commands — Task 1

**Save 20 Pokémon:**
```bash
curl "http://localhost:8080/pokemon/save?limit=20&offset=0"
```

**Save 50 Pokémon starting at offset 100:**
```bash
curl "http://localhost:8080/pokemon/save?limit=50&offset=100"
```

**Invalid parameters:**
```bash
curl "http://localhost:8080/pokemon/save?limit=0&offset=-1"
```

---

## Task 2 — Enrich Pokémon Locations

**GET** `/pokemon/locations/enrich`

Resolves location encounter URLs and stores the first location name inside `location_name`.

### Example Response

```json
{
  "message": "Successfully enriched Pokemon location data",
  "updated_count": 120
}
```

### Error

```json
{ "error": "Failed to fetch or update Pokemon location data" }
```

### Sample cURL Commands — Task 2

```bash
curl "http://localhost:8080/pokemon/locations/enrich"
```

**Recommended workflow:**
```bash
curl "http://localhost:8080/pokemon/save?limit=100&offset=0"
curl "http://localhost:8080/pokemon/locations/enrich"
```

---

## Task 3 — Generate Pokémon Natures

**GET** `/pokemon/generate-natures`

Fetches all available natures from PokeAPI and assigns one randomly to each Pokémon.

### Example Response

```json
{
  "message": "Successfully assigned natures",
  "count": 150
}
```

### Error

```json
{ "error": "Failed to assign natures" }
```

### Sample cURL Commands — Task 3

**Assign natures:**
```bash
curl "http://localhost:8080/pokemon/generate-natures"
```

**Check via SQL:**
```sql
SELECT pokemon_id, name, nature
FROM pokemon
ORDER BY pokemon_id
LIMIT 20;
```

---

## Task 4 — Get Locations by Pokémon Type

**GET** `/pokemon/locations/by-type/{type}`

Returns all locations where Pokémon of the given type can be found, ordered by count.

**Query Parameters:**
- `limit` (default 10, max 50)
- `offset` (default 0)

### Example Response

```json
{
  "type": "fairy",
  "total_locations": 4,
  "limit": 10,
  "offset": 0,
  "locations": [
    {
      "location_name": "cerulean-cave-2f",
      "pokemon_count": 1
    }
  ]
}
```

### Errors

```json
{ "error": "Invalid Pokemon type, limit, or offset parameter" }
```

```json
{ "error": "Failed to fetch location data" }
```

### Sample cURL Commands — Task 4

**Fairy type:**
```bash
curl "http://localhost:8080/pokemon/locations/by-type/fairy?limit=10&offset=0"
```

**Water type:**
```bash
curl "http://localhost:8080/pokemon/locations/by-type/water?limit=5&offset=0"
```

**Invalid type:**
```bash
curl "http://localhost:8080/pokemon/locations/by-type/notatype"
```

**Invalid params:**
```bash
curl "http://localhost:8080/pokemon/locations/by-type/fire?limit=-1"
```

---

# Optional PostgreSQL Inspection Commands

**Connect to DB:**
```bash
psql -h localhost -p 5433 -U postgres -d tokka_intern_assignment
```

**View Pokémon rows:**
```sql
SELECT pokemon_id, name, location_name, nature
FROM pokemon
ORDER BY pokemon_id
LIMIT 20;
```

**View Pokémon types:**
```sql
SELECT *
FROM pokemon_types
ORDER BY pokemon_id, type_name
LIMIT 20;
```

---

# Automatic Migrations & Startup Reliability

## Features

- Auto-migrations run on app startup
- Idempotent migrations (`IF NOT EXISTS`)
- Database readiness ensured through:
  - Retry logic with exponential backoff
  - Docker healthchecks
  - `depends_on: condition: service_healthy`

## Retry Logic Example

- **Attempts:** 10
- **Backoff:** 2s → 4s → 8s → 16s → … (max 30s)
- Ensures DB is ready before migrations execute.

---

# Design Decisions

## Asynchronous Architecture

Handles many PokeAPI requests concurrently using `asyncio` + `httpx`.

## Normalized Types Table

`pokemon_types` enables efficient filtering and grouping used for Task 4.

## Pre-Enrichment of Locations

Preprocessing improves performance and avoids external API calls for analytics endpoints.

## Idempotent Migrations

No Alembic required — simple, predictable startup behavior.

## Consistent Error Format

All errors use:
```json
{ "error": "<message>" }
```

# References & Tools Used

FastAPI Documentation — routing, dependency injection, error handling

PostgreSQL Documentation — schema design, ON CONFLICT rules

SQLAlchemy ORM Documentation — models, relationships, upserts

HTTPX Documentation — async external API calls and concurrency

Docker & Docker Compose Documentation — containerization and service orchestration

PokeAPI v2 Documentation — response formats for Pokémon, types, locations

ChatGPT — used as a technical assistant for architectural brainstorming, documentation drafting, and validating reasoning around async patterns and database design.

Cursor AI — assisted in navigating, refactoring, and understanding complex sections of the codebase.