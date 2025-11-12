import asyncio
import aiohttp
from app.auth import get_current_user_optional
from app.database import get_db

async def test_search_jobs_no_auth():
    """Test function to see if search works without authentication"""
    # Test making a direct API call to our endpoint
    async with aiohttp.ClientSession() as session:
        data = {
            "job_title": "test job",
            "location": "remote",
            "max_results": 1
        }
        
        async with session.post(
            'http://localhost:5001/api/search-jobs',
            json=data
        ) as response:
            print(f"Status: {response.status}")
            text = await response.text()
            print(f"Response: {text}")

if __name__ == "__main__":
    asyncio.run(test_search_jobs_no_auth())