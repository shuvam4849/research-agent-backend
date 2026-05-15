from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import os
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Import the search engine — reports clearly which methods are available
# ---------------------------------------------------------------------------
SEARCH_AVAILABLE = False
SEARCH_METHODS = []

try:
    from search import hybrid_search
    SEARCH_AVAILABLE = True
    print("✅ search.py loaded successfully")

    # Report which optional backends are ready
    try:
        from googlesearch import search as _gs  # noqa
        SEARCH_METHODS.append("googlesearch-python")
    except ImportError:
        print("   ⚠️  googlesearch-python not installed  →  pip install googlesearch-python")

    try:
        from bs4 import BeautifulSoup  # noqa
        SEARCH_METHODS.append("BeautifulSoup (rich extraction)")
    except ImportError:
        print("   ⚠️  beautifulsoup4 not installed  →  pip install beautifulsoup4")

    if os.getenv("BRAVE_API_KEY"):
        SEARCH_METHODS.append("Brave Search API")
    else:
        print("   ℹ️  BRAVE_API_KEY not set — free signup at api.search.brave.com for best results")

    SEARCH_METHODS.append("DuckDuckGo HTML")
    SEARCH_METHODS.append("Wikipedia OpenSearch (always active)")

except ImportError as e:
    print(f"❌ Could not import search.py: {e}")
    print("   Make sure search.py is in the same directory as main.py")

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
app = FastAPI(title="Vidhyaarthi Hybrid Search API", version="3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
        "https://your-vercel-app.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class SearchRequest(BaseModel):
    query: str
    max_results: Optional[int] = 5
    include_full_content: Optional[bool] = True

class SearchResult(BaseModel):
    title: str
    url: str
    content: str
    snippet: str
    source: str
    word_count: int

class SearchResponse(BaseModel):
    success: bool
    query: str
    results: List[SearchResult]
    total_results: int
    error: Optional[str] = None

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/")
async def root():
    return {
        "message": "Vidhyaarthi Hybrid Search API",
        "version": "3.0",
        "search_available": SEARCH_AVAILABLE,
        "active_methods": SEARCH_METHODS,
        "brave_api_configured": bool(os.getenv("BRAVE_API_KEY")),
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "search_available": SEARCH_AVAILABLE,
        "active_methods": SEARCH_METHODS,
        "brave_configured": bool(os.getenv("BRAVE_API_KEY")),
    }

@app.post("/api/hybrid-search", response_model=SearchResponse)
async def hybrid_search_endpoint(request: SearchRequest):
    """Perform hybrid search with full content extraction."""

    if not request.query or not request.query.strip():
        return SearchResponse(
            success=False, query="", results=[], total_results=0,
            error="Query cannot be empty"
        )

    if not SEARCH_AVAILABLE:
        return SearchResponse(
            success=False,
            query=request.query,
            results=[],
            total_results=0,
            error=(
                "search.py not found. "
                "Make sure search.py is in the same folder as main.py."
            )
        )

    try:
        results = await hybrid_search(
            query=request.query.strip(),
            max_results=request.max_results or 5,
        )

        return SearchResponse(
            success=True,
            query=request.query,
            results=[SearchResult(**r) for r in results],
            total_results=len(results),
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return SearchResponse(
            success=False,
            query=request.query,
            results=[],
            total_results=0,
            error=str(e),
        )

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    print("=" * 60)
    print("🚀 Starting Vidhyaarthi Hybrid Search API")
    print("📍 Server:   http://localhost:8000")
    print("📝 API Docs: http://localhost:8000/docs")
    print("🔍 Search:   POST /api/hybrid-search")
    if SEARCH_METHODS:
        print("🔧 Active search methods:")
        for m in SEARCH_METHODS:
            print(f"   • {m}")
    print("=" * 60)

    uvicorn.run(app, host="0.0.0.0", port=8000)