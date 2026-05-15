from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import json
import re
from urllib.parse import quote

app = Flask(__name__)
CORS(app)

def search_brave(query, max_results=5):
    """Use Brave Search API (free tier available)"""
    # Note: You'll need to sign up for free API key at https://brave.com/search/api/
    api_key = "YOUR_BRAVE_API_KEY"  # Replace with your key
    if api_key == "YOUR_BRAVE_API_KEY":
        return []
    
    url = "https://api.search.brave.com/res/v1/web/search"
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": api_key
    }
    params = {"q": query, "count": max_results}
    
    try:
        response = requests.get(url, headers=headers, params=params)
        data = response.json()
        results = []
        for item in data.get("web", {}).get("results", []):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("description", ""),
                "content": item.get("description", "")
            })
        return results
    except:
        return []

def search_duckduckgo_html(query, max_results=5):
    """Scrape DuckDuckGo HTML results (works without API)"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        url = f"https://html.duckduckgo.com/html/?q={quote(query)}"
        response = requests.get(url, headers=headers)
        
        results = []
        # Extract result blocks
        result_pattern = r'<a rel="nofollow" class="result__a" href="([^"]+)"[^>]*>([^<]+)</a>'
        snippet_pattern = r'<a class="result__snippet"[^>]*>([^<]+)</a>'
        
        links = re.findall(result_pattern, response.text)
        snippets = re.findall(snippet_pattern, response.text)
        
        for i, (url, title) in enumerate(links[:max_results]):
            if title.strip():
                results.append({
                    "title": title.strip(),
                    "url": url,
                    "snippet": snippets[i] if i < len(snippets) else "",
                    "content": snippets[i] if i < len(snippets) else ""
                })
        
        return results
    except Exception as e:
        print(f"DuckDuckGo HTML scrape failed: {e}")
        return []

def search_fallback(query, max_results=5):
    """Return helpful fallback results"""
    return [
        {
            "title": f"Search results for: {query}",
            "url": f"https://www.google.com/search?q={quote(query)}",
            "snippet": f"Click to search Google for '{query}'",
            "content": f"Open Google to search for '{query}'"
        },
        {
            "title": f"DuckDuckGo search: {query}",
            "url": f"https://duckduckgo.com/?q={quote(query)}",
            "snippet": f"Click to search DuckDuckGo for '{query}'",
            "content": f"Open DuckDuckGo to search for '{query}'"
        }
    ]

@app.route('/api/web-search', methods=['POST', 'OPTIONS'])
def web_search():
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    
    try:
        data = request.get_json()
        query = data.get('query', '')
        max_results = data.get('max_results', 5)
        
        if not query:
            return jsonify({
                "success": False,
                "error": "Query is required",
                "results": []
            }), 400
        
        print(f"🔍 Searching for: {query}")
        
        # Try different search methods
        results = []
        
        # Method 1: DuckDuckGo HTML scraping
        results = search_duckduckgo_html(query, max_results)
        
        # Method 2: If no results, use fallback
        if not results:
            print("No results from HTML scrape, using fallback...")
            results = search_fallback(query, max_results)
        
        print(f"✅ Found {len(results)} results")
        
        return jsonify({
            "success": True,
            "query": query,
            "results": results
        })
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "results": []
        }), 500

@app.route('/')
def home():
    return jsonify({"message": "Vidhyaarthi Web Search API", "status": "running"})

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

if __name__ == '__main__':
    print("=" * 50)
    print("🚀 Starting Vidhyaarthi Web Search API")
    print("📍 Server: http://localhost:8000")
    print("=" * 50)
    app.run(host='0.0.0.0', port=8000, debug=True)