from fastapi import FastAPI, APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid
from datetime import datetime, timezone
import json
import asyncio
import random


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except:
                # Remove broken connections
                self.active_connections.remove(connection)

manager = ConnectionManager()

# Define Models
class DrainStatus(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    latitude: float
    longitude: float
    status: str  # "livre", "parcialmente_obstruido", "entupido"
    location_name: str
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class DrainStatusCreate(BaseModel):
    latitude: float
    longitude: float
    status: str
    location_name: str

class DrainStatusUpdate(BaseModel):
    status: str

# Helper functions for MongoDB serialization
def prepare_for_mongo(data):
    if isinstance(data.get('last_updated'), datetime):
        data['last_updated'] = data['last_updated'].isoformat()
    return data

def parse_from_mongo(item):
    if isinstance(item.get('last_updated'), str):
        item['last_updated'] = datetime.fromisoformat(item['last_updated'])
    return item

# Add your routes to the router instead of directly to app
@api_router.get("/")
async def root():
    return {"message": "Smart Sewer Monitoring API"}

@api_router.post("/drains", response_model=DrainStatus)
async def create_drain(drain_data: DrainStatusCreate):
    drain_dict = drain_data.dict()
    drain_obj = DrainStatus(**drain_dict)
    prepared_data = prepare_for_mongo(drain_obj.dict())
    await db.drains.insert_one(prepared_data)
    
    # Broadcast the new drain to all connected clients
    await manager.broadcast({
        "type": "drain_created",
        "data": drain_obj.model_dump(mode='json')
    })
    
    return drain_obj

@api_router.get("/drains", response_model=List[DrainStatus])
async def get_drains(status_filter: Optional[str] = None):
    query = {}
    if status_filter:
        query["status"] = status_filter
    
    drains = await db.drains.find(query).to_list(1000)
    parsed_drains = [parse_from_mongo(drain) for drain in drains]
    return [DrainStatus(**drain) for drain in parsed_drains]

@api_router.put("/drains/{drain_id}", response_model=DrainStatus)
async def update_drain_status(drain_id: str, update_data: DrainStatusUpdate):
    update_dict = {
        "status": update_data.status,
        "last_updated": datetime.now(timezone.utc).isoformat()
    }
    
    result = await db.drains.update_one(
        {"id": drain_id},
        {"$set": update_dict}
    )
    
    if result.modified_count == 0:
        return {"error": "Drain not found"}
    
    # Get updated drain
    updated_drain = await db.drains.find_one({"id": drain_id})
    if updated_drain:
        parsed_drain = parse_from_mongo(updated_drain)
        drain_obj = DrainStatus(**parsed_drain)
        
        # Broadcast the update to all connected clients
        await manager.broadcast({
            "type": "drain_updated",
            "data": drain_obj.model_dump(mode='json')
        })
        
        return drain_obj

@api_router.get("/drains/{drain_id}", response_model=DrainStatus)
async def get_drain(drain_id: str):
    drain = await db.drains.find_one({"id": drain_id})
    if drain:
        parsed_drain = parse_from_mongo(drain)
        return DrainStatus(**parsed_drain)
    return {"error": "Drain not found"}

# Initialize sample data
@api_router.post("/init-sample-data")
async def init_sample_data():
    # São Paulo sample locations
    sample_drains = [
        {"latitude": -23.5505, "longitude": -46.6333, "status": "livre", "location_name": "Centro - Rua XV de Novembro"},
        {"latitude": -23.5475, "longitude": -46.6361, "status": "parcialmente_obstruido", "location_name": "Centro - Rua Direita"},
        {"latitude": -23.5445, "longitude": -46.6378, "status": "entupido", "location_name": "Centro - Largo São Bento"},
        {"latitude": -23.5615, "longitude": -46.6565, "status": "livre", "location_name": "Vila Madalena - Rua Harmonia"},
        {"latitude": -23.5635, "longitude": -46.6545, "status": "entupido", "location_name": "Vila Madalena - Rua Aspicuelta"},
        {"latitude": -23.5495, "longitude": -46.6395, "status": "parcialmente_obstruido", "location_name": "Centro - Rua Augusta"},
        {"latitude": -23.5555, "longitude": -46.6625, "status": "livre", "location_name": "Pinheiros - Rua dos Pinheiros"},
        {"latitude": -23.5585, "longitude": -46.6605, "status": "entupido", "location_name": "Pinheiros - Largo da Batata"},
        {"latitude": -23.5465, "longitude": -46.6445, "status": "livre", "location_name": "Consolação - Rua da Consolação"},
        {"latitude": -23.5525, "longitude": -46.6485, "status": "parcialmente_obstruido", "location_name": "Consolação - Av. Paulista"},
    ]
    
    # Clear existing data
    await db.drains.delete_many({})
    
    # Insert sample data
    for drain_data in sample_drains:
        drain_obj = DrainStatus(**drain_data)
        prepared_data = prepare_for_mongo(drain_obj.dict())
        await db.drains.insert_one(prepared_data)
    
    return {"message": f"Initialized {len(sample_drains)} sample drains"}

# WebSocket endpoint for real-time updates
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Handle incoming messages if needed
            await websocket.send_text(f"Message received: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# Background task to simulate Raspberry Pi sensor updates
async def simulate_sensor_updates():
    while True:
        await asyncio.sleep(10)  # Update every 10 seconds
        
        # Get all drains
        drains = await db.drains.find().to_list(1000)
        if drains:
            # Randomly select a drain to update
            random_drain = random.choice(drains)
            
            # Randomly change status (simulate sensor reading)
            statuses = ["livre", "parcialmente_obstruido", "entupido"]
            current_status = random_drain.get("status", "livre")
            
            # 70% chance to stay the same, 30% chance to change
            if random.random() < 0.3:
                new_status = random.choice([s for s in statuses if s != current_status])
                
                # Update in database
                update_dict = {
                    "status": new_status,
                    "last_updated": datetime.now(timezone.utc).isoformat()
                }
                
                await db.drains.update_one(
                    {"id": random_drain["id"]},
                    {"$set": update_dict}
                )
                
                # Get updated drain and broadcast
                updated_drain = await db.drains.find_one({"id": random_drain["id"]})
                if updated_drain:
                    parsed_drain = parse_from_mongo(updated_drain)
                    drain_obj = DrainStatus(**parsed_drain)
                    
                    await manager.broadcast({
                        "type": "sensor_update",
                        "data": drain_obj.model_dump(mode='json')
                    })

# Start background task
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(simulate_sensor_updates())

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()