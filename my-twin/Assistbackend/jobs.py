
import os
import requests
from dotenv import load_dotenv
import json
load_dotenv()
JOBSWIPR_URL = os.environ.get("JOBSWIPR_URL", "http://localhost:5001")

def search_jobs(query: str, location: str = "") -> dict:
    """Search for jobs using the Job Swipr API."""
    api_key = os.environ.get("JOB_SWIPR_KEY")
    if not api_key:
        return {"success": False, "error": "JOBSWIPR_API_KEY not set"}
    try:
        r = requests.post(
            f"{JOBSWIPR_URL}/api/search",
            json={"query": query, "location": location},
            headers={"X-API-Key": api_key},
            timeout=15,
        )
        r.raise_for_status()
        return {"success": True, "jobs": r.json()}
    except requests.ConnectionError:
        return {"success": False, "error": "Job Swipr API isn't running on port 5001"}
    except requests.RequestException as e:
        return {"success": False, "error": str(e)}

def test_search_jobs():
    """Test the search_jobs function."""
    api_key = os.environ.get("JOB_SWIPR_KEY")
    if not api_key:
        print("Job Swipr API key not set in environment")
        return

    try:
        response = requests.get(
            "http://localhost:5001/api/jobs",
            headers={"X-API-Key": api_key},
        )
        print(response.status_code)
        print(response.headers.get("content-type"))
        print(response.text[:300])
        response.raise_for_status()
        jobs = response.json()
        print(json.dumps(jobs, indent=4))
    except requests.RequestException as e:
        print(f"Error during job search: {e}")

if __name__ == "__main__":
    print(search_jobs("software engineer", "Manchester"))
    test_search_jobs()
