"""Azure OpenAI embeddings and chat, authenticated with ``DefaultAzureCredential``.

No API key exists anywhere: the Foundry account has local auth disabled, and the token
provider requests the Cognitive Services scope for the managed identity of the workload.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI

from rag.providers import ChatMessage

if TYPE_CHECKING:
    from openai.types.chat import ChatCompletionMessageParam

    from rag.config import Settings

COGNITIVE_SCOPE = "https://cognitiveservices.azure.com/.default"


def make_client(settings: Settings) -> AzureOpenAI:
    if not settings.openai_endpoint:
        msg = "RAG_OPENAI_ENDPOINT is required for the azure backend"
        raise ValueError(msg)
    token_provider = get_bearer_token_provider(DefaultAzureCredential(), COGNITIVE_SCOPE)
    return AzureOpenAI(
        azure_endpoint=settings.openai_endpoint,
        azure_ad_token_provider=token_provider,
        api_version=settings.openai_api_version,
        max_retries=3,
        timeout=30.0,
    )


@dataclass
class AzureOpenAIEmbedder:
    client: AzureOpenAI
    deployment: str
    size: int
    batch_size: int = 16

    @property
    def dimensions(self) -> int:
        return self.size

    def embed(self, texts: Sequence[str]) -> list[tuple[float, ...]]:
        vectors: list[tuple[float, ...]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = list(texts[start : start + self.batch_size])
            response = self.client.embeddings.create(
                model=self.deployment, input=batch, dimensions=self.size
            )
            ordered = sorted(response.data, key=lambda item: item.index)
            vectors.extend(tuple(item.embedding) for item in ordered)
        return vectors


def _to_params(messages: Sequence[ChatMessage]) -> list[ChatCompletionMessageParam]:
    params: list[ChatCompletionMessageParam] = []
    for m in messages:
        if m.role == "system":
            params.append({"role": "system", "content": m.content})
        elif m.role == "assistant":
            params.append({"role": "assistant", "content": m.content})
        else:
            params.append({"role": "user", "content": m.content})
    return params


@dataclass
class AzureOpenAIChat:
    client: AzureOpenAI
    deployment: str
    temperature: float = 0.0
    max_tokens: int = 600

    def complete(self, messages: Sequence[ChatMessage]) -> str:
        response = self.client.chat.completions.create(
            model=self.deployment,
            messages=_to_params(messages),
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        return response.choices[0].message.content or ""

    def stream(self, messages: Sequence[ChatMessage]) -> Iterator[str]:
        response = self.client.chat.completions.create(
            model=self.deployment,
            messages=_to_params(messages),
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            stream=True,
        )
        for event in response:
            if event.choices and event.choices[0].delta.content:
                yield event.choices[0].delta.content
