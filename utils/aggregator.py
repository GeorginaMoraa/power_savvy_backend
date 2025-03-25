from utils.database import mongo
from datetime import datetime, timedelta

import logging
from utils.database import mongo
from datetime import datetime, timedelta

# Set up basic logging
logging.basicConfig(level=logging.DEBUG)

def aggregate_daily_consumption():
    try:
        # Get the current time (UTC)
        current_time = datetime.now(datetime.timezone.utc)
        start_of_day = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)

        logging.info(f"Aggregating daily consumption for date: {start_of_day.date()}")

        devices = mongo.db.devices.find()  # Fetch all devices
        for device in devices:
            device_id = device["_id"]
            power_rating = device.get("power_rating", 0)  # kWh per hour
            user_id = device["user_id"]

            # Fetch logs for the device for the current day
            logs = list(mongo.db.device_logs.find({
                "device_id": device_id,
                "timestamp": {"$gte": start_of_day, "$lt": end_of_day}
            }).sort("timestamp", 1))

            # Initialize total consumption
            total_consumption = 0.0
            previous_status = None
            previous_timestamp = None

            for log in logs:
                log_status = log.get("status", "").lower()
                log_timestamp = log["timestamp"]

                if log_status == "on" and previous_timestamp:
                    duration = (log_timestamp - previous_timestamp).total_seconds() / 3600
                    total_consumption += duration * power_rating

                previous_status = log_status
                previous_timestamp = log_timestamp

            # If the last log status is "on", calculate usage till end_of_day
            if previous_status == "on" and previous_timestamp:
                duration = (end_of_day - previous_timestamp).total_seconds() / 3600
                total_consumption += duration * power_rating

            # Log consumption result before saving it
            logging.info(f"Device ID: {device_id}, Total Consumption: {total_consumption} kWh")

            # Save daily consumption to `daily_consumption` collection
            result = mongo.db.daily_consumption.update_one(
                {
                    "user_id": user_id,
                    "device_id": str(device_id),
                    "date": start_of_day.date().isoformat()
                },
                {
                    "$set": {
                        "consumption_kwh": total_consumption,
                        "timestamp": start_of_day
                    }
                },
                upsert=True
            )

            if result.modified_count > 0:
                logging.info(f"Updated daily consumption for Device ID: {device_id} and User ID: {user_id}")
            else:
                logging.warning(f"No update was made for Device ID: {device_id} (maybe it already had the same data)")

    except Exception as e:
        logging.error(f"Error in daily aggregation: {e}", exc_info=True)

