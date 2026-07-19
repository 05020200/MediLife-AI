import os
import json
import urllib.request
import urllib.error

def call_gemini_api(prompt):
    """
    Sends a request to the Google Gemini 1.5 Flash API using the configured key.
    Uses urllib to ensure zero third-party dependencies for the REST call.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        # Fallback to manual loading from .env
        try:
            # pyrefly: ignore [missing-import]
            from dotenv import load_dotenv
            load_dotenv()
            api_key = os.getenv("GEMINI_API_KEY")
        except Exception:
            pass
            
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not configured. Please add it to your environment or .env file.")
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ]
    }
    
    req_data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=req_data,
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    
    try:
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            candidates = res_data.get('candidates', [])
            if candidates:
                content = candidates[0].get('content', {})
                parts = content.get('parts', [])
                if parts:
                    return parts[0].get('text', '')
            return "No content generated from Gemini."
    except urllib.error.HTTPError as e:
        error_msg = e.read().decode('utf-8')
        try:
            error_json = json.loads(error_msg)
            message = error_json.get('error', {}).get('message', str(e))
        except Exception:
            message = error_msg
        raise RuntimeError(f"Gemini API Error: {message}")
    except Exception as e:
        raise RuntimeError(f"Failed to connect to Gemini API: {str(e)}")
