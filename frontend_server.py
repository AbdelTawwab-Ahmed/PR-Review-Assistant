import os
from pathlib import Path
from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import httpx

app = FastAPI(title="PR-Review-Assistant-Frontend")

BACKEND_URL = os.getenv("BACKEND_URL", "https://gpgai2-ghdvf7b6caetf3ds.westus3-01.azurewebsites.net").rstrip("/")
DIST_DIR = Path(__file__).resolve().parent / "frontend" / "dist"

@app.get("/healthz")
async def healthz():
    return {
        "status": "ok",
        "service": "frontend",
        "dist_exists": DIST_DIR.exists(),
        "backend_url": BACKEND_URL,
    }

# Proxy /api requests to Backend App Service
@app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def proxy_api(request: Request, path: str):
    async with httpx.AsyncClient(timeout=60.0) as client:
        url = f"{BACKEND_URL}/api/{path}"
        headers = dict(request.headers)
        headers.pop("host", None)
        body = await request.body()
        try:
            resp = await client.request(
                method=request.method,
                url=url,
                headers=headers,
                content=body,
                params=request.query_params,
            )
            # Filter hop-by-hop headers
            excluded_headers = {"content-encoding", "content-length", "transfer-encoding", "connection"}
            res_headers = {k: v for k, v in resp.headers.items() if k.lower() not in excluded_headers}
            return Response(
                content=resp.content,
                status_code=resp.status_code,
                headers=res_headers,
            )
        except Exception as e:
            return Response(
                content=f'{{"error": "Backend unreachable: {str(e)}"}}',
                status_code=502,
                media_type="application/json"
            )

# Mount static assets if dist/assets exists
assets_dir = DIST_DIR / "assets"
if assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

# SPA catch-all: serve exact file or fallback to index.html for React Router
@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    if full_path:
        file_path = DIST_DIR / full_path
        if file_path.is_file():
            return FileResponse(file_path)
    index_file = DIST_DIR / "index.html"
    if index_file.is_file():
        return FileResponse(index_file)
    return Response(
        content="""<!DOCTYPE html>
<html>
<head><title>PR Review Assistant - Deploying</title></head>
<body style="font-family: sans-serif; background: #0f172a; color: #f8fafc; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0;">
  <div style="text-align: center; max-width: 500px; padding: 2rem; background: #1e293b; border-radius: 12px; border: 1px solid #334155;">
    <h2 style="color: #60a5fa; margin-bottom: 1rem;">Frontend Build Initializing</h2>
    <p style="color: #94a3b8; line-height: 1.6;">The React dashboard assets are currently deploying or finalizing. Please refresh in a moment.</p>
  </div>
</body>
</html>""",
        media_type="text/html",
        status_code=200
    )
