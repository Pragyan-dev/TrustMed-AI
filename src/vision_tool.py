"""
Vision Tool for Medical Image Analysis

Uses Llama 3.2 Vision via OpenRouter API to analyze medical images
(X-rays, MRIs, skin photos) and identify abnormalities.

Anti-Hallucination Measures:
- temperature=0.1 for near-deterministic output
- Structured JSON output schema forcing confidence separation
- Reduced max_tokens to prevent verbose confabulation
- Post-processing validation of output structure
"""

import os
import base64
import requests
import json
import importlib.util
from langchain_core.tools import tool
from dotenv import load_dotenv
from src.ssl_bootstrap import configure_ssl_certificates, get_ssl_cert_path
from src.runtime_config import VISION_PROVIDER, VISION_MAX_TOKENS, VERTEX_VISION_MAX_TOKENS

load_dotenv()
configure_ssl_certificates()

# =============================================================================
# Vertex AI MedGemma 27B Integration
# =============================================================================

VERTEX_PROJECT_ID = os.getenv('VERTEX_PROJECT_ID', '')
VERTEX_ENDPOINT_ID = os.getenv('VERTEX_ENDPOINT_ID', '')
VERTEX_REGION = os.getenv('VERTEX_REGION', 'us-central1')
VERTEX_SA_JSON = os.getenv('VERTEX_SERVICE_ACCOUNT_JSON', '')  # optional
VERTEX_DEDICATED_DOMAIN = os.getenv('VERTEX_DEDICATED_DOMAIN', '')  # e.g. 12345.us-central1-123456.prediction.vertexai.goog


def call_medgemma_vertex(image_path: str, prompt: str) -> str:
    """
    Call the MedGemma 27B model deployed on Vertex AI Model Garden (vLLM)
    using the OpenAI-compatible chat completions API via the dedicated domain.
    """
    if not VERTEX_DEDICATED_DOMAIN:
        raise ValueError(
            "VERTEX_DEDICATED_DOMAIN must be set in .env "
            "(e.g. 12345.us-central1-123456.prediction.vertexai.goog)"
        )
    if not VERTEX_PROJECT_ID or not VERTEX_ENDPOINT_ID:
        raise ValueError("VERTEX_PROJECT_ID and VERTEX_ENDPOINT_ID must be set in .env")

    import google.auth
    import google.auth.transport.requests as google_requests

    # Authenticate
    if VERTEX_SA_JSON and os.path.exists(VERTEX_SA_JSON):
        from google.oauth2 import service_account
        credentials = service_account.Credentials.from_service_account_file(
            VERTEX_SA_JSON, scopes=['https://www.googleapis.com/auth/cloud-platform']
        )
    else:
        credentials, _ = google.auth.default(
            scopes=['https://www.googleapis.com/auth/cloud-platform']
        )

    auth_req = google_requests.Request()
    credentials.refresh(auth_req)

    # Encode image to base64 data URI
    with open(image_path, 'rb') as f:
        b64_data = base64.b64encode(f.read()).decode('utf-8')
    ext = os.path.splitext(image_path)[1].lower()
    mime_type = 'image/jpeg' if ext in ['.jpg', '.jpeg'] else 'image/png'
    data_uri = f"data:{mime_type};base64,{b64_data}"

    # Build OpenAI-compatible chat completions request via dedicated endpoint
    base_url = (
        f"https://{VERTEX_DEDICATED_DOMAIN}"
        f"/v1beta1/projects/{VERTEX_PROJECT_ID}"
        f"/locations/{VERTEX_REGION}"
        f"/endpoints/{VERTEX_ENDPOINT_ID}"
    )

    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {credentials.token}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "google_medgemma-27b-it",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_uri}},
                ],
            }
        ],
        "temperature": 0.1,
        "max_tokens": VERTEX_VISION_MAX_TOKENS,
    }

    resp = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=120,
        verify=get_ssl_cert_path() or True,
    )
    if resp.status_code != 200:
        raise ValueError(
            f"MedGemma endpoint returned {resp.status_code}: {resp.text[:500]}"
        )

    data = resp.json()
    content = (
        data.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
    )
    if not content:
        raise ValueError(f"MedGemma returned empty content. Response: {json.dumps(data)[:500]}")

    return content

# =============================================================================
# Anti-Hallucination: Structured Vision Prompt
# =============================================================================

