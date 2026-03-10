import sys, os, json, base64
sys.path.insert(0, '.')
from dotenv import load_dotenv; load_dotenv(override=True)
import google.auth
import google.auth.transport.requests

PROJECT = os.getenv('VERTEX_PROJECT_ID')
REGION = os.getenv('VERTEX_REGION')
ENDPOINT = os.getenv('VERTEX_ENDPOINT_ID')
# I will hardcode the dedicated domain from the error message for the test
DEDICATED_DOMAIN = '1797429382285885440.us-central1-501192112782.prediction.vertexai.goog'

creds, _ = google.auth.default()
auth_req = google.auth.transport.requests.Request()
creds.refresh(auth_req)

import openai

with open('uploads/scan_3bc3b8aec94e.jpeg', 'rb') as f:
    b64_image = base64.b64encode(f.read()).decode('utf-8')

# The OpenAI client base URL for Vertex dedicated endpoints requires a specific path format
base_url = f'https://{DEDICATED_DOMAIN}/v1beta1/projects/{PROJECT}/locations/{REGION}/endpoints/{ENDPOINT}'

client = openai.OpenAI(
    base_url=base_url,
    api_key=creds.token,
)

import warnings
warnings.filterwarnings('ignore')

try:
    print('Testing OpenAI Chat Completions on Dedicated Endpoint...')
    response = client.chat.completions.create(
        model='google_medgemma-27b-it',
        messages=[
            {
                'role': 'user',
                'content': [
                    {'type': 'text', 'text': 'Describe this medical image.'},
                    {'type': 'image_url', 'image_url': {'url': f'data:image/jpeg;base64,{b64_image}'}}
                ]
            }
        ],
        max_tokens=200
    )
    print('\nSUCCESS!! Response:')
    print(response.choices[0].message.content)
except Exception as e:
    print(f'OpenAI Error: {e}')
