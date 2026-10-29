"""
Near-Duplicate Discovery Module
Implements MinHash with LSH for efficient near-duplicate HTML/text detection.
"""

from typing import Dict, List, Set, Tuple, Optional
import hashlib
from datasketch import MinHashLSH, MinHash


class NearDuplicateDetector:
    """
    Detects near-duplicate HTML pages or text using MinHash and LSH.
    """

    def __init__(
        self,
        num_perm: int = 128,
        threshold: float = 0.7,
    ):
        self.num_perm = num_perm
        self.threshold = threshold
        self.lsh = MinHashLSH(threshold=threshold, num_perm=num_perm, weights=(0.5, 0.5))
        self.minhashes: Dict[str, MinHash] = {}
        self.html_texts: Dict[str, str] = {}
        self.processed_count = 0

    def _normalize_html(self, html: str) -> str:
        import re
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)
        html = re.sub(r'<[^>]+>', ' ', html)
        html = re.sub(r'\s+', ' ', html)
        return html.strip().lower()

    def _tokenize(self, text: str) -> List[str]:
        words = text.split()
        k = 3 if len(words) > 100 else 5
        shingles = []
        for i in range(len(words) - k + 1):
            shingles.append(' '.join(words[i:i+k]))
        return shingles

    def add_html(self, obs_id: str, html: str) -> None:
        normalized = self._normalize_html(html)
        shingles = self._tokenize(normalized)
        if len(shingles) == 0:
            return
        minhash = MinHash(num_perm=self.num_perm)
        for shingle in shingles:
            minhash.update(shingle.encode('utf-8'))
        self.minhashes[obs_id] = minhash
        self.html_texts[obs_id] = normalized
        self.lsh.insert(obs_id, minhash)
        self.processed_count += 1

    def query_duplicates(self, obs_id: str) -> List[Tuple[str, float]]:
        if obs_id not in self.minhashes:
            return []
        minhash = self.minhashes[obs_id]
        result = self.lsh.query(minhash)
        duplicates = []
        for candidate_id in result:
            if candidate_id == obs_id:
                continue
            jaccard = minhash.jaccard(self.minhashes[candidate_id])
            if jaccard >= self.threshold:
                duplicates.append((candidate_id, jaccard))
        return sorted(duplicates, key=lambda x: x[1], reverse=True)

    def get_statistics(self) -> Dict:
        return {"processed_documents": self.processed_count, "num_permutations": self.num_perm, "threshold": self.threshold}
