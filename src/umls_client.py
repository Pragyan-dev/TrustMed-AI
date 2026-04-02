import requests
from functools import lru_cache
from typing import Optional, Tuple, List
import os
from dotenv import load_dotenv
from src.ssl_bootstrap import configure_ssl_certificates, get_ssl_cert_path

load_dotenv()
configure_ssl_certificates()

class UMLSClient:
    """
    Client for interacting with the UMLS Terminology Services (UTS) REST API.
    """
    
    BASE_URL = "https://uts-ws.nlm.nih.gov/rest"

    def __init__(self, api_key: Optional[str] = None, version: str = 'current'):
        self.api_key = api_key or os.getenv("UMLS_API_KEY")
        if not self.api_key:
            raise ValueError("UMLS API key is required. Provide it in __init__ or set UMLS_API_KEY in .env")
        self.version = version

    @lru_cache(maxsize=128)
    def get_cui(self, term: str) -> Optional[Tuple[str, str]]:
        """
        Search for a term and return its CUI and name.
        Uses SNOMEDCT_US as the vocabulary.
        """
        endpoint = f"{self.BASE_URL}/search/{self.version}"
        params = {
            'apiKey': self.api_key,
            'string': term,
            'sabs': 'SNOMEDCT_US',
            'returnIdType': 'concept'
        }
        
        try:
            response = requests.get(endpoint, params=params, verify=get_ssl_cert_path() or True)
            response.raise_for_status()
            data = response.json()
            
            results = data.get('result', {}).get('results', [])
            if results:
                first_result = results[0]
                return first_result.get('ui'), first_result.get('name')
        except Exception as e:
            print(f"Error fetching CUI for '{term}': {e}")
            
        return None

    @lru_cache(maxsize=128)
    def get_definitions(self, cui: str) -> List[str]:
        """
        Get definitions for a given CUI.
        """
        endpoint = f"{self.BASE_URL}/content/{self.version}/CUI/{cui}/definitions"
        params = {
            'apiKey': self.api_key
        }
        
        try:
            response = requests.get(endpoint, params=params, verify=get_ssl_cert_path() or True)
            response.raise_for_status()
            data = response.json()
            
            results = data.get('result', [])
            return [defn.get('value') for defn in results if defn.get('value')]
        except Exception as e:
            print(f"Error fetching definitions for CUI '{cui}': {e}")
            
        return []

if __name__ == "__main__":
    # Test script
    client = UMLSClient()
    term = "Diabetes"
    print(f"Searching for term: {term}")
    result = client.get_cui(term)
    if result:
        cui, name = result
        print(f"Found: CUI={cui}, Name={name}")
        definitions = client.get_definitions(cui)
        print(f"Definitions for {cui}:")
        for i, d in enumerate(definitions, 1):
            print(f"{i}. {d[:100]}...")
    else:
        print("No results found.")