VISION_SYSTEM_PROMPT = (
    "You are a radiologist assistant analyzing a medical image. "
    "You MUST respond in EXACTLY this JSON format and nothing else:\n\n"
    "{\n"
    '  "modality": "<X-Ray|CT|MRI|Ultrasound|Skin Photo|Pathology Slide|Unknown>",\n'
    '  "body_region": "<anatomical region visible>",\n'
    '  "high_confidence_findings": [\n'
    '    {"finding": "<description>", "confidence": "HIGH"}\n'
    "  ],\n"
    '  "uncertain_findings": [\n'
    '    {"finding": "<description>", "confidence": "LOW"}\n'
    "  ],\n"
    '  "cannot_assess": ["<list what cannot be determined from this image>"],\n'
    '  "overall_impression": "<1-2 sentence conservative summary>"\n'
    "}\n\n"
    "STRICT RULES:\n"
    "1. Only put findings you can CLEARLY see in high_confidence_findings.\n"
    "2. Anything uncertain goes in uncertain_findings with LOW confidence.\n"
    "3. If you cannot determine something, put it in cannot_assess.\n"
    "4. Do NOT invent anatomy or pathology not visible in the image.\n"
    "5. Be CONSERVATIVE. When in doubt, classify as uncertain or cannot_assess.\n"
    "6. Respond ONLY with valid JSON, no markdown, no extra text."
)

# =============================================================================
# Configuration
# =============================================================================

OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
OPENROUTER_URL = 'https://openrouter.ai/api/v1/chat/completions'

# Try multiple vision models in order of preference
VISION_MODELS = [
    'google/gemini-3-flash-preview',# Primary
    'google/gemini-3.1-pro-preview',           
    'google/gemini-2.0-flash-exp:free',
    'meta-llama/llama-3.2-11b-vision-instruct',
    'meta-llama/llama-3.2-90b-vision-instruct:free', 
    'qwen/qwen-2-vl-7b-instruct:free',
]
MODEL_ID = VISION_MODELS[0]  # Primary model

# User-overridable preferred model (set by the brain before calling)
_preferred_vision_model = None


def set_preferred_vision_model(model_id: str = None):
    """Set the preferred vision model. Pass None to reset to default."""
    global _preferred_vision_model
    _preferred_vision_model = model_id


def get_vision_models_list() -> list:
    """Return the list of available vision models for UI display."""
    return list(VISION_MODELS)


def _vertex_vision_available() -> bool:
    """Return True only when Vertex was explicitly selected and deps/config exist."""
    if VISION_PROVIDER != "vertex":
        return False
    if not (VERTEX_PROJECT_ID and VERTEX_ENDPOINT_ID and VERTEX_DEDICATED_DOMAIN):
        return False
    try:
        return importlib.util.find_spec("google.auth") is not None
    except ModuleNotFoundError:
        return False


# =============================================================================
# Helper Functions
# =============================================================================

def encode_image(image_path: str) -> str:
    """
    Read an image file and encode it to base64.
    
    Args:
        image_path: Path to the image file
        
    Returns:
        Base64 encoded string of the image
    """
    with open(image_path, 'rb') as f:
        return base64.b64encode(f.read()).decode('utf-8')


# =============================================================================
# Output Validation & Formatting
# =============================================================================

def _validate_and_format_vision_output(raw_output: str, model_id: str) -> str:
    """
    Validate vision model output and format into a structured report.

    Attempts to parse as JSON (structured output). Falls back to raw text
    with a warning flag if the model didn't follow the JSON schema.

    Args:
        raw_output: Raw text from the vision model
        model_id: Which model produced the output

    Returns:
        Formatted analysis report with confidence annotations
    """
    model_name = model_id.split('/')[-1]
    header = f"🔬 Medical Image Analysis (via {model_name})\n{'=' * 40}\n"

    # Try to parse as JSON
    try:
        # Handle markdown-wrapped JSON (```json ... ```)
        cleaned = raw_output.strip()
        if cleaned.startswith('```'):
            # Strip opening fence: ```json or ```
            # Handle both "```json\n{" and "```json{" (no newline)
            import re
            cleaned = re.sub(r'^```\w*\n?', '', cleaned)
            if '```' in cleaned:
                cleaned = cleaned[:cleaned.rfind('```')]

        data = json.loads(cleaned)

        # Successfully parsed structured output
        report = [header]
        report.append(f"Modality & Region: {data.get('modality', 'Unknown')} — {data.get('body_region', 'Unknown')}")
        report.append("")

        # High confidence findings
        high = data.get('high_confidence_findings', [])
        if high:
            report.append("HIGH-CONFIDENCE Findings:")
            for f in high:
                finding = f.get('finding', '') if isinstance(f, dict) else str(f)
                report.append(f"  [HIGH] {finding}")
        else:
            report.append("HIGH-CONFIDENCE Findings: None identified")

        report.append("")

        # Uncertain findings
        uncertain = data.get('uncertain_findings', [])
        if uncertain:
            report.append("UNCERTAIN Findings (require verification):")
            for f in uncertain:
                finding = f.get('finding', '') if isinstance(f, dict) else str(f)
                report.append(f"  [LOW] {finding}")

        # Cannot assess
        cannot = data.get('cannot_assess', [])
        if cannot:
            report.append("")
            report.append(f"Cannot Assess: {', '.join(cannot)}")

        # Overall impression
        impression = data.get('overall_impression', '')
        if impression:
            report.append("")
            report.append(f"Overall Impression: {impression}")

        report.append("")
        report.append("[STRUCTURED OUTPUT — confidence levels verified]")

        return "\n".join(report)

    except (json.JSONDecodeError, KeyError):
        # Model didn't return valid JSON — use raw output but flag it
        return (
            f"{header}\n"
            f"[WARNING: Unstructured output — confidence levels NOT verified]\n\n"
            f"{raw_output}\n\n"
            f"[UNSTRUCTURED — treat all findings as LOW confidence]"
        )


