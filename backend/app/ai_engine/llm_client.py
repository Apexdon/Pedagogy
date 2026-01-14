"""
LLM Client Abstraction

Provides unified interface for LLM providers:
- Google Gemini (primary, cloud-based, free tier)
- Ollama (fallback, local/offline)
- OpenAI GPT-4.1 (alternative cloud option)
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import httpx
import json
import logging
import os

from app.config import settings

logger = logging.getLogger(__name__)


class LLMClient(ABC):
    """Abstract base class for LLM clients."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Generate text completion.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            **kwargs: Additional provider-specific parameters

        Returns:
            Generated text response
        """
        pass

    @abstractmethod
    async def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate structured JSON response.

        Args:
            prompt: User prompt (should request JSON output)
            system_prompt: Optional system prompt
            **kwargs: Additional provider-specific parameters

        Returns:
            Parsed JSON response as dictionary
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the LLM service is available."""
        pass


class OpenAIClient(LLMClient):
    """
    OpenAI GPT-4.1 API client.

    Primary LLM provider with native JSON mode support.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ):
        """
        Initialize OpenAI client.

        Args:
            api_key: OpenAI API key (defaults to settings)
            model: Model name (defaults to settings)
            max_tokens: Max response tokens (defaults to settings)
            temperature: Sampling temperature (defaults to settings)
        """
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model = model or settings.OPENAI_MODEL
        self.max_tokens = max_tokens or settings.OPENAI_MAX_TOKENS
        self.temperature = temperature or settings.OPENAI_TEMPERATURE
        self.base_url = "https://api.openai.com/v1"

        if not self.api_key:
            logger.warning("OpenAI API key not configured")

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> str:
        """Generate text completion using OpenAI API."""
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "temperature": kwargs.get("temperature", self.temperature),
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=self._get_headers(),
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        return data["choices"][0]["message"]["content"]

    async def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate structured JSON response using OpenAI's JSON mode.

        GPT-4.1 supports response_format: {"type": "json_object"} for
        guaranteed valid JSON output.
        """
        messages = []

        # System prompt should mention JSON output
        json_system = system_prompt or ""
        if "json" not in json_system.lower():
            json_system += "\n\nYou must respond with valid JSON only."

        messages.append({"role": "system", "content": json_system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "temperature": kwargs.get("temperature", self.temperature),
            "response_format": {"type": "json_object"},
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=self._get_headers(),
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        content = data["choices"][0]["message"]["content"]
        return json.loads(content)

    async def health_check(self) -> bool:
        """Check if OpenAI API is accessible."""
        if not self.api_key:
            return False

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/models",
                    headers=self._get_headers(),
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"OpenAI health check failed: {e}")
            return False


class GeminiClient(LLMClient):
    """
    Google Gemini API client.

    Primary LLM provider with free tier and excellent performance.
    Uses the new google-genai SDK.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ):
        """
        Initialize Gemini client.

        Args:
            api_key: Gemini API key (defaults to settings or env var)
            model: Model name (defaults to settings)
            max_tokens: Max response tokens (defaults to settings)
            temperature: Sampling temperature (defaults to settings)
        """
        self.api_key = api_key or settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY")
        self.model = model or settings.GEMINI_MODEL
        self.max_tokens = max_tokens or settings.GEMINI_MAX_TOKENS
        self.temperature = temperature or settings.GEMINI_TEMPERATURE
        self._client = None

        if not self.api_key:
            logger.warning("Gemini API key not configured. Set GEMINI_API_KEY in .env or environment.")

    def _get_client(self):
        """Lazy initialization of Gemini client."""
        if self._client is None:
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
                logger.info(f"[Gemini] Client initialized with model: {self.model}")
            except ImportError:
                logger.error("google-genai package not installed. Run: pip install google-genai")
                raise
        return self._client

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> str:
        """Generate text completion using Gemini API."""
        logger.info(f"[Gemini] Starting generation with model: {self.model}")
        logger.debug(f"[Gemini] Prompt length: {len(prompt)} chars")

        try:
            from google.genai import types

            client = self._get_client()

            # Build the content with system instruction if provided
            config = types.GenerateContentConfig(
                temperature=kwargs.get("temperature", self.temperature),
                max_output_tokens=kwargs.get("max_tokens", self.max_tokens),
            )

            if system_prompt:
                config.system_instruction = system_prompt
                logger.debug(f"[Gemini] System prompt length: {len(system_prompt)} chars")

            import time
            start_time = time.time()

            # Use async client
            response = await client.aio.models.generate_content(
                model=self.model,
                contents=prompt,
                config=config,
            )

            elapsed = time.time() - start_time
            logger.info(f"[Gemini] Response received in {elapsed:.2f}s")

            result = response.text
            logger.info(f"[Gemini] Response length: {len(result)} chars")
            return result

        except Exception as e:
            logger.error(f"[Gemini] Generation error: {type(e).__name__}: {e}")
            raise

    async def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate structured JSON response using Gemini's JSON mode.

        Gemini supports response_mime_type: "application/json" for
        guaranteed valid JSON output.
        """
        logger.info(f"[Gemini] generate_json called with model: {self.model}")

        try:
            from google.genai import types

            client = self._get_client()

            # Enhance system prompt for JSON
            json_system = system_prompt or ""
            if "json" not in json_system.lower():
                json_system += "\n\nYou must respond with valid JSON only."

            # Configure for JSON output
            config = types.GenerateContentConfig(
                temperature=kwargs.get("temperature", self.temperature),
                max_output_tokens=kwargs.get("max_tokens", self.max_tokens),
                response_mime_type="application/json",
                system_instruction=json_system,
            )

            import time
            start_time = time.time()

            response = await client.aio.models.generate_content(
                model=self.model,
                contents=prompt,
                config=config,
            )

            elapsed = time.time() - start_time
            logger.info(f"[Gemini] JSON response received in {elapsed:.2f}s")

            content = response.text
            logger.debug(f"[Gemini] Raw JSON response length: {len(content)} chars")

            # Parse JSON response
            try:
                return json.loads(content)
            except json.JSONDecodeError as e:
                logger.error(f"[Gemini] Failed to parse JSON: {e}")
                logger.error(f"[Gemini] Raw response: {content[:500]}")
                # Return empty structure on parse failure
                return {
                    "steps": [],
                    "context_summary": "Failed to generate guidance - JSON parse error",
                    "confidence": 0.0,
                    "reasoning": f"JSON parse error: {str(e)}",
                }

        except Exception as e:
            logger.error(f"[Gemini] generate_json error: {type(e).__name__}: {e}")
            raise

    async def health_check(self) -> bool:
        """Check if Gemini API is accessible."""
        if not self.api_key:
            logger.warning("[Gemini] Health check failed: No API key configured")
            return False

        try:
            import asyncio
            client = self._get_client()
            # Simple test generation with timeout to verify API connectivity
            response = await asyncio.wait_for(
                client.aio.models.generate_content(
                    model=self.model,
                    contents="Hi",
                ),
                timeout=10.0  # 10 second timeout for health check
            )
            if response.text:
                logger.info(f"[Gemini] Health check passed. Model: {self.model}")
                return True
            return False
        except asyncio.TimeoutError:
            logger.error("[Gemini] Health check timed out after 10s")
            return False
        except Exception as e:
            logger.error(f"[Gemini] Health check failed: {type(e).__name__}: {e}")
            return False


class OllamaClient(LLMClient):
    """
    Ollama local LLM client.

    Fallback provider for offline use with local models.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        """
        Initialize Ollama client.

        Args:
            base_url: Ollama server URL (defaults to settings)
            model: Model name (defaults to settings)
        """
        self.base_url = base_url or settings.OLLAMA_BASE_URL
        self.model = model or settings.OLLAMA_MODEL

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> str:
        """Generate text completion using Ollama API."""
        logger.info(f"[Ollama] Starting generation with model: {self.model}")
        logger.info(f"[Ollama] Base URL: {self.base_url}")
        logger.debug(f"[Ollama] Prompt length: {len(prompt)} chars")

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }

        if system_prompt:
            payload["system"] = system_prompt
            logger.debug(f"[Ollama] System prompt length: {len(system_prompt)} chars")

        # Add optional parameters
        if "temperature" in kwargs:
            payload["options"] = payload.get("options", {})
            payload["options"]["temperature"] = kwargs["temperature"]

        # Increase timeout for slow local LLM - 10 minutes with extended read timeout
        timeout = httpx.Timeout(600.0, read=600.0)
        logger.info(f"[Ollama] Sending request to {self.base_url}/api/generate (timeout: 600s)")

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                import time
                start_time = time.time()
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                )
                elapsed = time.time() - start_time
                logger.info(f"[Ollama] Response received in {elapsed:.2f}s, status: {response.status_code}")

                response.raise_for_status()
                data = response.json()

            response_text = data["response"]
            logger.info(f"[Ollama] Response length: {len(response_text)} chars")
            logger.debug(f"[Ollama] Response preview: {response_text[:200]}...")
            return response_text

        except httpx.TimeoutException as e:
            logger.error(f"[Ollama] Request timed out after 600s: {e}")
            raise
        except httpx.HTTPStatusError as e:
            logger.error(f"[Ollama] HTTP error {e.response.status_code}: {e.response.text[:500]}")
            raise
        except Exception as e:
            logger.error(f"[Ollama] Unexpected error: {type(e).__name__}: {e}")
            raise

    async def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate structured JSON response using Ollama.

        Note: Ollama doesn't have native JSON mode, so we rely on
        prompting and parsing.
        """
        logger.info(f"[Ollama] generate_json called with model: {self.model}")

        # Enhance system prompt for JSON output
        json_system = system_prompt or ""
        json_system += "\n\nIMPORTANT: You must respond with valid JSON only. No explanations, no markdown code blocks, just raw JSON."

        # Enhance prompt
        json_prompt = f"{prompt}\n\nRespond with valid JSON only:"

        logger.info(f"[Ollama] generate_json: sending request...")

        response_text = await self.generate(
            prompt=json_prompt,
            system_prompt=json_system,
            **kwargs
        )

        logger.debug(f"Ollama raw response length: {len(response_text)}")

        # Clean up response (remove any markdown artifacts)
        cleaned = response_text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        # Also handle case where response starts with extra text before JSON
        json_start = cleaned.find("{")
        if json_start > 0:
            logger.debug(f"Found JSON starting at position {json_start}, trimming prefix")
            cleaned = cleaned[json_start:]

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Ollama JSON response: {e}")
            logger.error(f"Raw response (first 500 chars): {response_text[:500]}")
            # Return empty steps structure instead of error
            # This allows the guidance to still be created (empty) rather than failing
            return {
                "steps": [],
                "context_summary": "Failed to generate guidance - LLM returned invalid JSON",
                "confidence": 0.0,
                "reasoning": f"JSON parse error: {str(e)}",
            }

    async def health_check(self) -> bool:
        """Check if Ollama server is running."""
        logger.info(f"[Ollama] Health check: {self.base_url}/api/tags")
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    models = [m.get("name", "unknown") for m in data.get("models", [])]
                    logger.info(f"[Ollama] Health check passed. Available models: {models}")
                    if self.model not in models and f"{self.model}:latest" not in models:
                        # Check if any model starts with the base name
                        base_model = self.model.split(":")[0]
                        matching = [m for m in models if m.startswith(base_model)]
                        if not matching:
                            logger.warning(f"[Ollama] Configured model '{self.model}' not found in available models: {models}")
                    return True
                else:
                    logger.warning(f"[Ollama] Health check returned status {response.status_code}")
                    return False
        except Exception as e:
            logger.error(f"[Ollama] Health check failed: {type(e).__name__}: {e}")
            return False


# Module-level cache for LLM clients
_llm_client_cache: Dict[str, LLMClient] = {}
_client_initialized: Dict[str, bool] = {}


async def get_llm_client(
    provider: Optional[str] = None,
    fallback: bool = True,
    skip_health_check: bool = False,
) -> LLMClient:
    """
    Get configured LLM client with caching.

    Args:
        provider: Specific provider to use ("gemini", "ollama", or "openai")
        fallback: If True and primary fails, try fallback provider
        skip_health_check: If True, skip health check (faster initialization)

    Returns:
        Configured LLM client instance

    Raises:
        RuntimeError: If no LLM provider is available
    """
    provider = provider or settings.LLM_PROVIDER

    # Return cached client if available and already validated
    if provider in _llm_client_cache and _client_initialized.get(provider, False):
        logger.debug(f"[LLM] Returning cached {provider} client")
        return _llm_client_cache[provider]

    # Define fallback order based on primary provider
    fallback_order = {
        "gemini": ["ollama", "openai"],
        "ollama": ["gemini", "openai"],
        "openai": ["gemini", "ollama"],
    }

    def get_client_by_name(name: str) -> LLMClient:
        """Get client instance by provider name."""
        if name == "gemini":
            return GeminiClient()
        elif name == "ollama":
            return OllamaClient()
        elif name == "openai":
            return OpenAIClient()
        else:
            raise ValueError(f"Unknown provider: {name}")

    async def try_provider(name: str) -> Optional[LLMClient]:
        """Try to initialize and optionally health check a provider."""
        try:
            # Check cache first
            if name in _llm_client_cache:
                client = _llm_client_cache[name]
            else:
                client = get_client_by_name(name)
                _llm_client_cache[name] = client

            # Skip health check if requested (for performance)
            if skip_health_check:
                _client_initialized[name] = True
                return client

            # Only health check if not already validated
            if not _client_initialized.get(name, False):
                if await client.health_check():
                    _client_initialized[name] = True
                    return client
                else:
                    return None
            return client
        except Exception as e:
            logger.warning(f"Provider {name} failed: {e}")
        return None

    # Try primary provider
    if provider not in fallback_order:
        raise ValueError(f"Unknown LLM provider: {provider}")

    client = await try_provider(provider)
    if client:
        logger.info(f"Using {provider.upper()} as LLM provider")
        return client

    # Try fallbacks if enabled
    if fallback:
        for fallback_provider in fallback_order[provider]:
            logger.warning(f"{provider} not available, trying {fallback_provider}...")
            client = await try_provider(fallback_provider)
            if client:
                logger.info(f"Using {fallback_provider.upper()} as fallback LLM provider")
                return client

        raise RuntimeError(
            f"No LLM provider available. Tried: {provider}, {', '.join(fallback_order[provider])}"
        )
    else:
        raise RuntimeError(f"{provider} not available and fallback disabled")
