import logging
import os
from typing import List

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

MAX_CHARS_PER_CHUNK = 12000


def _chunk_text(text: str, max_chars: int = MAX_CHARS_PER_CHUNK) -> List[str]:
    print(f"Chunking text with max_chars={max_chars}")  # Debugging print
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
    print(f"Generated {len(chunks)} chunks")  # Debugging print
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
        print("Initializing LlmClient")  # Debugging print
        self.api_key = os.getenv("GROQ_API_KEY")
        self.model = "openai/gpt-oss-120b"

        from openai import OpenAI
        # Use OpenAI client but point to Groq
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://api.groq.com/openai/v1",
        )
        print("OpenAI client initialized successfully")  # Debugging print

    def summarize(self, diff_text: str) -> str:
        print("Starting summarization")  # Debugging print
        chunks = _chunk_text(diff_text)

        if len(chunks) == 1:
            print("Single chunk detected. Summarizing directly.")  # Debugging print
            return self._summarize_single(chunks[0])
        print(f"Multiple chunks detected: {len(chunks)}. Summarizing each chunk.")  # Debugging print
        partials = [self._summarize_single(c) for c in chunks]
        merged = "\n".join(f"- {p.strip()}" for p in partials if p.strip())
        print("Merging partial summaries")  # Debugging print
        # Final merge pass
        return self._summarize_single(merged)

    def _summarize_single(self, text: str) -> str:
        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": USER_PROMPT_TEMPLATE.format(diff=text)},
                ],
                temperature=0.3,
            )
            print("Summarization successful")
            return completion.choices[0].message.content.strip()
        except Exception as e:
            print(f"Groq summarization failed: {e}")
            return text[:800]
