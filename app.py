from flask import Flask, jsonify, request
import requests
from datetime import datetime, timezone
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

API_KEY = "dcb3265445418c9589fa4af3b366cb35"
SPORTS = ["baseball_mlb", "basketball_nba"]
REGIONS = "us"
MARKET = "h2h"
BOOKMAKERS_FILTER = {"FanDuel", "DraftKings", "Bet365", "theScore", "BallyBet", "BetMGM"}

def get_odds():
    all_events = []
    for sport in SPORTS:
        url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds"
        params = {
            'apiKey': API_KEY,
            'regions': REGIONS,
            'markets': MARKET,
            'oddsFormat': 'decimal'
        }
        response = requests.get(url, params=params)
        if response.status_code == 200:
            all_events.extend(response.json())
    return all_events

def find_arbitrage(odds, profit_goal):
    if len(odds) < 2:
        return None
    for i in range(len(odds)):
        for j in range(i + 1, len(odds)):
            o1 = odds[i]
            o2 = odds[j]
            if o1['team'] == o2['team']:
                continue
            inv1 = 1 / o1['price']
            inv2 = 1 / o2['price']
            total_inv = inv1 + inv2
            if total_inv < 1:
                stake = profit_goal / (1 - total_inv)
                bet1 = round(stake * inv1, 2)
                bet2 = round(stake * inv2, 2)
                profit = round(min(bet1 * o1['price'] - stake, bet2 * o2['price'] - stake), 2)
                return {
                    "team_1": o1['team'],
                    "team_2": o2['team'],
                    "bookmaker_1": o1['bookmaker'],
                    "bookmaker_2": o2['bookmaker'],
                    "odds_1": o1['price'],
                    "odds_2": o2['price'],
                    "bet_1": bet1,
                    "bet_2": bet2,
                    "total_bet": round(bet1 + bet2, 2),
                    "guaranteed_profit": profit
                }
    return None

@app.route("/api/odds")
def odds_api():
    profit_goal = float(request.args.get("profit", 50))
    selected_date = request.args.get("date")
    try:
        selected_date = datetime.strptime(selected_date, "%Y-%m-%d").date()
    except:
        selected_date = datetime.now(timezone.utc).date()

    events = get_odds()
    result = {"MLB": [], "NBA": []}
    for event in events:
        try:
            if 'commence_time' not in event:
                continue
            start_time = datetime.fromisoformat(event['commence_time'].replace("Z", "+00:00"))
            if start_time.date() != selected_date:
                continue

            match_data = {
                "match": event.get('home_team', 'Unknown') + " vs " + event.get('away_team', 'Unknown'),
                "start_time": event['commence_time'],
                "odds": []
            }

            for bookmaker in event.get('bookmakers', []):
                if bookmaker['title'] not in BOOKMAKERS_FILTER:
                    continue
                if 'markets' not in bookmaker or not bookmaker['markets']:
                    continue
                for outcome in bookmaker['markets'][0].get('outcomes', []):
                    match_data['odds'].append({
                        "bookmaker": bookmaker['title'],
                        "team": outcome.get('name'),
                        "price": outcome.get('price')
                    })

            arb = find_arbitrage(match_data['odds'], profit_goal)
            if arb:
                match_data['arbitrage'] = arb

            if "baseball_mlb" in event.get('sport_key', ''):
                result["MLB"].append(match_data)
            elif "basketball_nba" in event.get('sport_key', ''):
                result["NBA"].append(match_data)
        except:
            continue

    return jsonify(result)

if __name__ == "__main__":
    app.run(debug=True)
