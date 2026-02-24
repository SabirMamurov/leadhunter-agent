import asyncio, sys
sys.path.insert(0, '.')
from backend.search_agent import search_companies, TAVILY_API_KEY, OPENAI_API_KEY

print(f'TAVILY_API_KEY present: {bool(TAVILY_API_KEY)}, len={len(TAVILY_API_KEY)}')
print(f'OPENAI_API_KEY present: {bool(OPENAI_API_KEY)}')

async def test():
    try:
        result = await search_companies('Catering Tomsk', max_results=5)
        print(f'\nSUCCESS! Got {len(result)} companies:')
        for c in result:
            print(f"  - {c.get('name', '??')}")
            print(f"    email   : {c.get('email', '(none)')}")
            print(f"    website : {c.get('website', '(none)')}")
            print(f"    phone   : {c.get('phone', '(none)')}")
    except Exception as e:
        print(f'ERROR: {type(e).__name__}: {e}')

asyncio.run(test())
