import math
import re
from typing import List, Optional, Tuple

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from models.analysis import DimensionScore, Gap
from models.job import JobDescription
from models.resume import Resume
from services.scorers.base import DimensionResult


_GAP_THRESHOLD = 0.5
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _split_sentences(text: str) -> List[str]:
    parts = [p.strip() for p in _SENTENCE_SPLIT.split(text) if p and p.strip()]
    return parts


def _collect_resume_bullets(resume: Resume) -> List[Tuple[str, str]]:
    """Return (path, text) pairs so suggestions can target the source bullet."""
    out: List[Tuple[str, str]] = []
    for i, exp in enumerate(resume.experience):
        for j, desc in enumerate(exp.descriptions):
            out.append((f"experience[{i}].descriptions[{j}]", desc))
    for i, proj in enumerate(resume.projects or []):
        for j, c in enumerate(proj.contributions):
            out.append((f"projects[{i}].contributions[{j}]", c))
    return out


def _cosine(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return dot / (na * nb)


class ExperienceScorer:
    name = "experience"
    default_weight = 0.30

    def applies(self, jd: JobDescription) -> bool:
        return bool(jd.description and jd.description.strip())

    def score(self, resume: Resume, jd: JobDescription, ai: Optional[object]) -> DimensionResult:
        jd_sentences = _split_sentences(jd.description or "")
        bullets = _collect_resume_bullets(resume)

        if not jd_sentences:
            return DimensionResult(
                score=DimensionScore(
                    name=self.name,
                    score=100.0,
                    weight=self.default_weight,
                    rationale="JD has no descriptive content",
                ),
                gaps=[],
            )

        if not bullets:
            gap = Gap(
                category="experience",
                item="Resume has no experience bullets to evaluate against the JD",
                severity="high",
            )
            return DimensionResult(
                score=DimensionScore(
                    name=self.name,
                    score=0.0,
                    weight=self.default_weight,
                    rationale="Resume has no experience bullets",
                ),
                gaps=[gap],
            )

        bullet_paths = [b[0] for b in bullets]
        bullet_texts = [b[1] for b in bullets]

        ai_fallback = False
        sims: List[List[float]] = []
        if ai is not None:
            try:
                all_vecs = ai.embed(jd_sentences + bullet_texts)  # type: ignore[attr-defined]
                jd_vecs = all_vecs[: len(jd_sentences)]
                bullet_vecs = all_vecs[len(jd_sentences):]
                sims = [
                    [_cosine(jv, bv) for bv in bullet_vecs]
                    for jv in jd_vecs
                ]
            except Exception:
                ai_fallback = True
                sims = []

        if not sims:
            # Keyword (TF-IDF) path.
            vec = TfidfVectorizer().fit(jd_sentences + bullet_texts)
            jd_tfidf = vec.transform(jd_sentences)
            bullet_tfidf = vec.transform(bullet_texts)
            sim_matrix = cosine_similarity(jd_tfidf, bullet_tfidf)
            sims = sim_matrix.tolist()

        # Per-JD-sentence top-1 similarity + best bullet.
        sentence_matches = []
        gaps: List[Gap] = []
        top1s: List[float] = []
        for s_idx, jd_sentence in enumerate(jd_sentences):
            row = sims[s_idx]
            best_idx = max(range(len(row)), key=lambda i: row[i])
            best_sim = row[best_idx]
            top1s.append(best_sim)
            sentence_matches.append({
                "jd_sentence": jd_sentence,
                "best_bullet_index": bullet_paths[best_idx],
                "best_bullet_text": bullet_texts[best_idx],
                "similarity": float(best_sim),
            })
            if best_sim < _GAP_THRESHOLD:
                trimmed = jd_sentence if len(jd_sentence) <= 200 else jd_sentence[:197] + "..."
                gaps.append(Gap(category="experience", item=trimmed, severity="medium"))

        avg = sum(top1s) / len(top1s)
        score_pct = max(0.0, min(100.0, avg * 100.0))
        rationale = f"avg top-1 sim {avg:.2f} across {len(jd_sentences)} JD sentence(s)"
        if ai_fallback:
            rationale = "[fallback] " + rationale

        return DimensionResult(
            score=DimensionScore(
                name=self.name,
                score=score_pct,
                weight=self.default_weight,
                rationale=rationale,
            ),
            gaps=gaps,
            metadata={"jd_sentence_matches": sentence_matches},
        )
