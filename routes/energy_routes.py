from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from utils.database import mongo
from bson.objectid import ObjectId

COST_PER_KWH = 0.15  # $0.15 per kWh

energy_bp = Blueprint('energy', __name__)

@energy_bp.route('/energy', methods=['POST'])
@jwt_required()
def log_energy():
    user_id = get_jwt_identity()
    data = request.get_json()
    usage_kwh = data['usage_kwh']

    mongo.db.energy_usage.insert_one({"user_id": ObjectId(user_id), "usage_kwh": usage_kwh})
    return jsonify({"msg": "Energy usage logged"}), 201

@energy_bp.route('/energy', methods=['GET'])
@jwt_required()
def get_energy():
    user_id = get_jwt_identity()
    usage = mongo.db.energy_usage.find({"user_id": ObjectId(user_id)})

    return jsonify([{"timestamp": str(doc["_id"].generation_time), "usage_kwh": doc["usage_kwh"]} for doc in usage]), 200

@energy_bp.route('/estimate_bill', methods=['POST'])
def estimate_bill():
    try:
        # Parse request data
        data = request.json
        if not data:
            return jsonify({"success": False, "message": "No data provided"}), 400
        
        # Required field
        energy_usage = data.get("energy_usage")  # kWh

        if not energy_usage or energy_usage <= 0:
            return jsonify({"success": False, "message": "Invalid energy usage (kWh)"}), 400

        # Simulation factors (customize as needed)
        fuel_energy_cost_per_kwh = 20.00  # KSH per kWh
        forex_adjustment = 1.5   # Flat forex adjustment fee
        inflation_adjustment = 2.0  # Inflation adjustment factor
        erc_levy = 0.5           # Energy regulatory levy per kWh
        vat_rate = 0.16          # VAT percentage (16%)

        # Bill breakdown calculation
        fuel_energy_cost = fuel_energy_cost_per_kwh * energy_usage
        forex_adj = forex_adjustment * energy_usage
        inflation_adj = inflation_adjustment * energy_usage
        erc_levy_total = erc_levy * energy_usage

        # Total before VAT
        total_before_vat = fuel_energy_cost + forex_adj + inflation_adj + erc_levy_total

        # VAT
        vat = total_before_vat * vat_rate

        # Final total
        total_amount = total_before_vat + vat

        # Response data
        breakdown = {
            "consumption": round(energy_usage, 2),
            "fuel_energy_cost": round(fuel_energy_cost, 2),
            "forex_adj": round(forex_adj, 2),
            "inflation_adj": round(inflation_adj, 2),
            "erc_levy": round(erc_levy_total, 2),
            "vat": round(vat, 2),
        }

        response = {
            "success": True,
            "data": {
                "total": round(total_amount, 2),
                "breakdown": breakdown,
            }
        }

        return jsonify(response), 200

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
