"""
MIND-FLOW Phase 3 Milestone 3: On-Device Semantic Task Classifier
Module: backend/task_classifier.py

3-Tier Hybrid Classification Architecture:
- Tier 1: O(1) LRU Hash Map for exact (process_name, title) lookup (<0.001ms).
- Tier 2: Safe Regex (_safe_regex_cache) + N-Gram TF-IDF Cosine Similarity for keyword matching (<0.1ms).
- Tier 3: Async background worker pool for ambiguous window titles to enrich Tier 1/2 caches without blocking hot loop.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
"""

import os
import sys
import re
import math
import queue
import threading
import logging
import concurrent.futures
from collections import OrderedDict, Counter
from typing import Dict, Any, List, Tuple, Set, Optional

logger = logging.getLogger("task_classifier")

CATEGORY_WORK = "work"
CATEGORY_REST = "rest"
CATEGORY_NEUTRAL = "neutral"
VALID_CATEGORIES = {CATEGORY_WORK, CATEGORY_REST, CATEGORY_NEUTRAL}

_TOKEN_CLEAN_RE = re.compile(r'[^a-z0-9\s]')
_NESTED_QUANTIFIER_RE = re.compile(r'\([^)]*[\*\+\?][^)]*\)[*+?{]')


def is_safe_regex(pattern: str, max_length: int = 1000) -> bool:
    """Validate pattern to prevent catastrophic backtracking (ReDoS) and invalid regex."""
    if not pattern or len(pattern) > max_length:
        return False
    try:
        re.compile(pattern)
    except re.error:
        return False
    if _NESTED_QUANTIFIER_RE.search(pattern):
        return False
    return True


class SimpleTFIDFClassifier:
    """Lightweight pure-Python N-Gram TF-IDF Cosine Similarity engine."""

    WORK_CORPUS = [
        "vs code visual studio pycharm intellij editor ide code compiler debug build python rust c++ java javascript react typescript git github terminal bash shell documentation stack overflow",
        "word excel powerpoint pdf document spreadsheet presentation google docs jupyter overleaf latex report paper writing draft thesis research study lecture course syllabus assignment",
        "jira confluence slack notion trello linear zoom meeting review pull request devops docker kubernetes aws azure webex teams figma design workspace"
    ]

    REST_CORPUS = [
        "steam vlc netflix youtube spotify discord twitch crunchyroll anime manga episode tập kaguya epic games gog galaxy xbox game gaming play video movie stream audio music player broadcast tv soundcloud bilibili webtoon manhwa series entertainment cinema film watch",
        "reddit twitter facebook instagram tiktok social media feed watch shorts reels scroll leisure entertainment movie video stream sitcom cartoon animation gaming gameplay"
    ]

    NEUTRAL_CORPUS = [
        "explorer finder desktop task manager settings system preferences file explorer calculator notepad blank new tab home search control panel system toolkit legion armoury crate device manager properties volume network bluetooth hardware monitor update shellhost start"
    ]

    def __init__(self):
        self.doc_freq = Counter()
        self.total_docs = 0
        self.class_vectors = {}
        self.vocab = set()
        self._build_index()

    def _extract_tokens(self, text: str) -> List[str]:
        if not text:
            return []
        clean = _TOKEN_CLEAN_RE.sub(' ', text.lower()).strip()
        words = clean.split()
        ngrams = []
        for w in words:
            ngrams.append(w)
            lw = len(w)
            if lw >= 3:
                for i in range(lw - 2):
                    ngrams.append(w[i:i+3])
            if lw >= 4:
                for i in range(lw - 3):
                    ngrams.append(w[i:i+4])
        return ngrams

    def _build_index(self):
        all_docs = []
        for text in self.WORK_CORPUS:
            all_docs.append((CATEGORY_WORK, self._extract_tokens(text)))
        for text in self.REST_CORPUS:
            all_docs.append((CATEGORY_REST, self._extract_tokens(text)))
        for text in self.NEUTRAL_CORPUS:
            all_docs.append((CATEGORY_NEUTRAL, self._extract_tokens(text)))

        self.total_docs = len(all_docs)

        for cat, tokens in all_docs:
            unique_tokens = set(tokens)
            for t in unique_tokens:
                self.doc_freq[t] += 1
                self.vocab.add(t)

        class_tokens = {CATEGORY_WORK: Counter(), CATEGORY_REST: Counter(), CATEGORY_NEUTRAL: Counter()}
        for cat, tokens in all_docs:
            class_tokens[cat].update(tokens)

        for cat, token_counts in class_tokens.items():
            total_count = sum(token_counts.values()) or 1
            vector = {}
            for token, count in token_counts.items():
                tf = count / total_count
                df = self.doc_freq.get(token, 1)
                idf = math.log(1.0 + (self.total_docs / (1.0 + df)))
                vector[token] = tf * idf

            norm = math.sqrt(sum(val * val for val in vector.values())) or 1.0
            for token in vector:
                vector[token] /= norm
            self.class_vectors[cat] = vector

    def predict(self, text: str) -> Tuple[str, float, Dict[str, float]]:
        tokens = self._extract_tokens(text)
        if not tokens:
            return CATEGORY_NEUTRAL, 0.0, {CATEGORY_WORK: 0.0, CATEGORY_REST: 0.0, CATEGORY_NEUTRAL: 0.0}

        counts = Counter(tokens)
        total_count = len(tokens)
        query_vec = {}
        for t, count in counts.items():
            if t in self.vocab:
                tf = count / total_count
                df = self.doc_freq.get(t, 1)
                idf = math.log(1.0 + (self.total_docs / (1.0 + df)))
                query_vec[t] = tf * idf

        q_norm = math.sqrt(sum(val * val for val in query_vec.values()))
        if q_norm == 0:
            return CATEGORY_NEUTRAL, 0.0, {CATEGORY_WORK: 0.0, CATEGORY_REST: 0.0, CATEGORY_NEUTRAL: 0.0}

        for t in query_vec:
            query_vec[t] /= q_norm

        scores = {}
        for cat, class_vec in self.class_vectors.items():
            dot = 0.0
            for t, val in query_vec.items():
                if t in class_vec:
                    dot += val * class_vec[t]
            scores[cat] = dot

        best_cat = max(scores, key=scores.get)
        best_score = scores[best_cat]
        return best_cat, best_score, scores


