"""Semantic Scholar API client for fetching reference lists."""

import requests
import time
from typing import List, Optional
from src.utils.logger import get_logger


logger = get_logger(__name__)


class SemanticScholarClient:
    """Client for Semantic Scholar API to fetch paper references."""

    def __init__(self, api_key: Optional[str] = None, delay: float = 3.1):
        """Initialize Semantic Scholar client with optional API key."""
        self.api_base = "https://api.semanticscholar.org/graph/v1/paper"
        self.delay = delay
        self.headers = {}

        if api_key:
            self.headers['x-api-key'] = api_key
            logger.info("Semantic Scholar client initialized (with API key)")
        else:
            logger.info("Semantic Scholar client initialized (no API key)")

    def fetch_references(self, doi: str) -> Optional[List[str]]:
        """Fetch reference DOIs for a paper. Returns list of DOIs or None if not found."""
        url = f"{self.api_base}/DOI:{doi}"
        params = {'fields': 'references,externalIds'}

        try:
            response = requests.get(url, params=params, headers=self.headers, timeout=10)

            if response.status_code == 200:
                data = response.json()
                references = data.get('references', [])

                cited_dois = []
                for ref in references:
                    cited_paper = ref.get('citedPaper', {})
                    external_ids = cited_paper.get('externalIds', {})
                    if 'DOI' in external_ids:
                        cited_dois.append(external_ids['DOI'].lower())

                time.sleep(self.delay)
                return cited_dois if cited_dois else None

            elif response.status_code == 404:
                time.sleep(self.delay)
                return None
            else:
                logger.warning(f"Semantic Scholar returned status {response.status_code} for DOI {doi}")
                time.sleep(self.delay)
                return None

        except requests.exceptions.Timeout:
            logger.error(f"Timeout fetching DOI {doi} from Semantic Scholar")
            time.sleep(self.delay)
            return None
        except Exception as e:
            logger.error(f"Semantic Scholar error for DOI {doi}: {e}")
            time.sleep(self.delay)
            return None
