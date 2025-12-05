from flask import Flask, request, jsonify, render_template, url_for, redirect
from flask_cors import CORS
from datetime import datetime, timedelta
import joblib
import numpy as np
import random
import math
import uuid
from pymongo import MongoClient

# ------------------ APP & DB SETUP ------------------
client = MongoClient("mongodb://localhost:27017/")
db = client["disaster_response"]

app = Flask(__name__)
CORS(app)  # Restrict in production

# -------- Sample Username & Password (demo only) --------
USERNAME = "admin@gmail.com"
PASSWORD = "12345"

# ------------------ HELPERS ------------------
def generate_disaster_prediction(lat, lon, radius_km=100):
    """
    Demo/mock disaster prediction generator.
    Uses UUID for unique ID instead of len(disasters).
    """
    disaster_types = ["flood", "earthquake", "cyclone", "wildfire"]
    risk_levels = ["low", "medium", "high", "critical"]

    prediction = {
        "id": f"pred_{uuid.uuid4().hex}",
        "type": random.choice(disaster_types),
        "risk_level": random.choice(risk_levels),
        "probability": round(random.uniform(0.3, 0.95), 2),
        "predicted_time": (
            datetime.now() + timedelta(hours=random.randint(6, 72))
        ).isoformat(),
        "impact_zone": {
            "center": {"lat": lat, "lon": lon},
            "radius_km": radius_km,
            "affected_population": random.randint(5000, 500000),
        },
        "confidence_score": round(random.uniform(0.7, 0.95), 2),
        "created_at": datetime.now().isoformat(),
    }
    return prediction

# Try loading ML model (optional)
try:
    model = joblib.load("disaster_model.pkl")
except Exception:
    model = None

# ------------------ ROUTES: PAGES ------------------
@app.route("/")
def home():
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        if username == USERNAME and password == PASSWORD:
            return redirect(url_for("dashboard"))
        return render_template("login.html", error="Invalid username or password")

    return render_template("login.html")


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


# ------------------ ML MODEL ROUTE (REAL MODEL) ------------------
@app.route("/predict", methods=["POST"])
def predict():
    if model is None:
        return jsonify({"error": "ML model not loaded"}), 500

    data = request.get_json(silent=True) or {}
    features = data.get("features")
    if features is None:
        return jsonify({"error": "Missing 'features' in request body"}), 400

    try:
        features_array = np.array(features, dtype=float).reshape(1, -1)
    except Exception:
        return jsonify({"error": "Invalid 'features' format"}), 400

    risk = model.predict(features_array)
    return jsonify({"risk": int(risk[0])})


# ------------------ DISASTER PREDICTION API ------------------
@app.route("/api/v1/predict", methods=["POST"])
def predict_disaster():
    data = request.get_json(silent=True) or {}
    lat = data.get("latitude")
    lon = data.get("longitude")
    radius = data.get("radius_km", 100)

    if lat is None or lon is None:
        return jsonify({"error": "Latitude and longitude required"}), 400

    try:
        lat = float(lat)
        lon = float(lon)
        radius = float(radius)
    except ValueError:
        return jsonify({"error": "Latitude, longitude, and radius_km must be numeric"}), 400

    prediction = generate_disaster_prediction(lat, lon, radius)
    db.disasters.insert_one(prediction)

    return jsonify(
        {
            "success": True,
            "prediction": prediction,
            "message": "Disaster prediction generated successfully",
        }
    ), 201


@app.route("/api/v1/predictions", methods=["GET"])
def get_predictions():
    risk_level = request.args.get("risk_level")
    disaster_type = request.args.get("type")

    query = {}
    if risk_level:
        query["risk_level"] = risk_level
    if disaster_type:
        query["type"] = disaster_type

    predictions = list(db.disasters.find(query, {"_id": 0}))
    return jsonify(
        {
            "success": True,
            "count": len(predictions),
            "predictions": predictions,
        }
    ), 200


@app.route("/api/v1/predictions/<prediction_id>", methods=["GET"])
def get_prediction(prediction_id):
    prediction = db.disasters.find_one({"id": prediction_id}, {"_id": 0})
    if not prediction:
        return jsonify({"error": "Prediction not found"}), 404

    return jsonify({"success": True, "prediction": prediction}), 200


