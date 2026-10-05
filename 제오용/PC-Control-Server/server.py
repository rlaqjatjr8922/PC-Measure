from pathlib import Path
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

import config
from api import router, mcp, mcp_app
from remote_routes import router as remote_router
from control_ui import router as control_router
from fastapi.responses import RedirectResponse


BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "data"
HISTORY_DIR = DATA_DIR / "history"
LOG_DIR = DATA_DIR / "logs"
PLUGINS_DIR = BASE_DIR / "plugins"


def prepare():
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    PLUGINS_DIR.mkdir(parents=True, exist_ok=True)


prepare()

@asynccontextmanager
async def lifespan(app):
    async with mcp.session_manager.run():
        yield


app = FastAPI(
    lifespan=lifespan,
    title="PC Control Server",
    version="1.0.0"
)

app.include_router(router)
app.include_router(remote_router)
app.include_router(control_router)


@app.get("/")
def root():
    return RedirectResponse('/control')

@app.get('/health')
def health():
    return {'success': True, 'server': 'PC Control Server'}


# Mount last so existing HTTP routes retain priority.
app.mount("/", mcp_app)


if __name__ == "__main__":
    uvicorn.run(
        "server:app",
        host=config.server["host"],
        port=config.server["port"],
        reload=config.server["debug"]
    )
