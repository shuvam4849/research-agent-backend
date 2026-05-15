from duckduckgo_search import DDGS

print("Testing DDGS...")
print(f"DDGS version: {DDGS.__module__}")

try:
    with DDGS() as ddgs:
        # Try different methods
        print("\nTrying ddgs.text()...")
        try:
            results = list(ddgs.text("python programming", max_results=2))
            print(f"Results from text(): {len(results)}")
            for r in results:
                print(f"  - {r.get('title', 'No title')}")
        except Exception as e:
            print(f"text() failed: {e}")
        
        print("\nTrying ddgs.search()...")
        try:
            results = list(ddgs.search("python programming", max_results=2))
            print(f"Results from search(): {len(results)}")
            for r in results:
                print(f"  - {r.get('title', 'No title')}")
        except Exception as e:
            print(f"search() failed: {e}")
            
except Exception as e:
    print(f"Error: {e}")