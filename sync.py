#!/usr/bin/env python3
import sys

# DEBUG: Catch immediate startup errors
try:
    import requests
    import json
    import os
    import argparse
    import time
    import base64
    import math
    from datetime import datetime, timedelta
    from typing import Dict, List
    print("✅ All libraries loaded successfully")
except Exception as e:
    print(f"❌ FATAL: Library import failed: {e}")
    sys.exit(1)

class IntervalsSync:
    def __init__(self, athlete_id, intervals_api_key, github_token=None, github_repo=None):
        self.athlete_id = athlete_id
        # Ensure auth is correctly formatted
        auth_str = f"API_KEY:{intervals_api_key}"
        self.intervals_auth = base64.b64encode(auth_str.encode()).decode()
        self.github_token = github_token
        self.github_repo = github_repo
        self.base_url = "https://intervals.icu/api/v1"

    def _intervals_get(self, endpoint, params=None):
        url = f"{self.base_url}/athlete/{self.athlete_id}/{endpoint}"
        if not endpoint:
            url = f"{self.base_url}/athlete/{self.athlete_id}"
        
        headers = {"Authorization": f"Basic {self.intervals_auth}"}
        r = requests.get(url, headers=headers, params=params)
        r.raise_for_status()
        return r.json()

    def collect_latest_workout(self) -> Dict:
        print("Fetching latest workout from Intervals...")
        params = {"limit": 1, "order": "desc", "_cb": int(time.time())}
        try:
            activities = self._intervals_get("activities", params)
            if activities and isinstance(activities, list):
                print(f"✅ Found: {activities[0].get('name')}")
                return activities[0]
        except Exception as e:
            print(f"⚠️ Workout fetch failed: {e}")
        return {}

    def collect_summary(self, days=7):
        print(f"Fetching {days} days of summary data...")
        oldest = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        return self._intervals_get("activities", {"oldest": oldest})

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--athlete-id")
    parser.add_argument("--intervals-key")
    parser.add_argument("--github-token")
    parser.add_argument("--github-repo")
    parser.add_argument("--output")
    parser.add_argument("--days", type=int, default=7)
    args = parser.parse_args()

    sync = IntervalsSync(args.athlete_id, args.intervals_key, args.github_token, args.github_repo)
    
    # Get Data
    latest_workout = sync.collect_latest_workout()
    summary_data = sync.collect_summary(args.days)

    # Save Files Locally
    with open("latest-workout.json", "w") as f:
        json.dump(latest_workout, f, indent=2)
    with open("latest.json", "w") as f:
        json.dump(summary_data, f, indent=2)
    
    print("✅ Files written to disk successfully.")

if __name__ == "__main__":
    main()
