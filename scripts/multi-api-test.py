import os
import sys
from openai import APIConnectionError, APIStatusError, AuthenticationError, OpenAI


# Define Providers and Models
PROVIDERS = {
    "google": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "api_key": os.getenv("GEMINI_API_KEY")
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "api_key": os.getenv("GROQ_API_KEY")
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "api_key": os.getenv("OPNRTR_API_KEY")
    }
}

MODELS = {
    "gemini-3.1-flash-lite": {"provider": "google", "id": "gemini-3.1-flash-lite"},
    "gemini-3.6-flash": {"provider": "google", "id": "gemini-3.6-flash"},
    "gemini-3.8-flash": {"provider": "google", "id": "gemini-3.8-flash"},
    "gpt-oss-120b": {"provider": "groq", "id": "openai/gpt-oss-120b"},
    "gpt-oss-20b": {"provider": "groq", "id": "openai/gpt-oss-20b"},
    "qwen3.8-27b": {"provider": "groq", "id": "qwen/qwen3.8-27b"},
    "nemotron-3-ultra-550b-a55b": {"provider": "openrouter", "id": "nvidia/nemotron-3-ultra-550b-a55b:free"},
    "nemotron-3-super-120b-a12b": {"provider": "openrouter", "id": "nvidia/nemotron-3-super-120b-a12b:free"},
    "laguna-s-2.1": {"provider": "openrouter", "id": "poolside/laguna-s-2.1:free"},
    "north-mini-code": {"provider": "openrouter", "id": "cohere/north-mini-code:free"},
    "gemma-4-31b": {"provider": "openrouter", "id": "google/gemma-4-31b:free"},
    "nemotron-3.5-super-vl": {"provider": "openrouter", "id": "nvidia/nemotron-3.5-super-vl:free"},
}

# Get user to select model
model_choices = {
    str(idx): name for idx, name in enumerate(MODELS.keys(), start=1)
}

selected_model_key = None

while not selected_model_key:
    print("\n--- Available Models ---")
    for num, name in model_choices.items():
        print(f"{num} - {name}")

    user_input = input("Choose model (number): ").strip()

    if user_input in model_choices:
        selected_model_key = model_choices[user_input]
    else:
        print("Invalid selection. Please enter a valid number.")


# Resolve the configuration variables
model_cfg = MODELS[selected_model_key]
provider_cfg = PROVIDERS[model_cfg["provider"]]

target_url = provider_cfg["base_url"]
target_key = provider_cfg["api_key"]
target_model_id = model_cfg["id"]


# Validate API key exists before attempting connection
if not target_key:
    print(
        f"[ERROR] Environment variable for provider '{model_cfg['provider']}' is not set.",
        file=sys.stderr,
    )
    sys.exit(1)

print(f"\n[INFO] Initializing client for {selected_model_key}...")  


# Initialize client
try:
    client = OpenAI(
        base_url=target_url,
        api_key=target_key,
        timeout=15.0
    )
except Exception as e:
    print(f"[ERROR] Client configuration failure: {e}", file=sys.stderr)
    sys.exit(1)

print("[INFO] Client initialized locally. Sending request...")


# Execute and catch API/network failures
try:
    response = client.chat.completions.create(
        model=target_model_id,  
        messages=[
            {
                "role": "system",
                "content": "You are a helpful assistant"
            },
            {
                "role": "user",
                "content": "Write a funny thought in a sentence or two.",
            },
        ],
    )

    if not response.choices or not response.choices[0].message.content:
        print(
            "[WARN] Received empty choice payload from endpoint.",
            file=sys.stderr,
        )
    else:
        print("[SUCCESS] Response received:\n")
        print(response.choices[0].message.content)
        print()
        print(response.choices[0].message)

except AuthenticationError:
    print("[ERROR] 401: Invalid API key or unauthorized.", file=sys.stderr)
except APIConnectionError as e:
    print(
        f"[ERROR] Network failure: Unable to reach endpoint. {e.__cause__}",
        file=sys.stderr,
    )
except APIStatusError as e:
    print(
        f"[ERROR] API returned HTTP {e.status_code}: {e.message}",
        file=sys.stderr,
    )
except Exception as e:
    print(f"[ERROR] Unexpected failure: {e}", file=sys.stderr)