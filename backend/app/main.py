from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes.analysis import router as analysis_router
import uvicorn
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="EA Analyzer API", version="1.0.0")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(analysis_router)

@app.get("/")
async def root():
    return {"message": "EA Analyzer API is running", "version": "1.0.0"}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
