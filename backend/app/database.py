"""
MongoDB Database Connection
"""
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from typing import Optional
from app.config import settings


class Database:
    client: Optional[AsyncIOMotorClient] = None
    db: Optional[AsyncIOMotorDatabase] = None
    connected: bool = False
    
    async def connect(self):
        """Connect to MongoDB Atlas"""
        try:
            self.client = AsyncIOMotorClient(
                settings.MONGODB_URI,
                serverSelectionTimeoutMS=5000
            )
            self.db = self.client[settings.MONGODB_DB_NAME]
            
            # Verify connection
            await self.client.admin.command('ping')
            self.connected = True
            print(f"✅ Connected to MongoDB: {settings.MONGODB_DB_NAME}")
        except Exception as e:
            print(f"⚠️ MongoDB connection failed: {e}")
            print("🔧 Running in offline mode - data will not persist")
            self.connected = False
    
    async def disconnect(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
            print("🔌 Disconnected from MongoDB")
    
    def get_collection(self, name: str):
        """Get a collection by name"""
        if self.db is None:
            return None
        return self.db[name]
    
    # Collection shortcuts
    @property
    def jobs(self):
        return self.db["jobs"] if self.db is not None else None
    
    @property
    def tasks(self):
        return self.db["tasks"] if self.db is not None else None
    
    @property
    def agents(self):
        return self.db["agents"] if self.db is not None else None
    
    @property
    def events(self):
        return self.db["events"] if self.db is not None else None
    
    @property
    def artifacts(self):
        return self.db["artifacts"] if self.db is not None else None


# Singleton database instance
database = Database()


async def get_database() -> Database:
    """Dependency for FastAPI routes"""
    return database
