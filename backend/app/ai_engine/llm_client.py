"""
LLM Client Abstraction

Provides unified interface for LLM providers:
- OpenAI GPT-4.1 (primary, cloud-based)
- Ollama (fallback, local/offline)
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import httpx
import json
import logging

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


async def get_llm_client(
    provider: Optional[str] = None,
    fallback: bool = True,
) -> LLMClient:
    """
    Get configured LLM client.

    Args:
        provider: Specific provider to use ("openai" or "ollama")
        fallback: If True and primary fails, try fallback provider

    Returns:
        Configured LLM client instance

    Raises:
        RuntimeError: If no LLM provider is available
    """
    provider = provider or settings.LLM_PROVIDER

    if provider == "openai":
        client = OpenAIClient()
        if await client.health_check():
            logger.info("Using OpenAI GPT-4.1 as LLM provider")
            return client
        elif fallback:
            logger.warning("OpenAI not available, falling back to Ollama")
            fallback_client = OllamaClient()
            if await fallback_client.health_check():
                logger.info("Using Ollama as fallback LLM provider")
                return fallback_client
            raise RuntimeError("No LLM provider available (OpenAI and Ollama both failed)")
        else:
            raise RuntimeError("OpenAI API not available and fallback disabled")

    elif provider == "ollama":
        client = OllamaClient()
        if await client.health_check():
            logger.info("Using Ollama as LLM provider")
            return client
        elif fallback:
            logger.warning("Ollama not available, falling back to OpenAI")
            fallback_client = OpenAIClient()
            if await fallback_client.health_check():
                logger.info("Using OpenAI as fallback LLM provider")
                return fallback_client
            raise RuntimeError("No LLM provider available (Ollama and OpenAI both failed)")
        else:
            raise RuntimeError("Ollama not available and fallback disabled")

    else:
        raise ValueError(f"Unknown LLM provider: {provider}")
