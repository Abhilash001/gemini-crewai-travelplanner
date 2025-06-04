import uvicorn
from common import logger
from api_endpoints import app

# ==============================================
# 🌐 Run FastAPI Server
# ==============================================
if __name__ == "__main__":
    logger.info("Starting Travel Planning API server")
    uvicorn.run(app, host="0.0.0.0", port=8000)