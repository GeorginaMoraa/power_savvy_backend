from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    JWTManager,
    jwt_required,
    get_jwt_identity,
    create_access_token
)
from utils.database import mongo
from utils.helpers import hash_password, verify_password
from bson.objectid import ObjectId

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data['username']
    email = data['email']
    password = hash_password(data['password'])

    user = mongo.db.users.find_one({"email": email})
    if user:
        return jsonify({"msg": "User already exists"}), 400

    mongo.db.users.insert_one({"username": username, "email": email, "password": password})
    return jsonify({"msg": "User registered successfully"}), 201

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data['email']
    password = data['password']

    user = mongo.db.users.find_one({"email": email})
    if not user or not verify_password(password, user['password']):
        return jsonify({"msg": "Invalid credentials"}), 401

    token = create_access_token(identity=str(user['_id']))
    return jsonify({"access_token": token}), 200


@auth_bp.route('/profile', methods=['GET'])
@jwt_required()
def profile():
    # Get the identity of the currently logged-in user
    user_id = get_jwt_identity()

    # Fetch the user from the database by their ID
    user = mongo.db.users.find_one({"_id": ObjectId(user_id)})
    
    if not user:
        return jsonify({"msg": "User not found"}), 404

    # Return the user's profile data
    return jsonify({
        "username": user["username"],
        "email": user["email"],
        "profile_picture": user.get("profile_picture", None)  # Optional, if available
    }), 200

@auth_bp.route('/update-profile', methods=['PUT'])
@jwt_required()
def update_profile():
    # Get the data from the request body
    data = request.get_json()
    
    profile_picture = data.get('profile_picture')
    username = data.get('username')
    email = data.get('email')

    # Get the user ID from the JWT token
    user_id = get_jwt_identity()

    # Prepare the fields to be updated
    update_fields = {}
    if profile_picture:
        update_fields["profile_picture"] = profile_picture
    if username:
        update_fields["username"] = username
    if email:
        update_fields["email"] = email

    # Update the user's profile in the database
    result = mongo.db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": update_fields}
    )

    # Check if the update was successful
    if result.matched_count > 0:
        return jsonify({"msg": "Profile updated successfully"}), 200
    else:
        return jsonify({"msg": "Failed to update profile"}), 400