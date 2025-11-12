"""Configuration management for loading settings from YAML."""

import getpass
from pathlib import Path
from typing import Any, Optional
import yaml


class ConfigManager:

    def __init__(self, config_path: str = "settings.yaml"):
        self.config_path = Path(config_path)
        self.config = {}
        self.load()
        self.validate()

    def load(self) -> None:
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"Configuration file not found: {self.config_path}\n"
                f"Please copy settings-template.yaml to settings.yaml and configure your values."
            )

        with open(self.config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        if not self.config:
            raise ValueError(f"Configuration file is empty: {self.config_path}")

        # Handle API key input if empty (only in interactive mode)
        api_key = self.get("pubmed.api_key", "")
        if api_key == "":
            try:
                api_key = self.get_api_key()
                if api_key:
                    self.set("pubmed.api_key", api_key)
            except (EOFError, OSError):
                self.set("pubmed.api_key", None)

    def validate(self) -> None:
        required_fields = {
            "pubmed.email": "NCBI requires email for API identification",
            "pubmed.tool": "Tool name for API identification"
        }

        for field, description in required_fields.items():
            value = self.get(field)
            if not value or value == "your.email@example.com":
                raise ValueError(
                    f"Required field '{field}' is missing or invalid.\n"
                    f"Description: {description}\n"
                    f"Please update {self.config_path}"
                )

    def get_api_key(self) -> Optional[str]:
        print("\nNCBI API Key (optional):")
        print("  - Leave empty to use 3 requests/second")
        print("  - Enter key for 10 requests/second")
        api_key = getpass.getpass("API Key (or press Enter to skip): ").strip()
        return api_key if api_key else None

    def get(self, key_path: str, default: Any = None) -> Any:
        keys = key_path.split('.')
        value = self.config

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default

        return value

    def set(self, key_path: str, value: Any) -> None:
        keys = key_path.split('.')
        config = self.config
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]
        config[keys[-1]] = value

    @property
    def pubmed_email(self) -> str:
        return self.get("pubmed.email")

    @property
    def pubmed_api_key(self) -> Optional[str]:
        return self.get("pubmed.api_key")

    @property
    def pubmed_tool(self) -> str:
        return self.get("pubmed.tool", "subiculum-lit-analysis")

    @property
    def rate_limit(self) -> int:
        """Returns 10 req/s if API key provided, else 3 req/s."""
        if self.pubmed_api_key:
            return self.get("pubmed.rate_limit_with_key", 10)
        else:
            return self.get("pubmed.rate_limit_without_key", 3)

    @property
    def search_query(self) -> str:
        return self.get("search.query", "subiculum[Title/Abstract]")

    @property
    def max_retries(self) -> int:
        return self.get("pubmed.max_retries", 3)

    @property
    def retry_backoff_base(self) -> int:
        return self.get("pubmed.retry_backoff_base", 2)

    @property
    def retry_backoff_max(self) -> int:
        return self.get("pubmed.retry_backoff_max", 60)
