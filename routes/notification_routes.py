from flask import request, jsonify , Blueprint
import socketio


notification = Blueprint('notification', __name__)

@notification.route('/webhook/notify', methods=['POST'])
def webhook_notify():
    """
    Endpoint to receive webhook notifications.
    The payload should include the `device_id`, `message`, or any other relevant data.
    """
    try:
        # Parse the JSON payload
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid payload"}), 400

        device_id = data.get("device_id")
        message = data.get("message", "Device notification received")

        if not device_id:
            return jsonify({"error": "Device ID is required"}), 400

        # Send notification to all connected clients for the specific device
        socketio.emit('notification', {
            "device_id": device_id,
            "message": message
        })

        return jsonify({"success": True, "message": "Notification sent"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
