#==============================================================================
# NODE: Tracer-04 (Gemini Pivot)
# FILE: config/settings.py
# RESPONSIBILITY: Enforce strict validation of environment variables for the Gemini engine.
# INVARIANT: The application will never start with a missing Gemini API key.
#==============================================================================

import sys
from pydantic_settings import BaseSettings
from pydantic import Field, ValidationError
from rich.console import Console

console = Console()

class Settings(BaseSettings):
    # Enforce the exact variable name required by the Gemini SDK.
    GEMINI_API_KEY: str = Field(..., description="Google AI Studio API key for the LLM Judge.")
    GEMINI_MODEL: str = Field(default="gemini-3.1-flash-lite", description="Model to use for evaluation.")
    LOG_LEVEL: str = Field(default="INFO", description="Logging verbosity.")
    ENVIRONMENT: str = Field(default="development", description="Current deployment environment.")

    class Config:
        env_file = "config/.env"
        env_file_encoding = "utf-8"
        extra = "ignore"

def load_settings() -> Settings:
    try:
        settings = Settings()
        console.print(f"[bold green]Environment loaded successfully.[/bold green] Target: {settings.ENVIRONMENT}")
        return settings
    except ValidationError as e:
        console.print(f"[bold red]FATAL: Configuration Validation Failed.[/bold red]")
        console.print(e)
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]FATAL: Unexpected error loading settings.[/bold red] Error: {str(e)}")
        sys.exit(1)

settings = load_settings()