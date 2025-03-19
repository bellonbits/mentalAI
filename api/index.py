from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import sys
import os

# Add the parent directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the main app
from main import app as main_app

# Create a new app that forwards requests to the main app
app = FastAPI()

@app.api_route("/{path_name:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def catch_all(request: Request, path_name: str):
    """
    This endpoint catches all requests and forwards them to the main app.
    """
    try:
        # Forward the request to the main app
        response = await main_app.handle_request(request)
        return response
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)},
        )