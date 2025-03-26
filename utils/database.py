from flask_pymongo import PyMongo

mongo = PyMongo()

def init_db(app):
    """Initialize the MongoDB connection."""
    app.config["MONGO_URI"] = app.config.get("MONGO_URI")

    try:
        mongo.init_app(app)
        # Attempt a simple query to check the connection
        mongo.db.list_collection_names()
        print("✅ Successfully connected to MongoDB!")
    except Exception as e:
        print(f"❌ Error connecting to MongoDB: {e}")
