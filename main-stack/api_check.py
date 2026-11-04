import time
from openai import OpenAI
from config import MODELS, PROVIDERS

def test_all_apis():
    print("Starting API validation check...\n")
    
    results = {"success": [], "failed": []}

    for model_key, model_cfg in MODELS.items():
        provider_name = model_cfg["provider"]
        provider_cfg = PROVIDERS[provider_name]
        
        target_url = provider_cfg["base_url"]
        target_key = provider_cfg["api_key"]
        target_model_id = model_cfg["id"]
        
        print(f"Testing {model_key:<25} via {provider_name}...")
        
        if not target_key:
            print(f"  [X] Failed: Missing API key for provider '{provider_name}'\n")
            results["failed"].append(f"{model_key} (Missing Key)")
            continue
            
        client = OpenAI(base_url=target_url, api_key=target_key, timeout=15.0)
        
        try:
            # Minimal token request to verify the endpoint is active and the model ID is correct
            response = client.chat.completions.create(
                model=target_model_id,
                messages=[{"role": "user", "content": "Ping. Reply 'pong'."}],
                max_tokens=5,
                temperature=0.1
            )
            
            if response.choices:
                print(f"  [✓] Success\n")
                results["success"].append(model_key)
            else:
                print(f"  [X] Failed: Empty response\n")
                results["failed"].append(f"{model_key} (Empty Response)")
                
        except Exception as e:
            print(f"  [X] Failed: {type(e).__name__} - {str(e)}\n")
            results["failed"].append(f"{model_key} ({type(e).__name__})")
            
        # 1.5s delay to prevent hitting free-tier RPM limits just from running the check
        time.sleep(1.5)

    print("-" * 50)
    print("API Validation Summary:")
    print(f"Successful endpoints: {len(results['success'])}")
    print(f"Failed endpoints:     {len(results['failed'])}")
    
    if results["failed"]:
        print("\nReview these failures before starting the batch:")
        for m in results["failed"]:
            print(f" - {m}")
    else:
        print("\nAll systems go. You are ready to run main.py.")

if __name__ == "__main__":
    test_all_apis()