# ------------------ ALERT SYSTEM API ------------------
@app.route("/api/v1/alerts", methods=["POST"])
def create_alert():
    data = request.get_json(silent=True) or {}

    alert = {
        "id": f"alert_{int(datetime.now().timestamp() * 1000)}",
        "disaster_id": data.get("disaster_id"),
        "severity": data.get("severity", "medium"),
        "title": data.get("title"),
        "message": data.get("message"),
        "location": data.get("location"),
        "alert_type": data.get("alert_type", "warning"),
        "recipients": data.get("recipients", ["general_public"]),
        "actions_required": data.get("actions_required", []),
        "status": "active",
        "created_at": datetime.now().isoformat(),
        "expires_at": (datetime.now() + timedelta(hours=24)).isoformat(),
    }

    db.alerts.insert_one(alert)
    return jsonify(
        {
            "success": True,
            "alert": alert,
            "message": "Alert sent successfully",
        }
    ), 201


@app.route("/api/v1/alerts", methods=["GET"])
def get_alerts():
    status = request.args.get("status", "active")
    severity = request.args.get("severity")

    query = {"status": status}
    if severity:
        query["severity"] = severity

    alerts_list = list(db.alerts.find(query, {"_id": 0}))
    return jsonify(
        {
            "success": True,
            "count": len(alerts_list),
            "alerts": alerts_list,
        }
    ), 200


@app.route("/api/v1/alerts/<alert_id>/acknowledge", methods=["PUT"])
def acknowledge_alert(alert_id):
    alert = db.alerts.find_one({"id": alert_id})
    if not alert:
        return jsonify({"error": "Alert not found"}), 404

    data = request.get_json(silent=True) or {}

    db.alerts.update_one(
        {"id": alert_id},
        {
            "$set": {
                "acknowledged_at": datetime.now().isoformat(),
                "acknowledged_by": data.get("user_id"),
                "status": "acknowledged",
            }
        },
    )

    updated_alert = db.alerts.find_one({"id": alert_id}, {"_id": 0})
    return jsonify({"success": True, "alert": updated_alert}), 200


# ------------------ SHELTER & SAFE ROUTES API ------------------
@app.route("/api/v1/shelters", methods=["POST"])
def add_shelter():
    data = request.get_json(silent=True) or {}

    capacity = data.get("capacity", 0)
    current_occupancy = data.get("current_occupancy", 0)

    try:
        capacity = int(capacity)
        current_occupancy = int(current_occupancy)
    except ValueError:
        return jsonify({"error": "capacity and current_occupancy must be integers"}), 400

    shelter = {
        "id": f"shelter_{int(datetime.now().timestamp() * 1000)}",
        "name": data.get("name"),
        "location": data.get("location"),  # expect dict with latitude, longitude
        "capacity": capacity,
        "current_occupancy": current_occupancy,
        "available_capacity": capacity - current_occupancy,
        "facilities": data.get("facilities", []),
        "contact": data.get("contact"),
        "status": data.get("status", "operational"),
        "created_at": datetime.now().isoformat(),
    }

    db.shelters.insert_one(shelter)
    return jsonify({"success": True, "shelter": shelter}), 201


@app.route("/api/v1/shelters", methods=["GET"])
def get_shelters():
    lat = request.args.get("latitude", type=float)
    lon = request.args.get("longitude", type=float)
    radius = request.args.get("radius_km", 50, type=float)

    all_shelters = list(db.shelters.find({}, {"_id": 0}))
    filtered_shelters = all_shelters

    if lat is not None and lon is not None:
        filtered_shelters = []
        for shelter in all_shelters:
            loc = shelter.get("location") or {}
            s_lat = loc.get("latitude")
            s_lon = loc.get("longitude")
            if s_lat is None or s_lon is None:
                continue

            try:
                s_lat = float(s_lat)
                s_lon = float(s_lon)
            except ValueError:
                continue

            # naive distance in km (lat/lon degrees -> km)
            distance = math.sqrt((lat - s_lat) ** 2 + (lon - s_lon) ** 2) * 111
            if distance <= radius:
                shelter_copy = dict(shelter)
                shelter_copy["distance_km"] = round(distance, 2)
                filtered_shelters.append(shelter_copy)

        filtered_shelters.sort(key=lambda x: x["distance_km"])

    return jsonify(
        {
            "success": True,
            "count": len(filtered_shelters),
            "shelters": filtered_shelters,
        }
    ), 200


