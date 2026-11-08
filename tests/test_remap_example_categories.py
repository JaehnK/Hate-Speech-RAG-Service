from app.analysis.embeddings import HashEmbeddingFunction
from app.analysis.models import ExampleDocument
from app.analysis.vector_store import ingest_example_documents
from scripts.remap_example_categories import remap


def _doc(index: int, label: str, targets: list[str], mapped: tuple[str, ...]) -> ExampleDocument:
    return ExampleDocument(
        doc_id=f"k-haters:train:{index}",
        text=f"예시 {index}",
        source_dataset="k-haters",
        source_split="train",
        source_revision=None,
        license_tier="commercial_ok",
        raw_labels={"label": label, "target_label": targets},
        mapped_categories=mapped,
        is_hate_speech=label != "normal",
        target_labels=tuple(targets),
    )


def test_remap_rewrites_stale_categories_and_is_idempotent(tmp_path) -> None:
    ingest_example_documents(
        tmp_path,
        [
            _doc(0, "l2_hate", ["region"], ("other",)),
            _doc(1, "l2_hate", ["political"], ("other",)),
            _doc(2, "l1_hate", ["gender"], ("gender",)),
        ],
        reset=True,
        embedding_function=HashEmbeddingFunction(),
    )

    assert remap(str(tmp_path), apply=False)["changed"] == 2
    result = remap(str(tmp_path), apply=True)

    assert result["updated"] == 2
    assert result["transitions"] == {'["other"] -> ["identity"]': 1, '["other"] -> []': 1}
    assert remap(str(tmp_path), apply=False)["changed"] == 0
