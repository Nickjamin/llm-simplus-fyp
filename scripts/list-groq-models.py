import requests
import json
import os

from dotenv import load_dotenv, dotenv_values 

load_dotenv()

url = "https://api.groq.com/openai/v1/models"
api_key = os.getenv("GROQ_API_KEY")

if api_key is None:
    print("No API key found")

headers = {"Authorization": f"Bearer {api_key}"}

response = requests.get(url, headers=headers)
data = response.json()

# usable_models = [m["id"] for m in data.get("data", []) if m.get("active") is True]

# print(f"Total returned: {len(data.get('data', []))}")
# print(f"Usable/Active:  {len(usable_models)}\n")
# print(json.dumps(usable_models, indent=2))

pretty_json = json.dumps(data,indent=4)
# print(pretty_json)