@app.route("/api/v1/routes/safe", methods=["POST"])
def get_safe_routes():
    data = request.get_json(silent=True) or {}
    origin = data.get("origin")
    destination = data.get("destination")

    if not origin or not destination:
        return jsonify({"error": "Origin and destination required"}), 400

    try:
        o_lat = float(origin["latitude"])
        o_lon = float(origin["longitude"])
    except (KeyError, ValueError, TypeError):
        return jsonify({"error": "Origin must include numeric latitude and longitude"}), 400

    route = {
        "id": f"route_{int(datetime.now().timestamp() * 1000)}",
        "origin": origin,
        "destination": destination,
        "waypoints": [
            {"lat": o_lat + 0.01, "lon": o_lon + 0.01},
            {"lat": o_lat + 0.02, "lon": o_lon + 0.02},
        ],
        "distance_km": round(random.uniform(5, 50), 2),
        "estimated_time_minutes": random.randint(15, 120),
        "safety_score": round(random.uniform(0.7, 1.0), 2),
        "hazards_avoided": ["flooding", "blocked_roads"],
        "status": "safe",
        "last_updated": datetime.now().isoformat(),
    }

    db.safe_routes.insert_one(route)
    return jsonify({"success": True, "route": route}), 200


# ------------------ RESOURCE TRACKING API ------------------
@app.route("/api/v1/resources", methods=["POST"])
def add_resource():
    data = request.get_json(silent=True) or {}

    resource = {
        "id": f"resource_{int(datetime.now().timestamp() * 1000)}",
        "type": data.get("type"),
        "name": data.get("name"),
        "quantity": data.get("quantity"),
        "unit": data.get("unit"),
        "location": data.get("location"),
        "status": data.get("status", "available"),
        "assigned_to": data.get("assigned_to"),
        "priority": data.get("priority", "medium"),
        "created_at": datetime.now().isoformat(),
    }

    db.resources.insert_one(resource)
    return jsonify({"success": True, "resource": resource}), 201


@app.route("/api/v1/resources", methods=["GET"])
def get_resources():
    resource_type = request.args.get("type")
    status = request.args.get("status")

    query = {}
    if resource_type:
        query["type"] = resource_type
    if status:
        query["status"] = status

    filtered = list(db.resources.find(query, {"_id": 0}))
    return jsonify(
        {
            "success": True,
            "count": len(filtered),
            "resources": filtered,
        }
    ), 200


@app.route("/api/v1/resources/<resource_id>", methods=["GET"])
def get_resource_by_id(resource_id):
    resource = db.resources.find_one({"id": resource_id}, {"_id": 0})
    if not resource:
        return jsonify({"error": "Resource not found"}), 404

    return jsonify({"success": True, "resource": resource}), 200


@app.route("/api/v1/resources/<resource_id>", methods=["DELETE"])
def delete_resource(resource_id):
    result = db.resources.delete_one({"id": resource_id})
    if result.deleted_count == 0:
        return jsonify({"error": "Resource not found"}), 404

    return jsonify(
        {"success": True, "message": f"Resource {resource_id} deleted"}
    ), 200


@app.route("/api/v1/resources/<resource_id>/allocate", methods=["PUT"])
def allocate_resource(resource_id):
    resource = db.resources.find_one({"id": resource_id})
    if not resource:
        return jsonify({"error": "Resource not found"}), 404

    data = request.get_json(silent=True) or {}

    db.resources.update_one(
        {"id": resource_id},
        {
            "$set": {
                "status": "allocated",
                "assigned_to": data.get("assigned_to"),
                "allocated_at": datetime.now().isoformat(),
            }
        },
    )

    updated_resource = db.resources.find_one({"id": resource_id}, {"_id": 0})
    return jsonify({"success": True, "resource": updated_resource}), 200


