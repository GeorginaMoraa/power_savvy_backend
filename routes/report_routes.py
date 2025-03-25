from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from utils.database import mongo
from bson.objectid import ObjectId
import datetime

report_bp = Blueprint('report', __name__)

@report_bp.route('/report', methods=['GET'])
@jwt_required()
def get_report():
    """Fetch total usage for the authenticated user."""
    user_id = get_jwt_identity()
    total_usage = sum(doc["usage_kwh"] for doc in mongo.db.energy_usage.find({"user_id": ObjectId(user_id)}))

    return jsonify({"total_usage": total_usage, "unit": "kWh"}), 200

@jwt_required()
def calculate_realtime_usage(user_id):
    """
    Calculate real-time usage based on device logs for the authenticated user.
    """
    current_time = datetime.datetime.now(datetime.timezone.utc)  # Current time
    total_usage = 0.0

    # Convert user_id to ObjectId
    try:
        user_id_obj = ObjectId(user_id)
        print(f"[DEBUG] Successfully converted user_id to ObjectId: {user_id_obj}")
    except Exception as e:
        print(f"[DEBUG] Error converting user_id to ObjectId: {e}")
        return 0.1  # Default usage if there's an error

    print(f"[DEBUG] Querying devices with user_id: {user_id_obj}")
    # Fetch all devices for the user
    devices = list(mongo.db.devices.find({"user_id": user_id}))
    print(f"[DEBUG] Devices fetched for User {user_id}: {devices}")

    if not devices:
        print(f"[DEBUG] No devices found for user {user_id_obj}. Returning default usage.")
        return 0.1  # Default usage when no devices found

    for device in devices:
        device_id = device["_id"]
        power_rating = device.get("power_rating", 0)  # Power consumption in kWh
        print(f"[DEBUG] Device {device_id} Power Rating: {power_rating}")

        if not power_rating or power_rating <= 0:
            print(f"[DEBUG] Device {device_id} has invalid power rating. Using default 0.1 kWh.")
            power_rating = 0.1  # Default power rating if invalid

        # Fetch logs for this device, sorted by timestamp
        logs = list(mongo.db.device_logs.find({"device_id": device_id}).sort("timestamp", 1))
        print(f"[DEBUG] Logs for Device {device_id}: {logs}")

        if not logs:
            print(f"[DEBUG] No logs found for Device {device_id}. Skipping.")
            continue

        # Track usage based on logs
        previous_status = None
        previous_timestamp = None
        device_usage = 0.0

        for log in logs:
            log_status = log.get("status", "").lower()
            log_timestamp = log.get("timestamp")

            if not log_timestamp:
                print(f"[DEBUG] Log entry without timestamp: {log}. Skipping.")
                continue

            # Ensure timezone-aware log timestamp
            if log_timestamp.tzinfo is None:
                log_timestamp = log_timestamp.replace(tzinfo=datetime.timezone.utc)

            if previous_status == "on" and previous_timestamp:
                duration = (log_timestamp - previous_timestamp).total_seconds() / 3600  # Convert seconds to hours
                device_usage += duration * power_rating
                print(f"[DEBUG] Device {device_id}: Duration {duration} hours, Usage Added {duration * power_rating} kWh")

            previous_status = log_status
            previous_timestamp = log_timestamp

        # If device is still ON, calculate usage from last log to now
        if previous_status == "on" and previous_timestamp:
            duration = (current_time - previous_timestamp).total_seconds() / 3600
            device_usage += duration * power_rating
            print(f"[DEBUG] Device {device_id} is currently ON. Usage added: {duration * power_rating} kWh")

        total_usage += device_usage

    if total_usage == 0:
        print(f"[DEBUG] Total usage is 0. Returning default usage.")
        return 0.1  # Return minimum usage

    return round(total_usage, 2)


@report_bp.route('/consumption/realtime', methods=['GET'])
@jwt_required()
def get_realtime_data_with_logs():
    """
    API route to fetch real-time consumption data for the authenticated user using logs.
    """
    user_id = get_jwt_identity()
    try:
        current_usage = calculate_realtime_usage(user_id)
        return jsonify({
            "status": "success",
            "data": {
                "current_usage": current_usage,
                "timestamp": datetime.datetime.now(datetime.timezone.utc)
            }
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500



@report_bp.route('/update_realtime', methods=['POST'])
@jwt_required()
def update_realtime_data_route():
    """
    API route to trigger real-time data update for the authenticated user.
    """
    user_id = get_jwt_identity()
    calculate_realtime_usage(user_id)
    return jsonify({"status": "success", "message": "Real-time data updated."}), 200


@report_bp.route('/consumption/monthly', methods=['GET'])
@jwt_required()
def get_monthly_consumption_with_cost():
    """
    Fetch monthly energy consumption data along with cost breakdown for the authenticated user.
    """
    user_id = get_jwt_identity()

    try:
        # Ensure `user_id` is converted to ObjectId
        user_id_obj = ObjectId(user_id)

        # Constants for cost calculation
        FUEL_ENERGY_COST_PER_KWH = 20.00  # KSH per kWh
        FOREX_ADJUSTMENT = 1.5           # Flat forex adjustment fee
        INFLATION_ADJUSTMENT = 2.0       # Inflation adjustment factor
        ERC_LEVY = 0.5                   # Energy regulatory levy per kWh
        VAT_RATE = 0.16                  # VAT percentage (16%)

        # Aggregate monthly consumption data
        pipeline = [
            {"$match": {"user_id": user_id_obj}},  # Match documents for the user
            {
                "$group": {  # Group by year and month
                    "_id": {
                        "year": {"$year": {"$dateFromString": {"dateString": "$date"}}},
                        "month": {"$month": {"$dateFromString": {"dateString": "$date"}}}
                    },
                    "total_usage": {"$sum": "$usage_kwh"}  # Sum usage for each group
                }
            },
            {"$sort": {"_id.year": 1, "_id.month": 1}}  # Sort by year and month
        ]

        result = list(mongo.db.energy_usage.aggregate(pipeline))

        # Calculate cost breakdown for each month
        monthly_data = []
        for entry in result:
            year = entry["_id"]["year"]
            month = entry["_id"]["month"]
            total_usage = entry["total_usage"]

            # Cost breakdown
            fuel_energy_cost = FUEL_ENERGY_COST_PER_KWH * total_usage
            forex_adj = FOREX_ADJUSTMENT * total_usage
            inflation_adj = INFLATION_ADJUSTMENT * total_usage
            erc_levy_total = ERC_LEVY * total_usage
            total_before_vat = fuel_energy_cost + forex_adj + inflation_adj + erc_levy_total
            vat = total_before_vat * VAT_RATE
            total_amount = total_before_vat + vat

            monthly_data.append({
                "year": year,
                "month": month,
                "total_usage": round(total_usage, 2),
                "total_cost": round(total_amount, 2),
                "cost_breakdown": {
                    "fuel_energy_cost": round(fuel_energy_cost, 2),
                    "forex_adj": round(forex_adj, 2),
                    "inflation_adj": round(inflation_adj, 2),
                    "erc_levy": round(erc_levy_total, 2),
                    "vat": round(vat, 2),
                }
            })

        return jsonify({
            "status": "success",
            "data": monthly_data
        }), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
