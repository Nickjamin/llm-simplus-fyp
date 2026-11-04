import json
import os
from pathlib import Path
from dotenv import load_dotenv
from schema import SimplusGTModelLLM

load_dotenv()

# --- Simplus Grid Tool Path Configuration ---
# Looks for SIMPLUS_DIR in .env, falling back to ~/Documents/MATLAB/...
DEFAULT_SIMPLUS_PATH = Path.home() / "Documents" / "MATLAB" / "Simplus-Grid-Tool-master"
raw_simplus_dir = os.getenv("SIMPLUS_DIR")

SIMPLUS_DIR = (
    Path(raw_simplus_dir).expanduser().resolve()
    if raw_simplus_dir
    else DEFAULT_SIMPLUS_PATH.resolve()
)

if not SIMPLUS_DIR.is_dir():
    raise FileNotFoundError(
        f"[CONFIG ERROR] Simplus directory not found at: {SIMPLUS_DIR}\n"
        f"Please verify or set SIMPLUS_DIR in your .env file."
    )

# --- Provider & API Configurations ---
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
    # --- Fast Iteration & Baseline APIs ---
    "gemini-3.1-flash-lite": {"provider": "google", "id": "gemini-3.1-flash-lite", "tier": "lite-prototype"},
    "gemini-3.5-flash-lite": {"provider": "google", "id": "gemini-3.5-flash-lite", "tier": "lite-prototype"},
    # "gemini-3.6-flash":      {"provider": "google", "id": "gemini-3.6-flash",      "tier": "strong-workhorse"},
    # "gemini-3.8-flash":      {"provider": "google", "id": "gemini-3.8-flash",      "tier": "strong-workhorse"},
    # "gemini-3-flash":        {"provider": "google", "id": "gemini-3-flash-preview",      "tier": "strong-workhorse"},

    # --- Ultra-Fast Open-Weights (Groq LPUs) ---
    # "gpt-oss-20b":           {"provider": "groq",   "id": "openai/gpt-oss-20b",     "tier": "fast-edge"},
    # "qwen3.8-27b":           {"provider": "groq",   "id": "qwen/qwen3.8-27b",       "tier": "balanced-fast"},
    # "gpt-oss-120b":          {"provider": "groq",   "id": "openai/gpt-oss-120b",    "tier": "heavy-fast"},

    # --- Code & Structured Specialists (OpenRouter Free) ---
    # "north-mini-code":       {"provider": "openrouter", "id": "cohere/north-mini-code:free", "tier": "code-specialist-small"},
    # "laguna-s-2.1":          {"provider": "openrouter", "id": "poolside/laguna-s-2.1:free",  "tier": "code-specialist-large"},

    # --- Frontier & Large Open-Weights (OpenRouter Free) ---
    # "gemma-4-26b-a4b-it":    {"provider": "openrouter", "id": "google/gemma-4-26b-a4b-it:free", "tier": "balanced-eval"},
    # "gemma-4-31b-it":        {"provider": "openrouter", "id": "google/gemma-4-31b-it:free", "tier": "balanced-eval"},
    # "nemotron-3.5-super-vl": {"provider": "openrouter", "id": "nvidia/nemotron-3.5-super-vl:free", "tier": "heavy-eval"},
    # "nemotron-3-ultra-550b": {"provider": "openrouter", "id": "nvidia/nemotron-3-ultra-550b-a55b:free", "tier": "frontier-eval"},
}

def build_system_prompt() -> str:
    schema_json = json.dumps(SimplusGTModelLLM.model_json_schema(), indent=2)
    return (
        "You are an expert power systems engineer configuring AC grids for SimplusGT.\n"
        "Respond ONLY with a raw, valid JSON object that strictly adheres to the JSON Schema below.\n"
        "Do NOT wrap the JSON in markdown code fences (```json) or include any conversational text.\n\n"
        "CRITICAL TOPOLOGY RULES:\n"
        "1. BusNo must be sequential starting from 1.\n"
        "2. Bus 1 (and ONLY Bus 1) must be the Slack Bus (BusType: 1).\n"
        "3. Shunt loads/capacitors are represented in NetworkLine as self-branches (FromBus == ToBus) "
        "with R: 'NaN', wL: 'NaN', and non-zero G or wC.\n"
        "4. Leave ParaOverrides null unless the user explicitly requests non-default device parameters.\n\n"
        f"JSON SCHEMA:\n{schema_json}"
    )