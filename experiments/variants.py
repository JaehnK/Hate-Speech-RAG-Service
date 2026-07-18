from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExperimentVariant:
    name: str
    taxonomy_k: int
    definition_k: int
    example_k: int


VARIANTS: dict[str, ExperimentVariant] = {
    "haiku_only": ExperimentVariant(
        name="haiku_only",
        taxonomy_k=0,
        definition_k=0,
        example_k=0,
    ),
    "definitions_only": ExperimentVariant(
        name="definitions_only",
        taxonomy_k=4,
        definition_k=4,
        example_k=0,
    ),
    "examples_only": ExperimentVariant(
        name="examples_only",
        taxonomy_k=0,
        definition_k=0,
        example_k=6,
    ),
    "three_vector_rag": ExperimentVariant(
        name="three_vector_rag",
        taxonomy_k=4,
        definition_k=4,
        example_k=6,
    ),
}

ALIASES: dict[str, str] = {
    "dual_rag": "three_vector_rag",
}


def get_variants(names: list[str] | None = None) -> list[ExperimentVariant]:
    if not names:
        return list(VARIANTS.values())
    return [VARIANTS[ALIASES.get(name, name)] for name in names]
