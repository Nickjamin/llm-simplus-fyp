import os
import re
import sys
import json
import time
import argparse
from openai import (
    APIConnectionError,
    APIStatusError,
    AuthenticationError,
    InternalServerError,
    RateLimitError,
    OpenAI,
)
from pydantic import ValidationError

from config import MODELS, PROVIDERS, SIMPLUS_DIR, build_system_prompt
from compiler import save_simplus_json, compile_to_simplus_dict
from schema import SimplusGTModelLLM
from logger import log_evaluation_run
from matlab_bridge import start_matlab_engine, run_simplus_headless

def prompt_input(prompt_text: str = "") -> str:
    try:
        val = input(prompt_text).strip()
    except (KeyboardInterrupt, EOFError):
        print("\n\nOperation cancelled. Exiting.")
        sys.exit(0)
        
    if val.lower() in {"quit", "exit", "q"}:
        print("\nExiting.")
        sys.exit(0)
    return val

def strip_markdown_fences(text: str) -> str:
    text = text.strip()
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    return match.group(1).strip() if match else text

def get_prompts_db(file_path) -> dict:
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

def run_evaluation(
    selected_model_key: str, 
    prompt_name: str, 
    user_prompt: str, 
    eng, 
    run_idx: int = 1, 
    total_runs: int = 1,
    delay_sec: int = 15,
    show_plots: bool = False
):
    """Handles the 3-iteration evaluation loop for a model/prompt combination with in-place terminal updates."""
    model_cfg = MODELS[selected_model_key]
    provider_cfg = PROVIDERS[model_cfg["provider"]]

    target_url = provider_cfg["base_url"]
    target_key = provider_cfg["api_key"]
    target_model_id = model_cfg["id"]

    prefix = f"[{run_idx:02d}/{total_runs:02d}] {selected_model_key:<22} | {prompt_name:<22} |"

    def update_status(step_msg: str):
        # \r moves to the start of the line; \033[K clears everything to the right
        print(f"\r\033[K{prefix} {step_msg}", end="", flush=True)

    if not target_key:
        print(f"\r\033[K{prefix} ERROR (API key not set for '{model_cfg['provider']}')")
        return eng

    start_time = time.perf_counter()
    client = OpenAI(base_url=target_url, api_key=target_key, timeout=60.0)

    messages = [
        {"role": "system", "content": build_system_prompt()},
        {"role": "user", "content": user_prompt},
    ]

    user_data_path = SIMPLUS_DIR / "UserData.json"
    max_iterations = 5
    iteration_data = []
    api_status = "SUCCESS"
    iterations_needed = 0
    final_status = "FAILED"

    for attempt in range(max_iterations):
        iterations_needed = attempt + 1
        it_num = f"Iter {iterations_needed}/{max_iterations}"
        
        it_state = {
            "json_syntax_valid": False,
            "pydantic_valid": False,
            "matlab_status": "PENDING",
            "failure_stage": "NONE",
            "error_message": "",
            "raw_response": "",
            "compiled_data": None,
            "matlab_log": ""
        }

        # 1. API Call with Transient Retry Logic
        update_status(f"{it_num} -> Calling API...")
        api_success = False
        api_retries = 3
        
        for attempt_api in range(api_retries):
            try:
                response = client.chat.completions.create(
                    model=target_model_id,
                    messages=messages,
                    temperature=0.1,
                    max_completion_tokens=32768
                )
                it_state["raw_response"] = response.choices[0].message.content
                
                if response.choices[0].finish_reason == "length":
                    it_state["failure_stage"] = "TOKEN_LIMIT"
                    it_state["error_message"] = "Model reached maximum output token limit. Output truncated."
                    api_success = True
                    break
                    
                if not it_state["raw_response"]:
                    raise ValueError("Empty response from endpoint.")
                    
                api_success = True
                break

            except (RateLimitError, InternalServerError, APIConnectionError) as e:
                # Transient errors: 429 rate limit, 5xx server issues, or dropouts
                if attempt_api < api_retries - 1:
                    wait_sec = 25 * (attempt_api + 1) if isinstance(e, RateLimitError) else 5
                    update_status(f"{it_num} -> Transient {type(e).__name__}. Retrying in {wait_sec}s ({attempt_api + 1}/{api_retries})...")
                    time.sleep(wait_sec)
                else:
                    api_status = f"API_ERROR: {type(e).__name__}"
                    it_state["failure_stage"] = "API"
                    it_state["error_message"] = str(e)
                    
            except (AuthenticationError, APIStatusError) as e:
                # Hard client errors: 400 Bad Request, 401 Auth, 404 Not Found (fail immediately)
                api_status = f"API_ERROR: {type(e).__name__}"
                it_state["failure_stage"] = "API"
                it_state["error_message"] = str(e)
                break
                
            except Exception as e:
                api_status = "UNKNOWN_API_ERROR"
                it_state["failure_stage"] = "API"
                it_state["error_message"] = str(e)
                break

        if not api_success:
            iteration_data.append(it_state)
            final_status = f"FAILED [{it_state['failure_stage']}]"
            break
            
        if it_state.get("failure_stage") == "TOKEN_LIMIT":
            iteration_data.append(it_state)
            final_status = "FAILED [TOKEN_LIMIT]"
            break

        # 2. Schema Validation
        update_status(f"{it_num} -> Validating Schema...")
        try:
            cleaned_json = strip_markdown_fences(it_state["raw_response"])
            json.loads(cleaned_json)
            it_state["json_syntax_valid"] = True

            validated_model = SimplusGTModelLLM.model_validate_json(cleaned_json)
            it_state["pydantic_valid"] = True

            it_state["compiled_data"] = compile_to_simplus_dict(validated_model)
            save_simplus_json(validated_model, filepath=str(user_data_path))
            
            # 3. MATLAB Execution
            update_status(f"{it_num} -> Running MATLAB...")
            
            # Prevent calling MATLAB if a previous run killed the engine
            if eng is None:
                it_state["matlab_status"] = "ENGINE_DEAD"
                it_state["failure_stage"] = "MATLAB"
                it_state["error_message"] = "MATLAB engine is dead."
                raise RuntimeError("MATLAB Engine Dead")

            # Pass the show_plots flag to the run_simplus_headless function
            m_success, m_out, m_err, m_errmsg, eng = run_simplus_headless(
                eng, str(SIMPLUS_DIR), timeout_sec=60, show_plots=show_plots
            )
            it_state["matlab_log"] = m_out + "\n" + m_err
            
            # Catch if engine crashed during this run's execution/recovery
            if eng is None:
                it_state["matlab_status"] = "ENGINE_CRASHED"
                it_state["failure_stage"] = "MATLAB"
                it_state["error_message"] = "Engine crashed and failed to restart."
                raise RuntimeError("MATLAB Engine Crash Recovery Failed")
            
            if m_success:
                if "unstable" in m_out.lower():
                    it_state["matlab_status"] = "UNSTABLE"
                    final_status = "SOLVED (UNSTABLE)"
                else:
                    it_state["matlab_status"] = "SOLVED"
                    final_status = "SOLVED"
                iteration_data.append(it_state)
                
                if show_plots:
                    prompt_input(f"\n\n[PAUSE] {final_status}: Review MATLAB figures, then press Enter to continue...")
                    
                break
            else:
                it_state["matlab_status"] = "SYNTAX_ERROR"
                it_state["failure_stage"] = "MATLAB"
                it_state["error_message"] = m_errmsg
                raise RuntimeError("MATLAB Execution Failed")

        except json.JSONDecodeError as e:
            it_state["failure_stage"] = "JSON_DECODE"
            it_state["error_message"] = str(e)
        except ValidationError as e:
            it_state["failure_stage"] = "PYDANTIC"
            it_state["error_message"] = str(e)
        except Exception as e:
            if it_state["failure_stage"] == "NONE":
                it_state["failure_stage"] = "UNKNOWN"
                it_state["error_message"] = str(e)

        iteration_data.append(it_state)
        final_status = f"FAILED [{it_state['failure_stage']}]"

        if attempt < max_iterations - 1:
            messages.append({"role": "assistant", "content": it_state["raw_response"]})
            messages.append({
                "role": "user", 
                "content": f"The previous configuration failed at the {it_state['failure_stage']} stage with this error:\n{it_state['error_message']}\nCorrect the JSON structure and regenerate."
            })

            if delay_sec > 0:
                update_status(f"{it_num} -> Pacing API... waiting {delay_sec}s")
                time.sleep(delay_sec)

    elapsed = time.perf_counter() - start_time

    # Lock final status line into terminal history
    print(f"\r\033[K{prefix} It: {iterations_needed}/{max_iterations} | {final_status} ({elapsed:.2f}s)")

    log_evaluation_run(
        model_name=selected_model_key,
        provider=model_cfg["provider"],
        tier=model_cfg.get("tier", "unknown"),
        prompt_name=prompt_name,
        prompt=user_prompt,
        api_status=api_status,
        iterations_needed=iterations_needed,
        iteration_data=iteration_data,
        verbose=False
    )

    return eng

