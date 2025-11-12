"""PubMed API client with ESearch/EFetch and inline rate limiting."""

import logging
import time
from dataclasses import dataclass
from typing import Optional
import requests


@dataclass
class SearchResult:
    count: int
    webenv: Optional[str] = None
    query_key: Optional[str] = None
    pmids: Optional[list[int]] = None


class PubMedAPIClient:
    """PubMed E-utilities API client with inline rate limiting."""

    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    def __init__(
        self,
        email: str,
        api_key: Optional[str] = None,
        tool: str = "subiculum-lit-analysis",
        rate_limit: int = 3,
        max_retries: int = 3,
        backoff_base: int = 2,
        backoff_max: int = 60
    ):
        self.email = email
        self.api_key = api_key
        self.tool = tool

        # Inline rate limiting
        self.rate_limit = rate_limit
        self.min_interval = 1.0 / rate_limit
        self.last_request_time = 0.0

        self.session = requests.Session()
        self.base_url = self.BASE_URL
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.backoff_max = backoff_max
        self.logger = logging.getLogger(__name__)

        self.session.headers.update({
            "User-Agent": f"{tool}/0.1.0 (Python; mailto:{email})"
        })

    def search(self, query: str, use_history: bool = True, retmax: int = 0) -> SearchResult:
        url = f"{self.base_url}/esearch.fcgi"
        params = self._build_params(
            db="pubmed",
            term=query,
            usehistory="y" if use_history else "n",
            retmode="json",
            retmax=retmax
        )

        self.logger.info(f"Executing ESearch: {query}")
        response = self._retry_request(url, params)
        data = response.json()

        if "esearchresult" not in data:
            raise ValueError(f"Malformed ESearch response: {data}")

        result_data = data["esearchresult"]
        count = int(result_data.get("count", 0))

        self.logger.info(f"ESearch found {count} total results")

        if use_history:
            return SearchResult(
                count=count,
                webenv=result_data.get("webenv"),
                query_key=result_data.get("querykey")
            )
        else:
            pmids = [int(pmid) for pmid in result_data.get("idlist", [])]
            return SearchResult(count=count, pmids=pmids)

    def fetch_batch(self, webenv: str, query_key: str, retstart: int, retmax: int) -> str:
        url = f"{self.base_url}/efetch.fcgi"
        params = self._build_params(
            db="pubmed",
            query_key=query_key,
            WebEnv=webenv,
            retstart=retstart,
            retmax=retmax,
            retmode="xml"
        )

        self.logger.info(f"Fetching batch: start={retstart}, max={retmax}")
        response = self._retry_request(url, params, timeout=120)
        return response.text

    def fetch_by_pmids(self, pmids: list[int]) -> str:
        url = f"{self.base_url}/efetch.fcgi"
        pmid_str = ",".join(str(pmid) for pmid in pmids)
        params = self._build_params(
            db="pubmed",
            id=pmid_str,
            retmode="xml"
        )

        self.logger.info(f"Fetching {len(pmids)} PMIDs directly")
        response = self._retry_request(url, params, timeout=120)
        return response.text

    def _wait_if_needed(self) -> None:
        """Rate limiting: block until min_interval has elapsed."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_request_time = time.time()

    def _build_params(self, **kwargs) -> dict:
        params = {"email": self.email, "tool": self.tool, **kwargs}
        if self.api_key:
            params["api_key"] = self.api_key
        return params

    def _retry_request(self, url: str, params: dict, timeout: int = 60) -> requests.Response:
        """Retry with exponential backoff. Handle 429 (rate limit) and 5xx (server errors)."""
        for attempt in range(self.max_retries):
            try:
                self._wait_if_needed()  # Rate limit before request
                response = self.session.get(url, params=params, timeout=timeout)
                response.raise_for_status()
                return response

            except requests.exceptions.Timeout:
                wait = self._calculate_backoff(attempt)
                self.logger.warning(
                    f"Request timeout (attempt {attempt + 1}/{self.max_retries}). "
                    f"Waiting {wait}s before retry."
                )
                if attempt < self.max_retries - 1:
                    time.sleep(wait)
                else:
                    self.logger.error("Max retries exceeded due to timeouts")
                    raise

            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429:  # Rate limit
                    retry_after = int(e.response.headers.get("Retry-After", 60))
                    self.logger.warning(
                        f"Rate limited by server (HTTP 429). Waiting {retry_after}s."
                    )
                    time.sleep(retry_after)
                    if attempt < self.max_retries - 1:
                        continue
                    else:
                        raise

                elif 500 <= e.response.status_code < 600:  # Server error - retry
                    wait = self._calculate_backoff(attempt)
                    self.logger.warning(f"Server error {e.response.status_code}, waiting {wait}s")
                    if attempt < self.max_retries - 1:
                        time.sleep(wait)
                    else:
                        raise

                else:  # Client error (4xx except 429) - don't retry
                    raise

        raise requests.exceptions.RequestException(f"Max retries ({self.max_retries}) exceeded for {url}")

    def _calculate_backoff(self, attempt: int) -> float:
        """Exponential backoff: min(base^attempt, max)"""
        return min(self.backoff_base ** attempt, self.backoff_max)

    def close(self) -> None:
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __repr__(self) -> str:
        return f"PubMedAPIClient(email={self.email}, rate={self.rate_limit} req/s)"
