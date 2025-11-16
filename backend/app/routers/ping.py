from fastapi import APIRouter

router = APIRouter(tags=["Sistem"])

@router.get("/ping")
async def ping():
    return {"message": "Neso backend pong! Service is running."}
