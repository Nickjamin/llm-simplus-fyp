import re
import sys
from openai import APIConnectionError, APIStatusError, AuthenticationError, OpenAI
from pydantic import ValidationError

from config import MODELS, PROVIDERS, build_system_prompt
from compiler import save_simplus_json
from schema import SimplusGTModelLLM
from logger import log_evaluation_run
from compiler import compile_to_simplus_dict


def strip_markdown_fences(text: str) -> str:
    """Removes ```json ... ``` wrappers if the LLM includes them despite instructions."""
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

    user_prompt = input("\nDescribe the AC power grid to generate: ").strip()
    if not user_prompt:
        user_prompt = (
            "Create a 4-bus AC ring network (lines 1-2, 2-3, 3-1) plus a radial transformer line from 3 to 4 "
            "(turns ratio 0.99). Put synchronous generators on Buses 1 and 2, a GFM inverter on Bus 3, "
            "and a GFL inverter on Bus 4. Include shunt loads on all 4 buses."
        )
        print(f"[INFO] Using default 4-bus test prompt:\n'{user_prompt}'")

    client = OpenAI(base_url=target_url, api_key=target_key, timeout=60.0)
    print(f"\n[INFO] Sending request to {selected_model_key} ({target_model_id})...")

    try:
        response = client.chat.completions.create(
            model=target_model_id,
            messages=[
                {"role": "system", "content": build_system_prompt()},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,  # Low temperature for deterministic structural adherence
        )

        raw_content = response.choices[0].message.content
        if not raw_content:
            print("[WARN] Received empty response payload from endpoint.", file=sys.stderr)
            sys.exit(1)

        json_syntax_valid = False
        pydantic_valid = False
        compiled_dict = None
        failure_stage = "NONE"
        err_msg = ""

        try:
            # 1. Clean response
            cleaned_json = strip_markdown_fences(raw_content)
            
            # 2. Check JSON parse
            import json
            json.loads(cleaned_json)
            json_syntax_valid = True

            # 3. Pydantic validation
            validated_model = SimplusGTModelLLM.model_validate_json(cleaned_json)
            pydantic_valid = True

            # 4. Compile full SimplusGT JSON
            compiled_dict = compile_to_simplus_dict(validated_model)

        except json.JSONDecodeError as e:
            failure_stage = "JSON_DECODE"
            err_msg = str(e)
        except ValidationError as e:
            failure_stage = "PYDANTIC"
            err_msg = str(e)
        except Exception as e:
            failure_stage = "UNKNOWN"
            err_msg = str(e)

        # Log the run regardless of success or failure
        log_evaluation_run(
            model_name=selected_model_key,
            provider=model_cfg["provider"],
            tier=model_cfg.get("tier", "unknown"),
            prompt=user_prompt,
            raw_response=raw_content,
            json_syntax_valid=json_syntax_valid,
            pydantic_valid=pydantic_valid,
            compiled_data=compiled_dict,
            matlab_status="PENDING", # or update after your MATLAB runner script executes
            failure_stage=failure_stage,
            error_message=err_msg
        )

    except ValidationError as e:
        print(f"\n[SCHEMA VALIDATION FAILED] {selected_model_key} produced invalid data:", file=sys.stderr)
        print(e, file=sys.stderr)
        print("\n--- Raw LLM Output ---", file=sys.stderr)
        print(raw_content, file=sys.stderr)
    except AuthenticationError:
        print("[ERROR] 401: Invalid API key or unauthorized.", file=sys.stderr)
    except APIConnectionError as e:
        print(f"[ERROR] Network failure: {e.__cause__}", file=sys.stderr)
    except APIStatusError as e:
        print(f"[ERROR] API returned HTTP {e.status_code}: {e.message}", file=sys.stderr)
    except Exception as e:
        print(f"[ERROR] Unexpected failure: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()