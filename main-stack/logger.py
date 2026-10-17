import csv
from datetime import datetime
import json
from pathlib import Path
from typing import Any, Dict, Optional

RESULTS_DIR = Path("eval_results")
RUNS_DIR = RESULTS_DIR / "runs"
CSV_PATH = RESULTS_DIR / "results.csv"

CSV_FIELDS = [
    "run_id",
    "timestamp",
    "model_name",
    "provider",
    "tier",
    "prompt_preview",
    "json_syntax_valid",
    "pydantic_valid",
    "matlab_status",        # e.g., "SKIPPED", "SOLVED", "UNSTABLE", "SYNTAX_ERROR"
    "failure_stage",        # "NONE", "API", "JSON_DECODE", "PYDANTIC", "MATLAB"
    "error_message",
    "run_dir"
]

def init_tracker():
    """Creates evaluation directories and initializes the CSV header if needed."""
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    if not CSV_PATH.exists():
        with open(CSV_PATH, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            writer.writeheader()

def log_evaluation_run(
    model_name: str,
    provider: str,
    tier: str,
    prompt: str,
    raw_response: Optional[str] = None,
    json_syntax_valid: bool = False,
    pydantic_valid: bool = False,
    compiled_data: Optional[Dict[str, Any]] = None,
    matlab_status: str = "SKIPPED",
    failure_stage: str = "NONE",
    error_message: str = "",
    matlab_log: str = ""
):
    init_tracker()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    clean_model_name = model_name.replace("/", "_").replace(":", "_")
    run_id = f"{timestamp}_{clean_model_name}"
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # Save artifact files
    (run_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
    
    if raw_response is not None:
        (run_dir / "raw_response.txt").write_text(raw_response, encoding="utf-8")
    
    if compiled_data is not None:
        (run_dir / "UserData.json").write_text(
            json.dumps(compiled_data, indent=2), encoding="utf-8"
        )
        
    if matlab_log:
        (run_dir / "matlab_output.log").write_text(matlab_log, encoding="utf-8")

    # Append row to CSV
    row = {
        "run_id": run_id,
        "timestamp": timestamp,
        "model_name": model_name,
        "provider": provider,
        "tier": tier,
        "prompt_preview": (prompt[:60] + "...") if len(prompt) > 60 else prompt,
        "json_syntax_valid": json_syntax_valid,
        "pydantic_valid": pydantic_valid,
        "matlab_status": matlab_status,
        "failure_stage": failure_stage,
        "error_message": error_message.replace("\n", " ")[:200],
        "run_dir": str(run_dir)
    }

    with open(CSV_PATH, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writerow(row)

    print(f"[TRACKER] Run logged to {CSV_PATH} (Run ID: {run_id})")