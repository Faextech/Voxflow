import urllib.request
import json
import os

try:
    req = urllib.request.urlopen("http://127.0.0.1:4040/api/requests/http?limit=15")
    data = json.loads(req.read().decode())
    print("--- NGROK REQUESTS ---")
    for r in data.get('requests', []):
        method = r['request']['method']
        uri = r['request']['uri']
        status = r['response']['status_code']
        print(f"{method} {uri} -> {status}")
except Exception as e:
    print(f"Error fetching ngrok api: {e}")
