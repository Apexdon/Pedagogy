"""
AI Guidance Engine

Core components for AI-powered user guidance:
- LLM Client: OpenAI GPT-4.1 and Ollama abstraction
- Element Matcher: Match UI elements to instruction targets
- AI Reasoner: LLM-based step generation
- Guidance Generator: Orchestrates RAG + LLM + Matching
- Step Tracker: Session and progress management
"""

from app.ai_engine.llm_client import (
    LLMClient,
    OpenAIClient,
    OllamaClient,
    get_llm_client,
)
from app.ai_engine.matcher import ElementMatcher
from app.ai_engine.reasoner import AIReasoner
from app.ai_engine.guidance_generator import GuidanceGenerator
from app.ai_engine.step_tracker import StepTracker

__all__ = [
    # LLM Clients
    "LLMClient",
    "OpenAIClient",
    "OllamaClient",
    "get_llm_client",
    # Components
    "ElementMatcher",
    "AIReasoner",
    "GuidanceGenerator",
    "StepTracker",
]
