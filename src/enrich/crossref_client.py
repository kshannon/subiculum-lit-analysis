"""CrossRef API client for fetching reference lists."""

import requests
import time
from typing import List, Optional
from src.utils.logger import get_logger


logger = get_logger(__name__)


class CrossRefClient:
    """Client for CrossRef API to fetch paper references."""

    def __init__(self, email: str, delay: float = 0.5):
        """Initialize CrossRef client with email for polite pool."""
        self.api_base = "https://api.crossref.org/works"
        self.delay = delay
        self.headers = {
            'User-Agent': f'SubiculumLitAnalysis/1.0 (mailto:{email})'
        }
        logger.info(f"CrossRef client initialized (email: {email}, delay: {delay}s)")

    def fetch_references(self, doi: str) -> Optional[List[str]]:
        """Fetch reference DOIs for a paper. Returns list of DOIs or None if not found."""
        url = f"{self.api_base}/{doi}"

        try:
            response = requests.get(url, headers=self.headers, timeout=10)

            if response.status_code == 200:
                data = response.json()['message']
                references = data.get('reference', [])

                cited_dois = []
                for ref in references:
                    if 'DOI' in ref:
                        cited_dois.append(ref['DOI'].lower())

                time.sleep(self.delay)
                return cited_dois if cited_dois else None

            elif response.status_code == 404:
                time.sleep(self.delay)
                return None
            else:
                logger.warning(f"CrossRef returned status {response.status_code} for DOI {doi}")
                time.sleep(self.delay)
                return None

        except requests.exceptions.Timeout:
            logger.error(f"Timeout fetching DOI {doi} from CrossRef")
            time.sleep(self.delay)
            return None
        except Exception as e:
            logger.error(f"CrossRef error for DOI {doi}: {e}")
            time.sleep(self.delay)
            return None
