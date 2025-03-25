from flask import Flask
from flask_jwt_extended import JWTManager
from flask_socketio import SocketIO
from config import Config
from utils.database import init_db
from routes.auth_routes import auth_bp
from routes.energy_routes import energy_bp
from routes.report_routes import report_bp
from routes.devices_routes import device_bp
from routes.rooms_route import room_bp

app = Flask(__name__)
app.config.from_object(Config)

# Initialize Extensions
init_db(app)
jwt = JWTManager(app)
socketio = SocketIO(app)

# Register Blueprints
app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(energy_bp, url_prefix='/api/energy')
app.register_blueprint(report_bp, url_prefix='/api/report')
app.register_blueprint(device_bp, url_prefix='/api/device')
app.register_blueprint(room_bp, url_prefix="/api/room")

# WebSocket Events
# @socketio.on('connect')
# def handle_connect():
#     print("Client connected")

# @socketio.on('disconnect')
# def handle_disconnect():
#     print("Client disconnected")

# @socketio.on('alert')
# def handle_alert(data):
#     print(f"Alert received: {data}")
#     socketio.emit('notification', {"msg": "Energy alert!"})

if __name__ == '__main__':
    socketio.run(app, debug=True)
