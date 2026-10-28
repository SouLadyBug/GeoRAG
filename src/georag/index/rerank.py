"""Cross-encoder reranking with Qwen3-Reranker.

Qwen3-Reranker is a causal LM asked to answer "yes" or "no" to whether a document satisfies a
query; the relevance score is P(yes) from the logits of the final position. The same scorer is
reused for the sentence-level support check in Ask and Design modes.
"""

from __future__ import annotations

import math
import re
from typing import Protocol

from georag.index.dense import model_dtype, resolve_device

RERANK_INSTRUCTION = "Given a geospatial research question, judge whether the passage helps answer it"
SUPPORT_INSTRUCTION = "Judge whether the passage provides evidence for the claim made in the query"

_PREFIX = (
    "<|im_start|>system\nJudge whether the Document meets the requirements based on the Query and the "
    'Instruct provided. Note that the answer can only be "yes" or "no".<|im_end|>\n<|im_start|>user\n'
)
_SUFFIX = "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"


class Scorer(Protocol):
    def score(self, query: str, docs: list[str], instruction: str = RERANK_INSTRUCTION) -> list[float]: ...


class QwenReranker:
    def __init__(self, model_name: str, device: str = "auto", max_length: int = 640, batch_size: int = 8):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.torch = torch
        self.device = resolve_device(device)
        self.tokenizer = AutoTokenizer.from_pretrained(model_name, padding_side="left")
        model = AutoModelForCausalLM.from_pretrained(model_name, torch_dtype=model_dtype(self.device))
        self.model = model.to(self.device).eval()  # type: ignore[arg-type]
        self.yes_id = self.tokenizer.convert_tokens_to_ids("yes")
        self.no_id = self.tokenizer.convert_tokens_to_ids("no")
        self.prefix_ids = self.tokenizer.encode(_PREFIX, add_special_tokens=False)
        self.suffix_ids = self.tokenizer.encode(_SUFFIX, add_special_tokens=False)
        self.max_length = max_length
        self.batch_size = batch_size
        self.name = model_name

    def _encode(self, pairs: list[str]):
        body_budget = self.max_length - len(self.prefix_ids) - len(self.suffix_ids)
        enc = self.tokenizer(
            pairs, padding=False, truncation="longest_first", max_length=body_budget, add_special_tokens=False
        )
        enc["input_ids"] = [self.prefix_ids + ids + self.suffix_ids for ids in enc["input_ids"]]
        enc.pop("attention_mask", None)
        batch = self.tokenizer.pad(enc, padding=True, return_tensors="pt")
        return {k: v.to(self.device) for k, v in batch.items()}

    def score(self, query: str, docs: list[str], instruction: str = RERANK_INSTRUCTION) -> list[float]:
        pairs = [f"<Instruct>: {instruction}\n<Query>: {query}\n<Document>: {d}" for d in docs]
        out: list[float] = []
        with self.torch.inference_mode():
            for i in range(0, len(pairs), self.batch_size):
                batch = self._encode(pairs[i : i + self.batch_size])
                logits = self.model(**batch).logits[:, -1, :]
                two = self.torch.stack([logits[:, self.no_id], logits[:, self.yes_id]], dim=1).float()
                out.extend(self.torch.softmax(two, dim=1)[:, 1].tolist())
        return out


class LexicalScorer:
    """Token-overlap scorer used in tests and when the reranker model is not available."""

    name = "lexical"

    @staticmethod
    def _toks(text: str) -> set[str]:
        stop = {
            "the",
            "a",
            "an",
            "of",
            "and",
            "or",
            "in",
            "on",
            "for",
            "to",
            "is",
            "are",
            "with",
            "by",
            "as",
            "what",
            "which",
            "how",
            "why",
            "does",
            "do",
        }
        return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in stop and len(t) > 1}

    def score(self, query: str, docs: list[str], instruction: str = RERANK_INSTRUCTION) -> list[float]:
        q = self._toks(query)
        scores = []
        for d in docs:
            dt = self._toks(d)
            overlap = len(q & dt) / max(1, len(q))
            scores.append(1 / (1 + math.exp(-8 * (overlap - 0.35))))
        return scores
