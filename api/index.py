from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI()


@app.get("/api/health")
def health():
    return {"status": "online", "projeto": "PremiumHost Roberto"}