class _ClassOrInstanceMethod:
    """Descriptor enabling dual invocation as instance method or class method via default instance."""
    def __init__(self, fn):
        self.fn = fn

    def __get__(self, instance, owner):
        if instance is None:
            default_inst = owner.get_default_instance()
            return getattr(default_inst, self.fn.__name__)
        return self.fn.__get__(instance, owner)


class TaskClassifier:
    """
    3-Tier Hybrid Task Classifier:
    - Tier 1: O(1) LRU Hash Map (<0.001ms)
    - Tier 2: Safe Regex + N-Gram TF-IDF Cosine Similarity (<0.1ms)
    - Tier 3: Async Background Worker Pool for ambiguous window titles
    """

    _default_instance = None
    _default_lock = threading.Lock()

    @classmethod
    def get_default_instance(cls) -> "TaskClassifier":
        if cls._default_instance is None:
            with cls._default_lock:
                if cls._default_instance is None:
                    cls._default_instance = cls()
        return cls._default_instance

    def __init__(self, lru_maxsize: int = 2000, worker_count: int = 2):
        self._lru_maxsize = max(100, lru_maxsize)
        self._lru_cache = OrderedDict()
        self._lock = threading.RLock()

        # Stats counters
        self._tier1_hits = 0
        self._tier2_hits = 0
        self._tier3_hits = 0
        self._total_classifications = 0

        # Tier 2 Engines
        self._tfidf_engine = SimpleTFIDFClassifier()
        self._safe_regex_cache: Dict[str, Optional[re.Pattern]] = {}
        self._init_default_patterns()

        # Tier 3 Async Background Worker Pool
        self._bg_queue = queue.Queue(maxsize=1000)
        self._stop_event = threading.Event()
        self._workers = []
        for i in range(max(1, worker_count)):
            w = threading.Thread(target=self._bg_worker_loop, daemon=True, name=f"TaskClassifierWorker-{i}")
            w.start()
            self._workers.append(w)

    def _init_default_patterns(self):
        work_pats = [
            r"(?i)\b(vs code|vscode|visual studio|pycharm|intellij|sublime|notepad\+\+|eclipse|rstudio|word|excel|powerpoint|pdf|stack overflow|github|gitlab|google docs|jupyter|overleaf|antigravity|terminal|cmd\.exe|powershell|bash|docker|postman|figma|jira|confluence|slack|python|rust|golang|c\+\+|compiler|developer|coding|programming|tutorial|documentation|arxiv|wikipedia|chatgpt|claude)\b"
        ]
        rest_pats = [
            r"(?i)\b(steam|vlc|netflix|youtube|spotify|discord|twitch|crunchyroll|anime|manga|episode|tập|kaguya|steins;gate|bojack|epic games|gog galaxy|xbox|hulu|disney|prime video|reddit|game|twitch\.tv|movie|stream|video|limbus|hades|sifu)\b"
        ]
        neutral_pats = [
            r"(?i)\b(explorer\.exe|finder|desktop|task manager|taskmgr|settings|calculator|system preferences|new tab|blank|toolkit|shellhost|shellexperiencehost|startmenuexperiencehost|searchhost|control panel)\b"
        ]

        self._compiled_rules = []
        for pat in work_pats:
            if is_safe_regex(pat):
                self._compiled_rules.append((re.compile(pat), CATEGORY_WORK))
        for pat in rest_pats:
            if is_safe_regex(pat):
                self._compiled_rules.append((re.compile(pat), CATEGORY_REST))
        for pat in neutral_pats:
            if is_safe_regex(pat):
                self._compiled_rules.append((re.compile(pat), CATEGORY_NEUTRAL))

    def _bg_worker_loop(self):
        while not self._stop_event.is_set():
            try:
                item = self._bg_queue.get(timeout=0.5)
                if item is None:
                    self._bg_queue.task_done()
                    break
                process_name, title = item
                try:
                    resolved_cat = self._enrich_ambiguous_title(process_name, title)
                    key = (process_name.lower().strip(), title.lower().strip())
                    with self._lock:
                        if key not in self._lru_cache:
                            self._lru_cache[key] = resolved_cat
                            if len(self._lru_cache) > self._lru_maxsize:
                                self._lru_cache.popitem(last=False)
                except Exception as e:
                    logger.exception(f"[TaskClassifierWorker] Tier 3 enrichment failed for process='{process_name}', title='{title}': {e}")
                finally:
                    self._bg_queue.task_done()
            except queue.Empty:
                continue

    def _enrich_ambiguous_title(self, process_name: str, title: str) -> str:
        """Deep background evaluation of ambiguous window titles."""
        text = f"{process_name} {title}".lower()
        if any(w in text for w in ["github", "stackoverflow", "docs", "arxiv", "paper", "py", "rs", "cpp", "js", "ts", "json", "xml", "sql", "code", "debug"]):
            return CATEGORY_WORK
        if any(w in text for w in ["yt", "vlc", "game", "play", "stream", "tv", "movie", "anime", "manga", "episode", "tập"]):
            return CATEGORY_REST
        if any(w in text for w in ["toolkit", "task manager", "settings", "control", "hardware", "system", "shell"]):
            return CATEGORY_NEUTRAL
        best_cat, score, _ = self._tfidf_engine.predict(text)
        return best_cat if score > 0.35 else CATEGORY_NEUTRAL

    @_ClassOrInstanceMethod
    def classify(self, process_name: str, title: str) -> str:
        """
        Classify a window process name and title into 'work', 'rest', or 'neutral'.
        Executes within <1ms latency SLA.
        """
        proc_str = str(process_name or "").strip().lower()
        title_str = str(title or "").strip().lower()[:512]
        key = (proc_str, title_str)

        with self._lock:
            self._total_classifications += 1

            # --- Tier 1: O(1) LRU Cache Lookup (<0.001ms) ---
            if key in self._lru_cache:
                self._lru_cache.move_to_end(key)
                self._tier1_hits += 1
                return self._lru_cache[key]

        # --- Tier 2: Safe Regex & N-Gram TF-IDF Cosine Similarity (<0.1ms) ---
        text = f"{proc_str} {title_str}"
        category_found = None

        # 1. Regex evaluation
        for compiled_re, category in self._compiled_rules:
            if compiled_re.search(text):
                category_found = category
                break

        # 2. Browser / dev heuristics if regex did not hit
        if not category_found:
            # Check dev process names directly
            dev_procs = {"pycharm", "vscode", "code", "studio", "rstudio", "eclipse", "sublime", "xcode", "unity", "godot", "terminal", "powershell", "cmd", "bash", "antigravity"}
            proc_base = proc_str.replace(".exe", "")
            if proc_base in dev_procs:
                category_found = CATEGORY_WORK

        # 3. TF-IDF Cosine Similarity evaluation
        best_cat, score, _ = self._tfidf_engine.predict(text)
        if not category_found and score >= 0.35:
            category_found = best_cat

        if category_found in VALID_CATEGORIES:
            with self._lock:
                self._tier2_hits += 1
                self._lru_cache[key] = category_found
                if len(self._lru_cache) > self._lru_maxsize:
                    self._lru_cache.popitem(last=False)
            return category_found

        # --- Tier 3: Async Background Enrichment for Ambiguous Window Titles ---
        fallback_cat = CATEGORY_NEUTRAL
        with self._lock:
            self._tier3_hits += 1

        try:
            self._bg_queue.put_nowait((proc_str, title_str))
        except queue.Full:
            pass

        return fallback_cat

    @_ClassOrInstanceMethod
    def clear_cache(self) -> None:
        """Clear LRU cache and reset hit counters."""
        with self._lock:
            self._lru_cache.clear()
            self._tier1_hits = 0
            self._tier2_hits = 0
            self._tier3_hits = 0
            self._total_classifications = 0

    @_ClassOrInstanceMethod
    def get_stats(self) -> Dict[str, Any]:
        """Return hit rates and metrics for Tier 1, Tier 2, Tier 3."""
        with self._lock:
            total = self._total_classifications
            t1 = self._tier1_hits
            t2 = self._tier2_hits
            t3 = self._tier3_hits

            return {
                "tier1_hits": t1,
                "tier2_hits": t2,
                "tier3_hits": t3,
                "total_classifications": total,
                "tier1_hit_rate": round(t1 / total, 4) if total > 0 else 0.0,
                "tier2_hit_rate": round(t2 / total, 4) if total > 0 else 0.0,
                "tier3_hit_rate": round(t3 / total, 4) if total > 0 else 0.0,
                "lru_cache_size": len(self._lru_cache),
                "lru_maxsize": self._lru_maxsize,
                "bg_queue_size": self._bg_queue.qsize()
            }


# Module-level convenience functions
def classify(process_name: str, title: str) -> str:
    return TaskClassifier.classify(process_name, title)

def clear_cache() -> None:
    TaskClassifier.clear_cache()

def get_stats() -> Dict[str, Any]:
    return TaskClassifier.get_stats()
