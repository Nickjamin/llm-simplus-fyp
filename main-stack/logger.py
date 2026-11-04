import csv
from datetime import datetime
import json
from pathlib import Path
from typing import Any, Dict, List

RESULTS_DIR = Path("eval_results")
RUNS_DIR = RESULTS_DIR / "runs"
CSV_PATH = RESULTS_DIR / "results.csv"

# Updated to the flattened "wide" format supporting up to 5 iterations
CSV_FIELDS = [
    "run_id", "timestamp", "model_name", "provider", "tier", 
    "prompt_name", "prompt_preview", "api_status", "iterations_needed",
    "it1_json_syntax_valid", "it1_pydantic_valid", "it1_matlab_status", "it1_failure_stage", "it1_error_message",
    "it2_json_syntax_valid", "it2_pydantic_valid", "it2_matlab_status", "it2_failure_stage", "it2_error_message",
    "it3_json_syntax_valid", "it3_pydantic_valid", "it3_matlab_status", "it3_failure_stage", "it3_error_message",
    "it4_json_syntax_valid", "it4_pydantic_valid", "it4_matlab_status", "it4_failure_stage", "it4_error_message",
    "it5_json_syntax_valid", "it5_pydantic_valid", "it5_matlab_status", "it5_failure_stage", "it5_error_message",
    "run_dir"
]

def init_tracker():
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    if not CSV_PATH.exists():
        with open(CSV_PATH, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            writer.writeheader()

def log_evaluation_run(
    model_name: str,
    provider: str,
    tier: str,
    prompt_name: str,
    prompt: str,
    api_status: str,
    iterations_needed: int,
    iteration_data: List[Dict[str, Any]],
    verbose: bool = False
):
    init_tracker()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    clean_model_name = model_name.replace("/", "_").replace(":", "_")
    run_id = f"{timestamp}_{clean_model_name}"
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # Save the original prompt once
    (run_dir / "prompt.txt").write_text(prompt, encoding="utf-8")

    row = {
        "run_id": run_id,
        "timestamp": timestamp,
        "model_name": model_name,
        "provider": provider,
        "tier": tier,
        "prompt_name": prompt_name,
        "prompt_preview": (prompt[:60] + "...") if len(prompt) > 60 else prompt,
        "api_status": api_status,
        "iterations_needed": iterations_needed,
        "run_dir": str(run_dir)
    }

    # Initialize all iteration columns to empty strings/defaults
    for i in range(1, 6):
        row[f"it{i}_json_syntax_valid"] = ""
        row[f"it{i}_pydantic_valid"] = ""
        row[f"it{i}_matlab_status"] = ""
        row[f"it{i}_failure_stage"] = ""
        row[f"it{i}_error_message"] = ""

    # Populate the wide columns and save iteration-specific artifacts
    for idx, it in enumerate(iteration_data):
        i = idx + 1  # 1-indexed for columns (it1, it2, it3)
        row[f"it{i}_json_syntax_valid"] = it.get("json_syntax_valid", False)
        row[f"it{i}_pydantic_valid"] = it.get("pydantic_valid", False)
        row[f"it{i}_matlab_status"] = it.get("matlab_status", "SKIPPED")
        row[f"it{i}_failure_stage"] = it.get("failure_stage", "NONE")
        row[f"it{i}_error_message"] = str(it.get("error_message", "")).replace("\n", " ")[:200]

        if it.get("raw_response"):
            (run_dir / f"it{i}_raw_response.txt").write_text(it["raw_response"], encoding="utf-8")
        if it.get("compiled_data"):
            (run_dir / f"it{i}_UserData.json").write_text(json.dumps(it["compiled_data"], indent=2), encoding="utf-8")
        if it.get("matlab_log"):
            (run_dir / f"it{i}_matlab_output.log").write_text(it["matlab_log"], encoding="utf-8")

    with open(CSV_PATH, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writerow(row)

    if verbose:
        print(f"[TRACKER] Run logged to {CSV_PATH} (Run ID: {run_id})")