# =============================================================================
# Vision Tool
# =============================================================================

@tool
def analyze_medical_image(image_path: str) -> str:
    """
    Analyze a medical image using Llama 3.2 Vision.
    
    Identifies the modality (X-Ray, MRI, CT, Skin Photo) and describes
    any visible abnormalities or potential diagnoses.
    
    Args:
        image_path: Path to the medical image file (jpg, png)
        
    Returns:
        Analysis report with modality identification and findings
    """
    # Debug: Show where we're looking for the file
    print(f"👁️ Vision Tool looking for: {os.path.abspath(image_path)}")
    
    # Check if file exists
    if not os.path.exists(image_path):
        return f"Error: The image file was not found at {os.path.abspath(image_path)}"
    
    try:
        # Encode image to base64
        base64_image = encode_image(image_path)
        
        # Determine image type from extension
        ext = os.path.splitext(image_path)[1].lower()
        mime_type = 'image/jpeg' if ext in ['.jpg', '.jpeg'] else 'image/png'
        
        # Set up headers
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://trustmed-ai.local",
            "X-Title": "TrustMed AI Vision"
        }
        
        # Try MedGemma on Vertex AI only when explicitly configured.
        if _vertex_vision_available():
            try:
                print("  🧬 Trying MedGemma 27B (Vertex AI)...")
                raw = call_medgemma_vertex(image_path, VISION_SYSTEM_PROMPT)
                if raw:
                    print(f"  ✅ MedGemma 27B (Vertex AI) succeeded. Raw Output:\n{'-'*40}\n{raw}\n{'-'*40}")
                    return _validate_and_format_vision_output(raw, "medgemma-27b-vertex")
            except Exception as ve:
                print(f"  ⚠️ MedGemma Vertex failed ({ve}), falling back to OpenRouter...")

        # Build model order: preferred model first (if set), then remaining fallbacks
        if _preferred_vision_model:
            models_to_try = [_preferred_vision_model] + [m for m in VISION_MODELS if m != _preferred_vision_model]
        else:
            models_to_try = VISION_MODELS

        # Try each model until one works
        last_error = None
        for model_id in models_to_try:
            print(f"  🔄 Trying model: {model_id}")
            
            # Construct the API payload with anti-hallucination settings
            payload = {
                "model": model_id,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": VISION_SYSTEM_PROMPT
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                "temperature": 0.1,   # Near-deterministic: reduces confabulation
                "max_tokens": VISION_MAX_TOKENS,
            }
            
            try:
                # Make API request
                response = requests.post(
                    OPENROUTER_URL,
                    headers=headers,
                    json=payload,
                    timeout=60,
                    verify=get_ssl_cert_path() or True,
                )
                
                if response.status_code == 404:
                    print(f"  ⚠️ Model {model_id} not found, trying next...")
                    last_error = f"Model {model_id} not available"
                    continue
                    
                response.raise_for_status()
                
                # Parse response
                result = response.json()
                analysis = result.get('choices', [{}])[0].get('message', {}).get('content', '')

                if analysis:
                    print(f"  ✅ Success with model: {model_id}")
                    # Validate and format structured output
                    formatted = _validate_and_format_vision_output(analysis, model_id)
                    return formatted
                    
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 404:
                    last_error = f"Model {model_id} not found"
                    continue
                raise
        
        # All models failed
        return f"Error: All vision models failed. Last error: {last_error}"
        
    except requests.exceptions.RequestException as e:
        return f"Error: API request failed - {str(e)}"
    except json.JSONDecodeError as e:
        return f"Error: Failed to parse API response - {str(e)}"
    except Exception as e:
        return f"Error: Unexpected error during analysis - {str(e)}"


# =============================================================================
# Test Block
# =============================================================================

if __name__ == "__main__":
    test_image = "test_image.jpg"
    
    if os.path.exists(test_image):
        print(f"Analyzing {test_image}...")
        result = analyze_medical_image.invoke(test_image)
        print(result)
    else:
        print(f"Test image not found: {test_image}")
        print("To test, place a medical image named 'test_image.jpg' in the project root.")
        print("\nTool registered successfully: analyze_medical_image")
