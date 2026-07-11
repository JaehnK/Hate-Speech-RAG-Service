from app.analysis.example_ingest import ingest_manifest_examples
from app.analysis.license_policy import SHAREALIKE_REVIEW
from app.analysis.vector_store import query_example_documents


def test_ingests_allowed_examples_to_chroma(tmp_path) -> None:
    dataset_path = tmp_path / "beep"
    labeled_path = dataset_path / "labeled"
    labeled_path.mkdir(parents=True)
    (labeled_path / "train.tsv").write_text(
        "\n".join(
            [
                "comments\tcontain_gender_bias\tbias\thate",
                "성별을 이유로 모욕하는 댓글\tTrue\tgender\thate",
                "평범한 댓글\tFalse\tnone\tnone",
            ]
        ),
        encoding="utf-8",
    )
    manifest_path = tmp_path / "dataset_sources.yaml"
    manifest_path.write_text(
        "\n".join(
            [
                "datasets:",
                "  - id: beep",
                f"    local_path: {dataset_path}",
                "    source_revision: rev",
                "    license_status: cc_by_sa_4_0_observed_review_required",
                "    corpus_target:",
                "      examples: true",
            ]
        ),
        encoding="utf-8",
    )

    loaded_count, collection_count = ingest_manifest_examples(
        manifest_path=manifest_path,
        persist_directory=tmp_path / "chroma",
        project_root=tmp_path,
        allowed_license_tiers=(SHAREALIKE_REVIEW,),
        reset=True,
    )
    results = query_example_documents(tmp_path / "chroma", "성별 모욕", n_results=1)

    assert loaded_count == 2
    assert collection_count == 2
    assert results[0].source_dataset == "beep"
    assert "gender" in results[0].mapped_categories
