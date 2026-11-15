from __future__ import annotations
import copy
import sys
import time
from collections import OrderedDict
from pathlib import Path

M5_RAG = Path.home() / "gigavolt-milestone5" / "rag"
if str(M5_RAG) not in sys.path:
    sys.path.insert(0, str(M5_RAG))
from rag_pipeline import GigavoltRAG

class CachedGigavoltRAG(GigavoltRAG):
    def __init__(self, max_entries=100):
        super().__init__()
        self.max_entries = max_entries
        self._cache = OrderedDict()

    def answer(self, question):
        key = question.strip()
        if key in self._cache:
            start = time.perf_counter()
            cached = copy.deepcopy(self._cache[key])
            self._cache.move_to_end(key)
            cached["cache_hit"] = True
            cached["retrieval_total_ms"] = 0.0
            cached["llm_ms"] = 0.0
            cached["retrieval_timings"] = {}
            cached["total_ms"] = round((time.perf_counter() - start) * 1000, 4)
            return cached
        result = super().answer(question)
        result["cache_hit"] = False
        self._cache[key] = copy.deepcopy(result)
        while len(self._cache) > self.max_entries:
            self._cache.popitem(last=False)
        return result
