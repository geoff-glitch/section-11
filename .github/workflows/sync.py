#!/usr/bin/env python3
"""
Intervals.icu → GitHub/Local JSON Export
Revised to include latest-workout.json
"""

import requests
import json
import os
import argparse
from datetime import datetime, timedelta
from typing import Dict, List
import base64
import math

class IntervalsSync:
    """Sync Intervals.icu data to GitHub repository or local file"""
    
    INTERVALS_BASE_URL = "https://intervals.icu/api/v1"
    GITHUB_API_URL = "https://api.github.com"
    
    def __init__(self, athlete_id: str, intervals_api_key: str, github_token: str = None, 
                 github_repo: str = None, debug: bool = False):
        self.athlete_id = athlete_id
        self.intervals_auth = base64.b64encode(f"API_KEY:{intervals_api_key}".encode()).decode()
        self.github_token = github_token
        self.github_repo = github_repo
        self.debug = debug
    
    def _intervals_get(self, endpoint: str, params: Dict = None) -> Dict:
        """Fetch from Intervals.icu API"""
        if endpoint:
            url = f"{self.INTERVALS_BASE_URL}/athlete/{self.athlete_id}/{endpoint}"
        else:
            url = f"{self.INTERVALS_BASE_URL}/athlete/{self.athlete_id}"
        headers = {
            "Authorization": f"Basic {self.intervals_auth}",
            "Accept": "application/json"
        }
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()

    def collect_latest_workout(self) -> Dict:
        """Fetch the absolute latest workout with cache-busting to ensure fresh data"""
        import time
        print("Fetching the absolute latest workout...")
        
        params = {
            "limit": 1, 
            "order": "desc", 
            "_cb": int(time.time())
        }
        
        try:
            activities = self._intervals_get("activities", params)
            if activities and isinstance(activities, list):
                act = activities[0]
                print(f"✅ Found latest activity: {act.get('name')} (ID: {act.get('id')})")
                return act
            elif isinstance(activities, dict):
                return activities
        except Exception as e:
            print(f"⚠️ Could not fetch latest workout: {e}")
            
        return {}

    def collect_training_data(self, days_back: int = 7, anonymize: bool = False) -> Dict:
        """Collect all training data for LLM analysis"""
        oldest = (datetime.now() - timedelta(days=days_back - 1)).strftime("%Y-%m-%d")
        newest = datetime.now().strftime("%Y-%m-%d")
        
        print("Fetching athlete data...")
        athlete = self._intervals_get("")
        
        cycling_settings = None
        if athlete.get("sportSettings"):
            for sport in athlete["sportSettings"]:
                if "Ride" in sport.get("types", []) or "VirtualRide" in sport.get("types", []):
                    cycling_settings = sport
                    break
        
        print("Fetching activities...")
        activities = self._intervals_get("activities", {"oldest": oldest, "newest": newest})
        
        print("Fetching wellness data...")
        wellness = self._intervals_get("wellness", {"oldest": oldest, "newest": newest})
        
        print("Fetching actual fitness metrics (yesterday + decay)...")
        try:
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            yesterday_wellness = self._intervals_get("wellness", {"oldest": yesterday, "newest": yesterday})
            yesterday_data = yesterday_wellness[0] if yesterday_wellness else {}
            
            ctl_decay = math.exp(-1/42)
            atl_decay = math.exp(-1/7)
            
            yesterday_ctl = yesterday_data.get("ctl")
            yesterday_atl = yesterday_data.get("atl")
            yesterday_ramp = yesterday_data.get("rampRate")
            
            ctl = round(yesterday_ctl * ctl_decay, 2) if yesterday_ctl else None
            atl = round(yesterday_atl * atl_decay, 2) if yesterday_atl else None
            ramp_rate = round(yesterday_ramp * ctl_decay, 2) if yesterday_ramp else None
        except:
            ctl = atl = ramp_rate = None
        
        tsb = round(ctl - atl, 2) if (ctl is not None and atl is not None) else None
        latest_wellness = wellness[-1] if wellness else {}
        
        print("Fetching planned workouts...")
        newest_ahead = (datetime.now() + timedelta(days=21)).strftime("%Y-%m-%d")
        events = self._intervals_get("events", {"oldest": datetime.now().strftime("%Y-%m-%d"), "newest": newest_ahead})
        
        data = {
            "READ_THIS_FIRST": {
                "instruction_for_ai": "DO NOT calculate totals from individual activities. Use pre-calculated values.",
                "data_period": f"Last {days_back} days",
                "quick_stats": {
                    "total_training_hours": round(sum(act.get("moving_time", 0) for act in activities) / 3600, 2),
                    "total_activities": len(activities),
                    "total_tss": round(sum(act.get("icu_training_load", 0) for act in activities if act.get("icu_training_load")), 0)
                }
            },
            "metadata": {
                "athlete_id": "REDACTED" if anonymize else self.athlete_id,
                "last_updated": datetime.now().isoformat(),
                "data_range_days": days_back
            },
            "summary": self._compute_activity_summary(activities, days_back),
            "current_status": {
                "fitness": {"ctl": ctl, "atl": atl, "tsb": tsb, "ramp_rate": ramp_rate},
                "thresholds": {
                    "ftp": cycling_settings.get("ftp") if cycling_settings else None,
                    "lthr": cycling_settings.get("lthr") if cycling_settings else None
                },
                "current_metrics": {
                    "weight_kg": latest_wellness.get("weight") or athlete.get("icu_weight"),
                    "resting_hr": latest_wellness.get("restingHR") or athlete.get("icu_resting_hr"),
                    "hrv": latest_wellness.get("hrv")
                }
            },
            "recent_activities": self._format_activities(activities, anonymize),
            "wellness_data": self._format_wellness(wellness),
            "planned_workouts": self._format_events(events, anonymize),
            "weekly_summary": self._compute_weekly_summary(activities, wellness)
        }
        return data

    def _format_activities(self, activities: List[Dict], anonymize: bool = False) -> List[Dict]:
        formatted = []
        for i, act in enumerate(activities):
            activity = {
                "id": f"activity_{i+1}" if anonymize else act["id"],
                "date": act["start_date_local"],
                "type": act["type"],
                "name": "Training Session" if anonymize and "Virtual" not in act.get("type", "") else act.get("name", ""),
                "duration_hours": round((act.get("moving_time") or 0) / 3600, 2),
                "distance_km": round((act.get("distance") or 0) / 1000, 2),
                "tss": act.get("icu_training_load"),
                "avg_power": act.get("average_watts"),
                "normalized_power": act.get("icu_weighted_avg_watts"),
                "avg_hr": act.get("icu_average_hr"),
                "decoupling": act.get("icu_hr_decoupling")
            }
            formatted.append(activity)
        return formatted

    def _format_wellness(self, wellness: List[Dict]) -> List[Dict]:
        return [{"date": w["id"], "hrv_rmssd": w.get("hrv"), "resting_hr": w.get("restingHR")} for w in wellness]

    def _format_events(self, events: List[Dict], anonymize: bool = False) -> List[Dict]:
        return [{"date": evt["start_date_local"], "name": evt.get("name", "")} for evt in events]

    def _compute_weekly_summary(self, activities: List[Dict], wellness: List[Dict]) -> Dict:
        return {"activities_count": len(activities)}

    def _compute_activity_summary(self, activities: List[Dict], days_back: int = 7) -> Dict:
        return {"total_activities": len(activities)}

