from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request, send_file
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func

db = SQLAlchemy()


def estimate_difficulty_category(length_miles: float, elevation_gain_ft: float) -> str:
    # Lightweight heuristic so new trails get a sensible difficulty label.
    score = (length_miles * elevation_gain_ft * 2) ** 0.5
    if score < 50:
        return "easy"
    if score <= 100:
        return "moderate"
    if score <= 150:
        return "moderately strenuous"
    if score <= 200:
        return "strenuous"
    return "very strenuous"


def _coerce_float(value: object) -> float | None:
    # Accept strings from JSON and fail softly on bad input.
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_int(value: object) -> int | None:
    # Same idea as _coerce_float, but for integer fields.
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_list(value: object) -> list[str]:
    # The DB stores list fields as pickles; keep it robust and return a clean list.
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if item]
    return []


def create_app() -> Flask:
    app = Flask(__name__)
    base_dir = Path(__file__).resolve().parent
    trails_db_path = base_dir / "trail_schema.db"
    users_db_path = base_dir / "users_trails_schema.db"

    # Two DBs: one for the trail catalog, one for user progress.
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{trails_db_path}"
    app.config["SQLALCHEMY_BINDS"] = {"users": f"sqlite:///{users_db_path}"}
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    class Trail(db.Model):
        __tablename__ = "trails"

        id = db.Column(db.Integer, primary_key=True)
        name = db.Column(db.String)
        difficulty_rating = db.Column(db.Integer)
        route_type = db.Column(db.String)
        visitor_usage = db.Column(db.Integer)
        avg_rating = db.Column(db.Float)
        area_name = db.Column(db.String)
        city_name = db.Column(db.String)
        features = db.Column(db.PickleType)
        activities = db.Column(db.PickleType)
        num_reviews = db.Column(db.Integer)
        latitude = db.Column(db.Float)
        longitude = db.Column(db.Float)
        length_miles = db.Column(db.Float)
        elevation_gain_ft = db.Column(db.Float)
        steepness_ftmi = db.Column(db.Float)
        difficulty_category = db.Column(db.String)
        area_category = db.Column(db.String)
        url = db.Column(db.String)

    class UserTrailProgress(db.Model):
        __bind_key__ = "users"
        __tablename__ = "user_trail_progress"

        id = db.Column(db.Integer, primary_key=True)
        user_id = db.Column(db.String, nullable=False)
        trail_id = db.Column(db.Integer, nullable=False)
        status = db.Column(db.String, default="completed")
        completed_at = db.Column(db.DateTime, default=datetime.utcnow)
        distance_miles = db.Column(db.Float)
        elevation_gain_ft = db.Column(db.Float)
        difficulty_category = db.Column(db.String)
        difficulty_rating = db.Column(db.Integer)
        rating = db.Column(db.Integer)
        notes = db.Column(db.String)

    class UserAchievement(db.Model):
        __bind_key__ = "users"
        __tablename__ = "user_achievements"

        id = db.Column(db.Integer, primary_key=True)
        user_id = db.Column(db.String, nullable=False)
        code = db.Column(db.String, nullable=False)
        earned_at = db.Column(db.DateTime, default=datetime.utcnow)

    class UserDifficultyFeedback(db.Model):
        __bind_key__ = "users"
        __tablename__ = "user_difficulty_feedback"

        id = db.Column(db.Integer, primary_key=True)
        user_id = db.Column(db.String)
        trail_id = db.Column(db.Integer)
        distance_miles = db.Column(db.Float)
        elevation_gain_ft = db.Column(db.Float)
        difficulty_estimate = db.Column(db.String)
        difficulty_feedback = db.Column(db.String)
        feedback_notes = db.Column(db.String)
        terrain_type = db.Column(db.String)
        created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def trail_to_dict(trail: Trail) -> dict:
        # Keep API output consistent and predictable.
        return {
            "id": trail.id,
            "name": trail.name,
            "difficulty_rating": trail.difficulty_rating,
            "route_type": trail.route_type,
            "visitor_usage": trail.visitor_usage,
            "avg_rating": trail.avg_rating,
            "area_name": trail.area_name,
            "city_name": trail.city_name,
            "features": list(trail.features) if trail.features else [],
            "activities": list(trail.activities) if trail.activities else [],
            "num_reviews": trail.num_reviews,
            "latitude": trail.latitude,
            "longitude": trail.longitude,
            "length_miles": trail.length_miles,
            "elevation_gain_ft": trail.elevation_gain_ft,
            "steepness_ftmi": trail.steepness_ftmi,
            "difficulty_category": trail.difficulty_category,
            "area_category": trail.area_category,
            "url": trail.url,
        }

    @app.get("/trails")
    def list_trails():
        # Flexible list endpoint for search + filters.
        query = Trail.query
        q = request.args.get("q")
        if q:
            like = f"%{q}%"
            query = query.filter(
                (Trail.name.ilike(like))
                | (Trail.city_name.ilike(like))
                | (Trail.area_name.ilike(like))
                | (Trail.difficulty_category.ilike(like))
            )

        min_length = request.args.get("min_length", type=float)
        max_length = request.args.get("max_length", type=float)
        min_difficulty = request.args.get("min_difficulty", type=int)
        max_difficulty = request.args.get("max_difficulty", type=int)
        min_rating = request.args.get("min_rating", type=float)
        max_rating = request.args.get("max_rating", type=float)

        if min_length is not None:
            query = query.filter(Trail.length_miles >= min_length)
        if max_length is not None:
            query = query.filter(Trail.length_miles <= max_length)
        if min_difficulty is not None:
            query = query.filter(Trail.difficulty_rating >= min_difficulty)
        if max_difficulty is not None:
            query = query.filter(Trail.difficulty_rating <= max_difficulty)
        if min_rating is not None:
            query = query.filter(Trail.avg_rating >= min_rating)
        if max_rating is not None:
            query = query.filter(Trail.avg_rating <= max_rating)

        sort = request.args.get("sort", "name")
        if sort == "rating":
            query = query.order_by(Trail.avg_rating.desc())
        elif sort == "length":
            query = query.order_by(Trail.length_miles.desc())
        elif sort == "difficulty":
            query = query.order_by(Trail.difficulty_rating.desc())
        else:
            query = query.order_by(Trail.name.asc())

        trails = query.limit(200).all()
        return jsonify({"count": len(trails), "items": [trail_to_dict(t) for t in trails]})

    @app.get("/")
    def index():
        # Single-page UI lives in templates/index.html.
        return render_template("index.html")

    @app.get("/trails/<int:trail_id>")
    def get_trail(trail_id: int):
        # Detail view for the drawer.
        trail = Trail.query.get_or_404(trail_id)
        return jsonify(trail_to_dict(trail))

    @app.post("/trails")
    def create_trail():
        # Admin-style trail creation.
        payload = request.get_json(silent=True) or {}
        name = payload.get("name")
        length_miles = _coerce_float(payload.get("length_miles"))
        elevation_gain_ft = _coerce_float(payload.get("elevation_gain_ft"))

        if not name or length_miles is None or elevation_gain_ft is None:
            return jsonify({"error": "name, length_miles, elevation_gain_ft required"}), 400

        steepness_ftmi = elevation_gain_ft / max(length_miles, 0.01)
        difficulty_category = estimate_difficulty_category(length_miles, elevation_gain_ft)

        trail = Trail(
            name=name,
            difficulty_rating=_coerce_int(payload.get("difficulty_rating")),
            route_type=payload.get("route_type"),
            visitor_usage=_coerce_int(payload.get("visitor_usage")),
            avg_rating=_coerce_float(payload.get("avg_rating")),
            area_name=payload.get("area_name"),
            city_name=payload.get("city_name"),
            features=payload.get("features"),
            activities=payload.get("activities"),
            num_reviews=_coerce_int(payload.get("num_reviews")),
            latitude=_coerce_float(payload.get("latitude")),
            longitude=_coerce_float(payload.get("longitude")),
            length_miles=length_miles,
            elevation_gain_ft=elevation_gain_ft,
            steepness_ftmi=steepness_ftmi,
            difficulty_category=difficulty_category,
            area_category=payload.get("area_category"),
            url=payload.get("url"),
        )
        db.session.add(trail)
        db.session.commit()

        return jsonify({"trail": trail_to_dict(trail)}), 201

    @app.patch("/trails/<int:trail_id>")
    def update_trail(trail_id: int):
        # Partial updates; only fields present in the payload are touched.
        payload = request.get_json(silent=True) or {}
        trail = Trail.query.get_or_404(trail_id)

        if "name" in payload:
            trail.name = payload.get("name")
        if "difficulty_rating" in payload:
            trail.difficulty_rating = _coerce_int(payload.get("difficulty_rating"))
        if "route_type" in payload:
            trail.route_type = payload.get("route_type")
        if "visitor_usage" in payload:
            trail.visitor_usage = _coerce_int(payload.get("visitor_usage"))
        if "avg_rating" in payload:
            trail.avg_rating = _coerce_float(payload.get("avg_rating"))
        if "area_name" in payload:
            trail.area_name = payload.get("area_name")
        if "city_name" in payload:
            trail.city_name = payload.get("city_name")
        if "features" in payload:
            trail.features = payload.get("features")
        if "activities" in payload:
            trail.activities = payload.get("activities")
        if "num_reviews" in payload:
            trail.num_reviews = _coerce_int(payload.get("num_reviews"))
        if "latitude" in payload:
            trail.latitude = _coerce_float(payload.get("latitude"))
        if "longitude" in payload:
            trail.longitude = _coerce_float(payload.get("longitude"))
        if "area_category" in payload:
            trail.area_category = payload.get("area_category")
        if "url" in payload:
            trail.url = payload.get("url")

        length_miles = (
            _coerce_float(payload.get("length_miles"))
            if "length_miles" in payload
            else trail.length_miles
        )
        elevation_gain_ft = (
            _coerce_float(payload.get("elevation_gain_ft"))
            if "elevation_gain_ft" in payload
            else trail.elevation_gain_ft
        )

        trail.length_miles = length_miles
        trail.elevation_gain_ft = elevation_gain_ft
        if length_miles is not None and elevation_gain_ft is not None:
            # Keep derived fields in sync when core metrics change.
            trail.steepness_ftmi = elevation_gain_ft / max(length_miles, 0.01)
            trail.difficulty_category = estimate_difficulty_category(
                length_miles, elevation_gain_ft
            )

        db.session.commit()
        return jsonify({"trail": trail_to_dict(trail)})

    @app.post("/trails/<int:trail_id>/complete")
    def complete_trail(trail_id: int):
        # Record a user's completion so progress/achievements can update.
        payload = request.get_json(silent=True) or {}
        user_id = payload.get("user_id")
        if not user_id:
            return jsonify({"error": "user_id required"}), 400

        trail = Trail.query.get_or_404(trail_id)
        progress = UserTrailProgress(
            user_id=user_id,
            trail_id=trail_id,
            status=payload.get("status", "completed"),
            completed_at=datetime.utcnow(),
            distance_miles=trail.length_miles,
            elevation_gain_ft=trail.elevation_gain_ft,
            difficulty_category=trail.difficulty_category,
            difficulty_rating=trail.difficulty_rating,
            rating=payload.get("rating"),
            notes=payload.get("notes"),
        )
        db.session.add(progress)
        db.session.commit()
        return jsonify({"progress_id": progress.id}), 201

    @app.get("/users/<string:user_id>/achievements")
    def user_achievements(user_id: str):
        # Computed on the fly so it always reflects latest progress.
        trails_done = (
            UserTrailProgress.query.filter_by(user_id=user_id)
            .with_entities(func.count(UserTrailProgress.id))
            .scalar()
        )
        miles = (
            UserTrailProgress.query.filter_by(user_id=user_id)
            .with_entities(func.sum(UserTrailProgress.distance_miles))
            .scalar()
            or 0
        )
        elevation = (
            UserTrailProgress.query.filter_by(user_id=user_id)
            .with_entities(func.sum(UserTrailProgress.elevation_gain_ft))
            .scalar()
            or 0
        )

        achievements = []
        if trails_done >= 10:
            achievements.append("trails_10")
        if trails_done >= 25:
            achievements.append("trails_25")
        if trails_done >= 50:
            achievements.append("trails_50")
        if miles >= 50:
            achievements.append("miles_50")
        if miles >= 100:
            achievements.append("miles_100")
        if elevation >= 10000:
            achievements.append("elevation_10k")
        if elevation >= 25000:
            achievements.append("elevation_25k")

        return jsonify(
            {
                "user_id": user_id,
                "trails_completed": trails_done,
                "miles_completed": miles,
                "elevation_gain_ft": elevation,
                "achievements": achievements,
            }
        )

    @app.get("/users/<string:user_id>/graphs")
    def user_graphs(user_id: str):
        # Simple breakdowns for the progress widgets.
        progress = UserTrailProgress.query.filter_by(user_id=user_id).all()
        trail_ids = [p.trail_id for p in progress]
        trails = Trail.query.filter(Trail.id.in_(trail_ids)).all() if trail_ids else []

        by_difficulty = {}
        by_route = {}
        by_area = {}
        for trail in trails:
            by_difficulty[trail.difficulty_category] = by_difficulty.get(
                trail.difficulty_category, 0
            ) + 1
            by_route[trail.route_type] = by_route.get(trail.route_type, 0) + 1
            by_area[trail.area_category] = by_area.get(trail.area_category, 0) + 1

        return jsonify(
            {
                "difficulty_pie": by_difficulty,
                "route_type_pie": by_route,
                "area_category_pie": by_area,
            }
        )

    @app.get("/about/stats")
    def about_stats():
        # Simple rollups for the About page charts.
        trails = Trail.query.with_entities(Trail.features, Trail.activities).all()
        activity_counts: Counter[str] = Counter()
        feature_counts: Counter[str] = Counter()

        for features, activities in trails:
            activity_counts.update(_normalize_list(activities))
            feature_counts.update(_normalize_list(features))

        def bucket_counts(counter: Counter[str], min_count: int) -> dict[str, int]:
            # Keep charts readable by bucketing the long tail into "Other".
            major = {key: count for key, count in counter.items() if count >= min_count}
            other = sum(count for key, count in counter.items() if count < min_count)
            if other:
                major["Other"] = other
            return dict(sorted(major.items(), key=lambda item: item[1], reverse=True))

        return jsonify(
            {
                "activities": bucket_counts(activity_counts, min_count=500),
                "features": bucket_counts(feature_counts, min_count=600),
            }
        )

    @app.get("/map")
    def trail_map():
        # Serve a pre-generated Folium map (regen when the dataset changes).
        map_path = Path(__file__).resolve().parent / "trail_map.html"
        if not map_path.exists():
            return (
                "<h1>Trail map not generated.</h1><p>Run the map generation script to create trail_map.html.</p>",
                404,
            )
        return send_file(map_path)

    with app.app_context():
        db.create_all()

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
