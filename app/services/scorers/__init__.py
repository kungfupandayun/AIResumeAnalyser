from services.scorers.education import EducationScorer
from services.scorers.experience import ExperienceScorer
from services.scorers.seniority import SeniorityScorer
from services.scorers.skills import SkillsScorer
from services.scorers.summary import SummaryAlignmentScorer


# Order is informational only — the orchestrator iterates and re-normalizes
# weights, so registry order does not affect the score.
REGISTRY = [
    SkillsScorer(),
    ExperienceScorer(),
    SeniorityScorer(),
    EducationScorer(),
    SummaryAlignmentScorer(),
]
