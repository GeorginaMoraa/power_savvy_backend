from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    jwt_required,
    get_jwt_identity,
)
from utils.database import mongo
from utils.helpers import hash_password, verify_password
from bson.objectid import ObjectId
import datetime

room_bp = Blueprint('room', __name__)

@room_bp.route('/rooms', methods=['POST'])
@jwt_required()
def add_room():
    current_user = get_jwt_identity()  
    data = request.json

    # Validate input
    if not data.get('name') or not data.get('description'):
        return jsonify({"error": "Room name and description are required"}), 400

    try:
        # Insert room into MongoDB
        room = {
            "name": data['name'],
            "description": data['description'],
            "user_id": current_user,  # Associate room with the logged-in user
            "created_at": datetime.datetime.now(datetime.timezone.utc)
        }
        result = mongo.db.rooms.insert_one(room)

        # Return the created room details
        room['_id'] = str(result.inserted_id)
        return jsonify({"message": "Room created successfully", "room": room}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

# Get all rooms for the logged-in user
@room_bp.route('/rooms', methods=['GET'])
@jwt_required()
def get_rooms():
    current_user = get_jwt_identity()  # Get the logged-in user's ID

    try:
        rooms = []
        for room in mongo.db.rooms.find({"user_id": current_user}):  # Filter by user ID
            room['_id'] = str(room['_id'])
            rooms.append(room)
        return jsonify(rooms), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Get a single room by ID for the logged-in user
@room_bp.route('/api/rooms/<room_id>', methods=['GET'])
@jwt_required()
def get_room(room_id):
    current_user = get_jwt_identity()

    try:
        room = mongo.db.rooms.find_one({"_id": ObjectId(room_id), "user_id": current_user})  # Filter by user ID
        if not room:
            return jsonify({"error": "Room not found"}), 404

        room['_id'] = str(room['_id'])
        return jsonify(room), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@room_bp.route('/rooms/<room_id>', methods=['DELETE'])
@jwt_required()
def delete_room(room_id):
    current_user = get_jwt_identity()  # Get the logged-in user's ID

    try:
        # Find the room to be deleted by room_id and user_id
        room = mongo.db.rooms.find_one({"_id": ObjectId(room_id), "user_id": current_user})

        if not room:
            return jsonify({"error": "Room not found or you do not have permission to delete it"}), 404

        # Delete the room
        mongo.db.rooms.delete_one({"_id": ObjectId(room_id)})

        return jsonify({"message": "Room deleted successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500