def main():
    parser = argparse.ArgumentParser(description="SimplusGT LLM Configuration Evaluator")
    parser.add_argument("--model", type=str, help="Specific model key or 'all' to batch evaluate all models.")
    parser.add_argument("--prompt", type=str, help="Specific prompt name or 'all' to batch evaluate all prompts.")
    parser.add_argument("--delay", type=int, default=15, help="Seconds to wait between API calls to prevent 429 rate limits.")
    parser.add_argument("--prompt-file", type=str, default="prompts_examples.json", help="specific prompt json file to use")
    parser.add_argument("--show-plots", action="store_true", help="Show MATLAB figure windows and plots.")
    args = parser.parse_args()

    prompts_db = get_prompts_db(args.prompt_file)

    # Determine Models
    if args.model == "all":
        from collections import defaultdict
        
        # Group models by their provider
        provider_groups = defaultdict(list)
        for m_key, m_data in MODELS.items():
            provider_groups[m_data["provider"]].append(m_key)
            
        # Interleave models (Round-Robin)
        models_to_run = []
        while any(provider_groups.values()):
            for provider in list(provider_groups.keys()):
                if provider_groups[provider]:
                    models_to_run.append(provider_groups[provider].pop(0))
    elif args.model in MODELS:
        models_to_run = [args.model]
    else:
        model_choices = {str(idx): key for idx, key in enumerate(MODELS.keys(), start=1)}
        print("\n    -----------  Available Models  -----------    ")
        for num, key in model_choices.items():
            print(f"{num:>2}: {key:<26} [{MODELS[key].get('tier')}]")
        
        # Input Validation Loop for Models
        while True:
            user_input = prompt_input("\nChoose model (number): ")
            if user_input in model_choices:
                models_to_run = [model_choices[user_input]]
                break
            print(f"Invalid input. Please enter a number between 1 and {len(model_choices)}.")

    # Determine Prompts
    if args.prompt == "all":
        prompts_to_run = [(name, data.get("high_level", "")) for name, data in prompts_db.items()]
    elif args.prompt in prompts_db:
        prompts_to_run = [(args.prompt, prompts_db[args.prompt].get("high_level", ""))]
    else:
        options = []
        print("\n    -----------  Available Prompts  -----------    ")
        print(" 0: [Write manual prompt]")
        for idx, (name, data) in enumerate(prompts_db.items(), start=1):
            options.append((name, data.get("high_level", "")))
            print(f"{idx:>2}: {name}")
        
        while True:
            user_input = prompt_input("\nChoose prompt (number): ")
            try:
                choice = int(user_input)
                if choice == 0:
                    custom_prompt = prompt_input("\nEnter your custom prompt: ")
                    prompts_to_run = [("custom_manual_prompt", custom_prompt)]
                    break
                elif 1 <= choice <= len(options):
                    prompts_to_run = [options[choice - 1]]
                    break
                else:
                    print(f"Invalid choice. Please enter a number between 0 and {len(options)}.")
            except ValueError:
                print("Invalid input. Please enter a valid number.")

    total_runs = len(models_to_run) * len(prompts_to_run)
    eng = start_matlab_engine(show_plots=args.show_plots)
    
    print(f"\n[EVAL] Running {total_runs} test combinations...\n")
    run_idx = 1
    try:
        for prompt_name, prompt_text in prompts_to_run:
            for model_key in models_to_run:
                eng = run_evaluation(
                    model_key, prompt_name, prompt_text, eng, 
                    run_idx=run_idx, total_runs=total_runs, 
                    delay_sec=args.delay, show_plots=args.show_plots
                )
                run_idx += 1
    finally:
        print("\n[MATLAB] Closing engine...")
        eng.quit()

if __name__ == "__main__":
    main()