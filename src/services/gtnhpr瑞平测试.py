import asyncio
import random
from src.services.gtnhpr import get_merged_prs, analyze_pr

async def main():
    prs = await get_merged_prs()

    for pr in random.sample(prs, min(5, len(prs))):
        result = await analyze_pr(pr)
        print(f"\n{'='*40}")
        print(pr["title"])
        print(result)

asyncio.run(main())