# ------------------ ANALYTICS API ------------------
@app.route("/api/v1/analytics/dashboard", methods=["GET"])
def get_dashboard_analytics():
    predictions = list(db.disasters.find({}, {"_id": 0}))
    alerts = list(db.alerts.find({}, {"_id": 0}))
    shelters = list(db.shelters.find({}, {"_id": 0}))
    resources = list(db.resources.find({}, {"_id": 0}))

    analytics = {
        "total_predictions": len(predictions),
        "active_alerts": len([a for a in alerts if a.get("status") == "active"]),
        "available_shelters": len(
            [s for s in shelters if s.get("status") == "operational"]
        ),
        "total_resources": len(resources),
        "high_risk_zones": len(
            [d for d in predictions if d.get("risk_level") in ["high", "critical"]]
        ),
        "shelter_capacity": {
            "total": sum(s.get("capacity", 0) for s in shelters),
            "occupied": sum(s.get("current_occupancy", 0) for s in shelters),
            "available": sum(s.get("available_capacity", 0) for s in shelters),
        },
        "resources_by_type": {},
        "alert_severity_distribution": {
            "low": len([a for a in alerts if a.get("severity") == "low"]),
            "medium": len([a for a in alerts if a.get("severity") == "medium"]),
            "high": len([a for a in alerts if a.get("severity") == "high"]),
            "critical": len([a for a in alerts if a.get("severity") == "critical"]),
        },
    }

    resource_types = {
        r.get("type") for r in resources if r.get("type") is not None
    }
    analytics["resources_by_type"] = {
        t: len([r for r in resources if r.get("type") == t]) for t in resource_types
    }

    return jsonify(
        {
            "success": True,
            "analytics": analytics,
            "generated_at": datetime.now().isoformat(),
        }
    ), 200


# ------------------ MAP VISUALIZATION API ------------------
@app.route("/api/v1/map/overlay", methods=["GET"])
def get_map_overlay():
    disasters = list(db.disasters.find({}, {"_id": 0}))
    shelters = list(db.shelters.find({}, {"_id": 0}))

    overlay = {
        "disasters": disasters,
        "shelters": shelters,
        "blocked_areas": [
            {
                "id": "block_1",
                "type": "flood",
                "coordinates": [
                    {"lat": 23.25, "lon": 77.40},
                    {"lat": 23.26, "lon": 77.42},
                ],
                "severity": "high",
            }
        ],
        "safe_zones": [
            {
                "id": "safe_1",
                "name": "Higher Ground Area",
                "coordinates": {"lat": 23.30, "lon": 77.50},
                "radius_km": 5,
            }
        ],
    }

    return jsonify({"success": True, "overlay": overlay}), 200


# ------------------ HEALTH CHECK ------------------
@app.route("/api/v1/health", methods=["GET"])
def health_check():
    try:
        db.command("ping")
        mongo_status = "connected"
    except Exception as e:
        mongo_status = f"error: {str(e)}"

    return jsonify(
        {
            "status": "healthy",
            "version": "1.0.0",
            "mongodb": mongo_status,
            "timestamp": datetime.now().isoformat(),
        }
    ), 200


# ------------------ API DOCUMENTATION (JSON) ------------------
@app.route("/api", methods=["GET"])
def api_docs():
    endpoints = {
        "Disaster Prediction": {
            "POST /api/v1/predict": "Predict potential disasters (mock)",
            "GET /api/v1/predictions": "Get all predictions",
            "GET /api/v1/predictions/<id>": "Get specific prediction",
        },
        "Alert System": {
            "POST /api/v1/alerts": "Create new alert",
            "GET /api/v1/alerts": "Get all alerts",
            "PUT /api/v1/alerts/<id>/acknowledge": "Acknowledge alert",
        },
        "Shelters & Routes": {
            "POST /api/v1/shelters": "Add new shelter",
            "GET /api/v1/shelters": "Get shelters (with proximity filter)",
            "POST /api/v1/routes/safe": "Get safe evacuation routes",
        },
        "Resource Management": {
            "POST /api/v1/resources": "Add resource",
            "GET /api/v1/resources": "Get all resources",
            "GET /api/v1/resources/<id>": "Get single resource",
            "DELETE /api/v1/resources/<id>": "Delete resource",
            "PUT /api/v1/resources/<id>/allocate": "Allocate resource",
        },
        "Analytics": {
            "GET /api/v1/analytics/dashboard": "Get dashboard statistics",
        },
        "Map Visualization": {
            "GET /api/v1/map/overlay": "Get map overlay data",
        },
        "Health": {
            "GET /api/v1/health": "Health check",
        },
    }

    return jsonify(
        {
            "name": "AI-Powered Disaster Response API",
            "version": "1.0.0",
            "endpoints": endpoints,
        }
    ), 200


if __name__ == "__main__":
    # Use debug=True only in development
    app.run(debug=True)
    