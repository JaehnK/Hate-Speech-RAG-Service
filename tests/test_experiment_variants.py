from experiments.variants import get_variants


def test_experiment_variants_define_expected_retrieval_slots() -> None:
    variants = {variant.name: variant for variant in get_variants()}

    assert variants["haiku_only"].taxonomy_k == 0
    assert variants["haiku_only"].definition_k == 0
    assert variants["haiku_only"].example_k == 0
    assert variants["definitions_only"].definition_k > 0
    assert variants["definitions_only"].example_k == 0
    assert variants["examples_only"].definition_k == 0
    assert variants["examples_only"].example_k > 0
    assert variants["three_vector_rag"].taxonomy_k > 0
    assert variants["three_vector_rag"].definition_k > 0
    assert variants["three_vector_rag"].example_k > 0


def test_legacy_dual_rag_variant_name_maps_to_three_vector_rag() -> None:
    variant = get_variants(["dual_rag"])[0]

    assert variant.name == "three_vector_rag"
