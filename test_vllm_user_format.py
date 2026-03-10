import sys, os, json, requests
sys.path.insert(0, '.')
from dotenv import load_dotenv; load_dotenv(override=True)

PROJECT = os.getenv('VERTEX_PROJECT_ID')
REGION = os.getenv('VERTEX_REGION')
ENDPOINT = os.getenv('VERTEX_ENDPOINT_ID')

import google.auth
import google.auth.transport.requests

creds, _ = google.auth.default()
auth_req = google.auth.transport.requests.Request()
creds.refresh(auth_req)

url = f'https://{REGION}-aiplatform.googleapis.com/v1beta1/projects/{PROJECT}/locations/{REGION}/endpoints/{ENDPOINT}:rawPredict'
headers = {
    'Authorization': f'Bearer {creds.token}',
    'Content-Type': 'application/json'
}

payload = {
    "instances": [
        {
          "@requestFormat": "chatCompletions",
          "messages": [
              {
                  "role": "system",
                  "content": [{"type": "text", "text": "You are an expert radiologist."}]
              },
              {
                  "role": "user",
                  "content": [
                      {
                          "type": "text",
                          "text": "Describe this X-ray"
                      },
                      {
                          "type": "image_url",
                          "image_url": {"url": "https://upload.wikimedia.org/wikipedia/commons/c/c8/Chest_Xray_PA_3-8-2010.png"}
                      }
                  ]
              }
          ],
          "max_tokens": 200
        }
    ]
}

print('Testing user-provided payload format with @requestFormat...')
try:
    response = requests.post(url, headers=headers, json=payload)
    print(f'Status: {response.status_code}')
    print(response.text[:1000])
except Exception as e:
    print(f'Error: {e}')
