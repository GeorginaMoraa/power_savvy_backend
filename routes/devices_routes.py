from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    JWTManager,
    jwt_required,
    get_jwt_identity,
)
from utils.database import mongo
from bson.objectid import ObjectId
import datetime

device_bp = Blueprint('device', __name__)

# Add a device tied to the logged-in user
@device_bp.route('/devices', methods=['POST'])
@jwt_required()
def add_device():
    current_user = get_jwt_identity()
    data = request.json

    # Validate input
    if not data.get('name') or not data.get('watts') or not data.get('roomId') or not data.get('status'):
        return jsonify({"error": "Device name, watts, room ID, and status are required"}), 400

    if data['status'] not in ['on', 'off']:
        return jsonify({"error": "Status must be either 'on' or 'off'"}), 400

    try:
        # Convert roomId to ObjectId (since roomId is passed as a string)
        room_id = ObjectId(data['roomId'])  # Convert string ID to ObjectId

        # Insert device into MongoDB with status
        created_at = datetime.datetime.now(datetime.timezone.utc)
        device = {
            "name": data['name'],
            "watts": data['watts'],
            "room_id": room_id,  # Store as ObjectId in MongoDB
            "status": data['status'],  # Store the status of the device (on/off)
            "user_id": current_user,  # Associate device with the logged-in user
            "created_at": created_at
        }
        result = mongo.db.devices.insert_one(device)

        # Create an initial log entry
        initial_log = {
            "device_id": result.inserted_id,  # Use the newly created device ID
            "status": data['status'],  # Use the initial status
            "timestamp": created_at  # Use the device creation time
        }
        mongo.db.device_logs.insert_one(initial_log)

        # Return the created device details with room ID and status
        device['_id'] = str(result.inserted_id)  # Ensure the _id is a string
        device['room_id'] = str(device['room_id'])  # Ensure the room_id is a string
        return jsonify({"message": "Device created successfully", "device": device}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Get all devices for the logged-in user
@device_bp.route('/devices', methods=['GET'])
@jwt_required()
def get_devices():
    current_user = get_jwt_identity()  # Get the logged-in user's ID

    try:
        devices = []
        # Fetch devices tied to the logged-in user
        for device in mongo.db.devices.find({"user_id": current_user}):
            # Ensure _id is serialized to a string
            device['_id'] = str(device['_id'])  # Convert ObjectId to string
            if 'room_id' in device:  # If there's a room_id field
                device['room_id'] = str(device['room_id'])  # Convert room_id ObjectId to string
            devices.append(device)

        return jsonify(devices), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Get a single device by ID for the logged-in user
@device_bp.route('/devices/<device_id>', methods=['GET'])
@jwt_required()
def get_device(device_id):
    current_user = get_jwt_identity()

    try:
        device = mongo.db.devices.find_one({
            "_id": ObjectId(device_id),
            "user_id": current_user  # Ensure the device belongs to the current user
        })

        if not device:
            return jsonify({"error": "Device not found"}), 404

        device['_id'] = str(device['_id'])
        device['roomId'] = str(device['roomId'])  # Convert room ID to string for frontend usage
        return jsonify(device), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
# Get all devices associated with a specific room for the logged-in user
@device_bp.route('/devices/room', methods=['GET'])
@jwt_required()
def get_devices_by_room():
    current_user = get_jwt_identity()  # Get the logged-in user's ID
    room_id = request.args.get('roomId')

    # Validate input
    if not room_id:
        return jsonify({"error": "roomId is required"}), 400

    try:
        # Convert roomId to ObjectId (since roomId is passed as a string)
        room_id_object = ObjectId(room_id)

        devices = []
        # Fetch devices tied to the logged-in user and the specified room
        for device in mongo.db.devices.find({
            "user_id": current_user,
            "room_id": room_id_object  # Ensure the device belongs to the room
        }):
            device['_id'] = str(device['_id'])  # Convert ObjectId to string
            device['room_id'] = str(device['room_id'])  # Convert room_id ObjectId to string
            devices.append(device)

        return jsonify(devices), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@device_bp.route('/devices/status', methods=['PUT'])
@jwt_required()
def update_device_status():
    data = request.get_json()
    device_id = data.get('device_id')
    new_status = data.get('status')

    if not device_id or not new_status:
        return jsonify({"msg": "Device ID and status are required"}), 400

    if new_status not in ['on', 'off']:
        return jsonify({"error": "Status must be either 'on' or 'off'"}), 400

    try:
        now = datetime.datetime.now(datetime.timezone.utc)
        today = now.strftime('%Y-%m-%d')  # Get the current date in YYYY-MM-DD format

        # Update the device status
        result = mongo.db.devices.update_one(
            {"_id": ObjectId(device_id)},
            {"$set": {"status": new_status, "status_changed_at": now}}
        )

        if result.matched_count > 0:
            # Fetch the last log for this device
            last_log = mongo.db.device_logs.find_one(
                {"device_id": ObjectId(device_id)},
                sort=[("timestamp", -1)]
            )

            # Calculate the duration if the device was previously "on"
            if last_log and last_log['status'] == "on":
                last_timestamp = last_log["timestamp"]
                if last_timestamp.tzinfo is None:
                    last_timestamp = last_timestamp.replace(tzinfo=datetime.timezone.utc)

                duration = (now - last_timestamp).total_seconds()

                # Update the daily aggregation
                mongo.db.device_status_daily.update_one(
                    {"device_id": ObjectId(device_id), "date": today},
                    {"$inc": {"on_duration": duration}, "$set": {"status": new_status}},
                    upsert=True
                )

            # Insert the new log
            mongo.db.device_logs.insert_one({
                "device_id": ObjectId(device_id),
                "status": new_status,
                "timestamp": now
            })

            return jsonify({"msg": "Device status updated successfully"}), 200
        else:
            return jsonify({"msg": "Device not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Delete a device by ID
@device_bp.route('/devices/<device_id>', methods=['DELETE'])
@jwt_required()
def delete_device(device_id):
    current_user = get_jwt_identity()

    try:
        # Attempt to delete the device by its ID and ensure it's the logged-in user's device
        result = mongo.db.devices.delete_one({
            "_id": ObjectId(device_id),
            "user_id": current_user  # Only allow the user to delete their own device
        })

        if result.deleted_count > 0:
            return jsonify({"msg": "Device deleted successfully"}), 200
        else:
            return jsonify({"error": "Device not found or not authorized to delete"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Edit a device by ID
@device_bp.route('/devices/<device_id>', methods=['PUT'])
@jwt_required()
def edit_device(device_id):
    current_user = get_jwt_identity()
    data = request.json

    # Validate input
    if not data.get('name') and not data.get('watts') and not data.get('roomId') and not data.get('status'):
        return jsonify({"error": "At least one field (name, watts, room ID, status) must be provided for update"}), 400

    # Convert roomId to ObjectId if provided
    if data.get('roomId'):
        try:
            room_id = ObjectId(data['roomId'])  # Convert string ID to ObjectId
        except Exception as e:
            return jsonify({"error": "Invalid room ID format"}), 400

    try:
        # Prepare the update data
        update_data = {}
        if data.get('name'):
            update_data["name"] = data['name']
        if data.get('watts'):
            update_data["watts"] = data['watts']
        if data.get('roomId'):
            update_data["room_id"] = room_id  # Update room_id if provided
        if data.get('status'):
            if data['status'] not in ['on', 'off']:
                return jsonify({"error": "Status must be either 'on' or 'off'"}), 400
            update_data["status"] = data['status']

        # Update the device in the database
        result = mongo.db.devices.update_one(
            {"_id": ObjectId(device_id), "user_id": current_user},
            {"$set": update_data}
        )

        if result.matched_count > 0:
            # Fetch the updated device data
            updated_device = mongo.db.devices.find_one({"_id": ObjectId(device_id)})
            updated_device['_id'] = str(updated_device['_id'])
            updated_device['room_id'] = str(updated_device['room_id'])  # Ensure room_id is a string
            return jsonify({"msg": "Device updated successfully", "device": updated_device}), 200
        else:
            return jsonify({"error": "Device not found or not authorized to edit"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@device_bp.route('/devices/<device_id>/on-duration-summary', methods=['GET'])
@jwt_required()
def get_device_on_duration_summary(device_id):
    current_user = get_jwt_identity()

    try:
        # Fetch the device to ensure it belongs to the current user
        device = mongo.db.devices.find_one({"_id": ObjectId(device_id), "user_id": current_user})
        if not device:
            return jsonify({"error": "Device not found"}), 404

        # Fetch all logs for the device
        logs = list(mongo.db.device_logs.find({"device_id": ObjectId(device_id)}).sort("timestamp", 1))

        # Calculate durations
        daily_duration = datetime.timedelta(0)
        weekly_duration = datetime.timedelta(0)
        monthly_duration = datetime.timedelta(0)

        now = datetime.datetime.now(datetime.timezone.utc)

        # Determine the start of the current day (00:00)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # Determine the start of the current week (Monday, 00:00)
        start_of_week = (now - datetime.timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)

        # Determine the start of the current month
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Track previous log's status and timestamp
        previous_status = None
        previous_timestamp = None

        for log in logs:
            log_timestamp = log["timestamp"]

            # Convert to timezone-aware datetime if naive
            if log_timestamp.tzinfo is None:
                log_timestamp = log_timestamp.replace(tzinfo=datetime.timezone.utc)

            log_status = log["status"]

            # If the previous status was 'on', calculate the duration
            if previous_status == "on":
                duration = log_timestamp - previous_timestamp
                if log_timestamp >= start_of_day:  # Check if the duration falls within the current day
                    daily_duration += duration
                if log_timestamp >= start_of_week:  # Check if the duration falls within the current week
                    weekly_duration += duration
                if log_timestamp >= start_of_month:  # Check if the duration falls within the current month
                    monthly_duration += duration

            # Update previous status and timestamp
            previous_status = log_status
            previous_timestamp = log_timestamp

        # Account for current "on" duration if the device is still on
        if previous_status == "on":
            duration = now - previous_timestamp
            if now >= start_of_day:
                daily_duration += duration
            if now >= start_of_week:
                weekly_duration += duration
            if now >= start_of_month:
                monthly_duration += duration

        # Format durations to HH:MM:SS
        def format_duration(duration):
            total_seconds = int(duration.total_seconds())
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            return f"{hours:02}:{minutes:02}:{seconds:02}"

        # Get the daily tag in YYYY-MM-DD format
        daily_tag = start_of_day.strftime('%Y-%m-%d')

        return jsonify({
            "device_id": device_id,
            "daily_tag": daily_tag,  # Add the day being measured
            "daily_on_duration": format_duration(daily_duration),
            "weekly_on_duration": format_duration(weekly_duration),
            "monthly_on_duration": format_duration(monthly_duration)
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@device_bp.route('/devices/daily-consumption', methods=['GET'])
@jwt_required()
def get_daily_consumption():
    current_user = get_jwt_identity()  # Get the logged-in user's ID
    date = request.args.get('date')  # Accept the date from the query string (e.g., 2024-12-05)

    # Validate input
    if not date:
        return jsonify({"error": "Date is required"}), 400

    try:
        # Parse the provided date (ensure it's in YYYY-MM-DD format)
        parsed_date = datetime.datetime.strptime(date, '%Y-%m-%d').date()

        # Determine the start and end of the day for comparison (00:00:00 and 23:59:59)
        start_of_day = datetime.datetime.combine(parsed_date, datetime.time.min)
        end_of_day = datetime.datetime.combine(parsed_date, datetime.time.max)

        # Fetch all devices for the logged-in user
        devices = mongo.db.devices.find({"user_id": current_user})

        consumption_data = []

        for device in devices:
            device_name = device['name']
            room_id = device['room_id']
            # Retrieve room name (ensure room_id exists and can be used to fetch room)
            room = mongo.db.rooms.find_one({"_id": room_id})  # Assuming rooms collection exists

            room_name = room['name'] if room else "Unknown Room"
            
            # Fetch the logs for the device, filtered by date
            logs = mongo.db.device_logs.find({
                "device_id": device['_id'],
                "timestamp": {"$gte": start_of_day, "$lte": end_of_day}
            })

            total_consumption = 0.0

            # Ensure that 'watts' is a float before performing calculations
            watts = float(device.get('watts', 0))  # Default to 0 if 'watts' is missing or invalid

            # Calculate the total energy consumption for the day
            previous_timestamp = None
            for log in logs:
                if log['status'] == 'on' and previous_timestamp:
                    duration = log['timestamp'] - previous_timestamp
                    # Calculate the energy consumption in kWh
                    # Watts to kWh conversion: consumption = (watts * duration in hours) / 1000
                    duration_in_hours = duration.total_seconds() / 3600
                    consumption = (watts * duration_in_hours) / 1000
                    total_consumption += consumption

                previous_timestamp = log['timestamp']

            # Add the daily consumption data for the device
            consumption_data.append({
                "device_name": device_name,
                "consumption": round(total_consumption, 2),  # rounded to 2 decimal places
                "date": date,
                "room": room_name
            })

        # Return the formatted data as a response (could also be passed to a frontend app)
        return jsonify(consumption_data), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

@device_bp.route('/consumption/monthly', methods=['GET'])
@jwt_required()
def get_monthly_consumption_with_cost():
    """
    Fetch monthly energy consumption data along with cost breakdown for the authenticated user.
    """
    user_id = get_jwt_identity()  # Assuming this is the user ID passed from the JWT

    try:
        # Convert the user_id to ObjectId
        user_id_obj = ObjectId(user_id)  # Convert string to ObjectId

        # Constants for cost calculation
        FUEL_ENERGY_COST_PER_KWH = 20.00  # KSH per kWh
        FOREX_ADJUSTMENT = 1.5           # Flat forex adjustment fee
        INFLATION_ADJUSTMENT = 2.0       # Inflation adjustment factor
        ERC_LEVY = 0.5                   # Energy regulatory levy per kWh
        VAT_RATE = 0.16                  # VAT percentage (16%)

        # Get the month parameter from the request (YYYY-MM)
        month_str = request.args.get('month')  # e.g., '2024-12'

        # Parse the month into a date range (start of month and end of month)
        start_of_month = datetime.strptime(month_str + "-01", "%Y-%m-%d")
        end_of_month = (start_of_month.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)

        # Aggregate monthly consumption data using the date range
        pipeline = [
            {"$match": {
                "user_id": user_id_obj,
                "date": {"$gte": start_of_month, "$lte": end_of_month}
            }},
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