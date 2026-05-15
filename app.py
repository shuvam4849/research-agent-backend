from flask import Flask, request, jsonify
from flask_cors import CORS
from duckduckgo_search import DDGS
import json

app = Flask(__name__)
CORS(app)

@app.route('/')
def home():
    return jsonify({"message": "Vidhyaarthi Web Search API", "status": "running"})

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

@app.route('/api/web-search', methods=['POST', 'OPTIONS'])
def web_search():
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    
    try:
        if request.is_json:
            data = request.get_json()
        else:
            try:
                data = json.loads(request.data)
            except:
                return jsonify({
                    "success": False,
                    "error": "Invalid JSON format",
                    "results": []
                }), 400
        
        query = data.get('query', '')
        max_results = data.get('max_results', 5)
        
        if not query:
            return jsonify({
                "success": False,
                "error": "Query is required",
                "results": []
            }), 400
        
        print(f"🔍 Searching for: {query}")
        
        search_results = []
        try:
            # Use the correct method based on version
            with DDGS() as ddgs:
                # Try different method names
                try:
                    # For newer versions
                    results = list(ddgs.text(query, max_results=max_results))
                except AttributeError:
                    try:
                        # For older versions
                        results = list(ddgs.search(query, max_results=max_results))
                    except:
                        # Alternative method
                        results = list(ddgs.answers(query))
                
                print(f"📊 Raw results count: {len(results)}")
                
                for r in results:
                    # Handle different response formats
                    title = r.get('title') or r.get('heading') or 'No title'
                    url = r.get('href') or r.get('url') or '#'
                    body = r.get('body') or r.get('description') or r.get('text', '')
                    
                    if title and body:  # Only add if we have meaningful content
                        search_results.append({
                            "title": title,
                            "url": url,
                            "content": body[:1000],
                            "snippet": body[:300]
                        })
                        print(f"  ✓ Added: {title[:50]}...")
                    
        except Exception as e:
            print(f"Search error: {e}")
            import traceback
            traceback.print_exc()
        
        # If still no results, use a fallback
        if not search_results:
            print("No results from DDGS, using fallback...")
            search_results = [
                {
                    "title": f"Search: {query}",
                    "url": f"https://duckduckgo.com/?q={query.replace(' ', '+')}",
                    "content": f"Click to search DuckDuckGo for '{query}'",
                    "snippet": f"Direct DuckDuckGo search results for '{query}'"
                }
            ]
        
        print(f"✅ Returning {len(search_results)} results")
        
        return jsonify({
            "success": True,
            "query": query,
            "results": search_results
        })
        
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e),
            "results": []
        }), 500

if __name__ == '__main__':
    print("=" * 50)
    print("🚀 Starting Vidhyaarthi Web Search API")
    print("📍 Server: http://localhost:8000")
    print("=" * 50)
    app.run(host='0.0.0.0', port=8000, debug=True)