def publish_to_github(self, data: Dict, path: str, message: str) -> str:
        import base64
        import json
        
        # 1. Convert data to JSON string
        new_content = json.dumps(data, indent=2)
        
        # 2. Get the current file SHA (Required by GitHub API for updates)
        sha = None
        headers = {"Authorization": f"token {self.github_token}", "Accept": "application/vnd.github+json"}
        url = f"https://api.github.com/repos/{self.github_repo}/contents/{path}"
        
        try:
            resp = requests.get(url, headers=headers)
            if resp.status_code == 200:
                sha = resp.json().get("sha")
                print(f"🔄 Updating existing file: {path} (SHA: {sha[:6]}...)")
            else:
                print(f"🆕 Creating new file: {path}")
        except:
            pass

        # 3. Prepare the commit payload
        payload = {
            "message": message,
            "content": base64.b64encode(new_content.encode()).decode(),
            "branch": "main"
        }
        if sha:
            payload["sha"] = sha

        # 4. Push to GitHub
        response = requests.put(url, headers=headers, json=payload)
        
        if response.status_code in [200, 201]:
            print(f"✨ Successfully pushed {path} to GitHub.")
            return response.json()["content"]["html_url"]
        else:
            print(f"❌ FAILED to push {path}. Status: {response.status_code}")
            print(f"Reason: {response.text}")
            return ""
            
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--athlete-id", help="Intervals.icu athlete ID")
    parser.add_argument("--intervals-key", help="Intervals.icu API key")
    parser.add_argument("--github-token", help="GitHub Token")
    parser.add_argument("--github-repo", help="GitHub repo")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--output", help="Save locally")
    parser.add_argument("--anonymize", action="store_true", default=True)
    
    args = parser.parse_args()
    
    # Load config if exists
    config = {}
    if os.path.exists(".sync_config.json"):
        with open(".sync_config.json") as f:
            config = json.load(f)
    
    athlete_id = args.athlete_id or config.get("athlete_id")
    intervals_key = args.intervals_key or config.get("intervals_key")
    github_token = args.github_token or config.get("github_token")
    github_repo = args.github_repo or config.get("github_repo")

    sync = IntervalsSync(athlete_id, intervals_key, github_token, github_repo)
    
    # 1. Sync Wellness/Summary Data
    print("Step 1: Syncing Summary Data...")
    data = sync.collect_training_data(days_back=args.days, anonymize=args.anonymize)
    
    # 2. Sync Latest Single Workout
    print("Step 2: Syncing Detailed Workout...")
    latest_workout = sync.collect_latest_workout()
    
    if args.output:
        sync.save_to_file(data, "latest.json")
        sync.save_to_file(latest_workout, "latest-workout.json")
    else:
        # We add a timestamp to the commit message to force visibility in GitHub
        now_ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        url_summary = sync.publish_to_github(data, "latest.json", f"Summary Update {now_ts}")
        print(f"✅ Summary synced: {url_summary}")
        
        # If latest_workout is empty, the script will now print a warning
        if latest_workout and latest_workout.get('id'):
            url_workout = sync.publish_to_github(latest_workout, "latest-workout.json", f"Workout Update {latest_workout.get('id')} - {now_ts}")
            print(f"✅ Workout synced: {url_workout}")
        else:
            print("⚠️ No valid latest workout found to sync.")
