import os
import re
import sys
import json
from openai import APIConnectionError, APIStatusError, AuthenticationError, OpenAI
from pydantic import ValidationError

from config import MODELS, PROVIDERS, build_system_prompt
from compiler import save_simplus_json, compile_to_simplus_dict
from schema import SimplusGTModelLLM
from logger import log_evaluation_run
from matlab_bridge import run_simplus_headless

def strip_markdown_fences(text: str) -> str:
    text = text.strip()
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    return match.group(1).strip() if match else text

def select_model() -> str:
    model_choices = {str(idx): key for idx, key in enumerate(MODELS.keys(), start=1)}
    while True:
        print("\n    -----------  Available Models  -----------    ")
        for num, key in model_choices.items():
            tier = MODELS[key].get("tier")
            print(f"{num:>2}: {key:<26} [{tier}]")
        user_input = input("\nChoose model (number): ").strip()
        if user_input in model_choices:
            return model_choices[user_input]
        print("Invalid selection. Please enter a valid number.")

def get_user_prompt() -> tuple[str, str]:
    """Returns a tuple of (prompt_name, prompt_text)"""
    with open("prompts.json", "r") as f:
        prompts_db = json.load(f)

    options = []
    print("\n    -----------  Available Prompts  -----------    ")
    print(" 0: [Write a custom prompt]")
    
    idx = 1
    for category, prompts in prompts_db.items():
        print(f"\n--- {category} ---")
        for name, text in prompts.items():
            options.append((name, text))
            print(f"{idx:>2}: {name}")
            idx += 1

    while True:
        user_input = input("\nChoose a prompt (number): ").strip()
        if user_input == "0":
            return ("Custom Prompt", input("\nEnter your custom prompt: ").strip())
        try:
            choice = int(user_input)
            if 1 <= choice <= len(options):
                return options[choice - 1]
        except ValueError:
            pass
        print("Invalid selection. Please enter a valid number.")

def main():
    selected_model_key = select_model()
    model_cfg = MODELS[selected_model_key]
    provider_cfg = PROVIDERS[model_cfg["provider"]]

    target_url = provider_cfg["base_url"]
    target_key = provider_cfg["api_key"]
    target_model_id = model_cfg["id"]

    if not target_key:
        print(f"[ERROR] Environment variable for '{model_cfg['provider']}' is not set.", file=sys.stderr)
        sys.exit(1)

    prompt_name, user_prompt = get_user_prompt()

    client = OpenAI(base_url=target_url, api_key=target_key, timeout=60.0)
    print(f"\n[INFO] Sending request to {selected_model_key} ({target_model_id})...")

    messages = [
        {"role": "system", "content": build_system_prompt()},
        {"role": "user", "content": user_prompt},
    ]

    SIMPLUS_DIR = os.path.abspath("/var/home/burgerking/Documents/MATLAB/Simplus-Grid-Tool-master/")
    max_iterations = 3
    
    iteration_data = []
    api_status = "SUCCESS"
    iterations_needed = 0

    for attempt in range(max_iterations):
        print(f"\n--- Iteration {attempt + 1} of {max_iterations} ---")
        iterations_needed = attempt + 1
        
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

        try:
            response = client.chat.completions.create(
                model=target_model_id,
                messages=messages,
                temperature=0.1,
            )
            it_state["raw_response"] = response.choices[0].message.content
            if not it_state["raw_response"]:
                raise ValueError("Received empty response payload from endpoint.")
                
        except AuthenticationError as e:
            api_status = "AUTH_ERROR"
            it_state["failure_stage"] = "API"
            it_state["error_message"] = str(e)
            iteration_data.append(it_state)
            break
        except APIConnectionError as e:
            api_status = "CONNECTION_ERROR"
            it_state["failure_stage"] = "API"
            it_state["error_message"] = str(e)
            iteration_data.append(it_state)
            break
        except APIStatusError as e:
            # Catches Rate Limits (429), Bad Gateways (502), etc.
            api_status = f"HTTP_{e.status_code}"
            it_state["failure_stage"] = "API"
            it_state["error_message"] = e.message
            iteration_data.append(it_state)
            break
        except Exception as e:
            api_status = "UNKNOWN_API_ERROR"
            it_state["failure_stage"] = "API"
            it_state["error_message"] = str(e)
            iteration_data.append(it_state)
            break

        # Parsing & Validation Pipeline
        try:
            cleaned_json = strip_markdown_fences(it_state["raw_response"])
            import json
            json.loads(cleaned_json)
            it_state["json_syntax_valid"] = True

            validated_model = SimplusGTModelLLM.model_validate_json(cleaned_json)
            it_state["pydantic_valid"] = True

            it_state["compiled_data"] = compile_to_simplus_dict(validated_model)

            user_data_path = os.path.join(SIMPLUS_DIR, "UserData.json")
            save_simplus_json(validated_model, filepath=user_data_path)
            
            m_success, m_out, m_err, m_errmsg = run_simplus_headless(SIMPLUS_DIR)
            it_state["matlab_log"] = m_out + "\n" + m_err
            
            if m_success:
                if "unstable" in m_out.lower():
                    it_state["matlab_status"] = "UNSTABLE"
                    print("[SUCCESS] MATLAB execution completed, but system is UNSTABLE.")
                else:
                    it_state["matlab_status"] = "SOLVED"
                    print("[SUCCESS] MATLAB execution completed cleanly (SOLVED).")
                iteration_data.append(it_state)
                break
            else:
                it_state["matlab_status"] = "SYNTAX_ERROR"
                it_state["failure_stage"] = "MATLAB"
                it_state["error_message"] = m_errmsg
                raise RuntimeError(f"MATLAB Error:\n{m_errmsg}")

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
        print(f"[{it_state['failure_stage']} FAILED] {it_state['error_message'][:200]}...")

        if attempt < max_iterations - 1:
            messages.append({"role": "assistant", "content": it_state["raw_response"]})
            messages.append({
                "role": "user", 
                "content": f"The previous configuration failed at the {it_state['failure_stage']} stage with this error:\n{it_state['error_message']}\nCorrect the JSON structure and regenerate."
            })

    # Log the consolidated results
    log_evaluation_run(
        model_name=selected_model_key,
        provider=model_cfg["provider"],
        tier=model_cfg.get("tier", "unknown"),
        prompt_name=prompt_name,
        prompt=user_prompt,
        api_status=api_status,
        iterations_needed=iterations_needed,
        iteration_data=iteration_data
    )

if __name__ == "__main__":
    main()