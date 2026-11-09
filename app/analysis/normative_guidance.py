"""Use the labels of retrieved similar cases to steer normative-document retrieval.

Short colloquial comments and formal standards share little vocabulary, so ranking
standards by similarity to the comment alone picks loosely related clauses. The
similar-case store does match comments well, and every case carries category labels.
The categories those cases agree on are used to filter the normative corpus before
ranking. The LLM still makes the decision; this only chooses which standards it sees.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from app.analysis.models import ExampleSearchResult
from app.analysis.taxonomy import POLITICAL_CATEGORIES

MIN_VOTES = 2


def guided_categories(examples: Iterable[ExampleSearchResult], min_votes: int = MIN_VOTES) -> tuple[str, ...]:
    """Categories that at least `min_votes` hate-labelled similar cases share."""
    votes: Counter[str] = Counter()
    for example in examples:
        if not example.is_hate_speech:
            continue
        categories = set(example.mapped_categories) - {"unclassified"}
        if "political" in example.target_labels:
            # The corpus cannot tell which of the six political categories applies.
            categories |= set(POLITICAL_CATEGORIES)
        votes.update(categories)
    return tuple(category for category, count in votes.most_common() if count >= min_votes)


def category_filter(categories: tuple[str, ...]) -> dict | None:
    """Chroma `where` clause matching documents tagged with any of the categories."""
    clauses = [{f"cat_{category}": True} for category in categories]
    if not clauses:
        return None
    return clauses[0] if len(clauses) == 1 else {"$or": clauses}
