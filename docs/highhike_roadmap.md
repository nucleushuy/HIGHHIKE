# Highhike Spark + Flask Roadmap (Draft)

## Overview
Highhike is a trail discovery and management app that will be rebuilt with Spark for scalable data processing while using Flask for the web layer. The system will ingest cleaned trail data, support search and filtering, track user progress, compute achievements, and provide graph-ready analytics. The current SQLite databases will be used as a starting point for Flask, with a planned migration to Flask-SQLAlchemy models (lecture 19 style).

## Goals
- Fast, flexible trail search and filtering.
- Display trail metadata and images.
- Support add/edit updates to trail records.
- Track user trail completions and progress.
- Compute achievements and analytics.
- Export cleaned CSV and/or persist in a database.
- Prepare a scalable Spark pipeline.

## Data Sources
- `cleaned_trails/cleaned_ca_trails.csv`
- Key fields: `ID`, `name`, `city_name`, `area_name`, `length_miles`, `difficulty_rating`, `avg_rating`, `features`, `activities`, `url`, etc.

## Database Strategy (Two DBs)
1) **trails_db**
- Stores cleaned trail catalog.
- Used by Flask for search and trail detail views.

2) **users_db**
- Stores user progress, completions, ratings, achievements.
- Used by Flask for profiles and analytics.

## Current Starting Point
- Use the existing SQLite DB scripts to seed both DBs.
- Flask app can query these DBs directly as a working baseline.
- Later migrate models to Flask-SQLAlchemy (lecture 19 pattern).

## Spark Pipeline (High-Level)
- Ingest CSV -> normalize types -> parse list fields -> clean URLs.
- Persist to Parquet/Delta for fast analytics.
- Export cleaned CSV for DB seeding.

## Search + Filtering
- Text search: `name`, `city_name`, `area_name`, `features`, `activities`.
- Numeric filters: difficulty, length, rating, elevation.
- Sorting: popularity, rating, length, difficulty, name.

## Update Workflow
- Add or edit trails by `trail_id`.
- Validate and coerce input types.
- Persist updates and re-export cleaned CSV.

## User-Created Route + Difficulty Feedback
- User inputs: `distance_miles`, `elevation_gain_ft`, optional `terrain_type`, optional `notes`.
- System computes:
  - `steepness_ftmi = elevation_gain_ft / max(distance_miles, tiny)`
  - `difficulty_category` using Jennie's formula and thresholds.
- Confirmation prompt:
  - "We estimate this trail is Moderate. Does that feel right?"
  - Buttons: `Yes`, `No - felt easier`, `No - felt harder`
  - Optional text: "Why?" (terrain, elevation concentration, exposure, weather, etc.)
- Stored feedback fields:
  - `difficulty_estimate`
  - `difficulty_feedback` (enum: accurate/easier/harder)
  - `feedback_notes` (text)
  - `terrain_type` (optional)
- Usage of feedback:
  - Show user history (how often their feedback differs).
  - Aggregate signals to refine thresholds later.

## Achievements (Examples)
- Trails completed: 10, 25, 50, 100.
- Total distance: 50, 100, 250 miles.
- Total elevation: 10k, 25k, 50k ft.
- Difficulty milestones: X strenuous trails.
- Streaks: N consecutive weeks with completions.

## Graphs
- Line chart: completions over time.
- Line chart: elevation gained over time.
- Bar chart: difficulty distribution.
- Pie charts: difficulty category, route type, area category.

## Next Steps (Proposed)
1) Confirm final DB schema for trails and users DBs.
2) Build Spark cleaning + export job.
3) Seed SQLite DBs from cleaned CSV.
4) Add Flask endpoints for search, detail, completion, achievements.
5) Migrate to Flask-SQLAlchemy models (lecture 19 alignment).
