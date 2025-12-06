"""
Secure credential management for API access.
Uses getpass to avoid printing sensitive data to stdout.
Supports environment variables for non-interactive use.
"""

import getpass
import os
from typing import Optional, Tuple, Dict


def get_api_credentials(
    service_name: str,
    email_required: bool = True,
    env_email_var: Optional[str] = None,
    env_key_var: Optional[str] = None
) -> Tuple[Optional[str], Optional[str]]:
    """
    Securely prompt for API credentials without echoing to terminal.
    Checks environment variables first for non-interactive use.

    Args:
        service_name: Display name for the service
        email_required: Whether email is mandatory
        env_email_var: Environment variable name for email
        env_key_var: Environment variable name for API key

    Returns:
        Tuple of (email, api_key) where api_key may be None
    """
    email = os.environ.get(env_email_var) if env_email_var else None
    api_key = os.environ.get(env_key_var) if env_key_var else None

    if email:
        return email, api_key

    print(f"\n=== {service_name} API Credentials ===")

    email = None
    if email_required:
        email = input("Email: ").strip()
        if not email:
            raise ValueError(f"Email is required for {service_name}")

    api_key = getpass.getpass("API Key (press Enter to skip): ").strip()

    return email, api_key if api_key else None


def get_all_enrichment_credentials(require_api_keys: bool = False) -> Dict[str, Dict[str, Optional[str]]]:
    """
    Get credentials for all enrichment APIs (CrossRef, Semantic Scholar).

    Checks environment variables first:
    - CROSSREF_EMAIL, CROSSREF_API_KEY
    - SEMANTIC_SCHOLAR_API_KEY

    Args:
        require_api_keys: If True, raises error if API key not provided

    Returns:
        Dict with credentials for each service
    """
    credentials = {}

    if not os.environ.get('CROSSREF_EMAIL'):
        print("\n" + "="*60)
        print("ENRICHMENT API CREDENTIALS")
        print("="*60)

    email, key = get_api_credentials(
        "CrossRef",
        email_required=True,
        env_email_var='CROSSREF_EMAIL',
        env_key_var='CROSSREF_API_KEY'
    )
    credentials['crossref'] = {'email': email, 'api_key': key}

    email, key = get_api_credentials(
        "Semantic Scholar",
        email_required=False,
        env_email_var='SEMANTIC_SCHOLAR_EMAIL',
        env_key_var='SEMANTIC_SCHOLAR_API_KEY'
    )
    credentials['semantic_scholar'] = {'email': email, 'api_key': key}

    if require_api_keys:
        for service, creds in credentials.items():
            if not creds['api_key']:
                raise ValueError(
                    f"API key required for {service} (use --test flag to skip)"
                )

    return credentials
