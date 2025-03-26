from flask_pymongo import PyMongo

mongo = PyMongo()

def init_db(app):
    """Initialize the MongoDB connection."""
    app.config["MONGO_URI"] = app.config.get("MONGO_URI")

    if not app.config["MONGO_URI"]:
        print("❌ MONGO_URI is missing! Set it in your environment or config.")
        return  # Prevent further execution

    print(f"🔍 Connecting to MongoDB: {app.config['MONGO_URI']}")

    try:
        mongo.init_app(app)
        # Check connection by listing collections
        collections = mongo.db.list_collection_names()
        print(f"✅ Successfully connected! Collections: {collections}")
    except Exception as e:
        print(f"❌ Error connecting to MongoDB: {e}")
