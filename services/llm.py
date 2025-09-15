import logging
from typing import List

from config import settings

logger = logging.getLogger(__name__)

MAX_CHARS_PER_CHUNK = 12000  # conservative per-request size bound


def _chunk_text(text: str, max_chars: int = MAX_CHARS_PER_CHUNK) -> List[str]:
    if len(text) <= max_chars:
        return [text]
    chunks: List[str] = []
    current: List[str] = []
    current_len = 0
    for line in text.splitlines(True):  # keep line breaks
        if current_len + len(line) > max_chars and current:
            chunks.append("".join(current))
            current = [line]
            current_len = len(line)
        else:
            current.append(line)
            current_len += len(line)
    if current:
        chunks.append("".join(current))
    return chunks


SYSTEM_PROMPT = (
    "You are a senior code reviewer. Summarize the linked Git diff in clear, concise plain English. "
    "Highlight key changes, new files, deleted files, risky areas, and tests. Keep it 4-8 bullet points max."
)

USER_PROMPT_TEMPLATE = (
    "Summarize this PR diff:\n\n"
    "{diff}\n\n"
    "Constraints: Be concise, actionable, and avoid code excerpts unless critical."
)


class LlmClient:
    def __init__(self) -> None:
        self.api_key = settings.get_groq_api_key()
        if not self.api_key:
            logger.warning("GROQ_API_KEY not configured. Summaries will be truncated diffs.")
        # Prefer MODEL_CHECKPOINT if provided; else use GROQ_MODEL
        self.model = settings.model_checkpoint.strip() or settings.groq_model

    def summarize(self, diff_text: str) -> str:
        chunks = _chunk_text(diff_text)
        if not self.api_key:
            preview = diff_text[:1000]
            return f"LLM unavailable. Diff preview (truncated):\n{preview}"

        if len(chunks) == 1:
            return self._summarize_single(chunks[0])
        partials = [self._summarize_single(c) for c in chunks]
        merged = "\n".join(f"- {p.strip()}" for p in partials if p.strip())
        # Final merge pass
        return self._summarize_single(merged)

    def _summarize_single(self, text: str) -> str:
        try:
            from groq import Groq  # type: ignore
            client = Groq(api_key=self.api_key)
            completion = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": USER_PROMPT_TEMPLATE.format(diff=text)},
                ],
                temperature=0.2,
                max_tokens=500,
            )
            return completion.choices[0].message.content.strip()
        except Exception as e:
            logger.exception("Groq summarization failed: %s", e)
            return text[:800]
