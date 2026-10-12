"""Context-window budgeting independent of document retrieval."""

from __future__ import annotations

from dataclasses import dataclass

from app.config import get_settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


def estimate_tokens(text: str) -> int:
    """Approximate token count when a model tokenizer is unavailable."""
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


def count_tokens(text: str, model: str | None = None) -> int:
    settings = get_settings()
    model_name = model or settings.GEMINI_MODEL
    try:
        import google.generativeai as genai

        genai.configure(api_key=settings.GOOGLE_API_KEY)
        result = genai.GenerativeModel(model_name).count_tokens(text)
        total = getattr(result, "total_tokens", None)
        if isinstance(total, int) and total > 0:
            return total
    except Exception:
        logger.debug("Tokenizer unavailable; using character heuristic")
    return estimate_tokens(text)


@dataclass
class ContextPlan:
    model_context: int
    output_reserve: int
    system_tokens: int
    query_tokens: int
    remaining: int
    retrieval_budget: int
    history_budget: int


class TokenBudgetService:
    def plan(self, system_prompt: str, query: str) -> ContextPlan:
        settings = get_settings()
        model_context = settings.resolved_context_window
        output_reserve = settings.OUTPUT_TOKEN_RESERVE
        system_tokens = count_tokens(system_prompt)
        query_tokens = count_tokens(query)
        remaining = max(0, model_context - output_reserve - system_tokens - query_tokens)
        retrieval_budget = min(settings.RETRIEVAL_TOKEN_BUDGET, max(0, remaining // 2))
        history_budget = min(settings.HISTORY_TOKEN_BUDGET, max(0, remaining - retrieval_budget))
        return ContextPlan(
            model_context=model_context,
            output_reserve=output_reserve,
            system_tokens=system_tokens,
            query_tokens=query_tokens,
            remaining=remaining,
            retrieval_budget=retrieval_budget,
            history_budget=history_budget,
        )

    def fit_texts(self, texts: list[str], budget: int) -> list[str]:
        selected: list[str] = []
        used = 0
        for text in texts:
            cost = count_tokens(text)
            if used + cost > budget:
                leftover = budget - used
                if leftover > 50:
                    approx_chars = leftover * 4
                    selected.append(text[:approx_chars] + " …[truncated]")
                break
            selected.append(text)
            used += cost
        return selected
