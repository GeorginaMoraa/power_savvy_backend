import os

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "your_secret_key")
    MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://bridge:oWOpozyihRVNBIFP@cluster0.xk1esci.mongodb.net/power_savvy?retryWrites=true&w=majority&appName=Cluster0")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your_jwt_secret")
