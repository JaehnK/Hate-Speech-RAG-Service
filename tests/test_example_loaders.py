from pathlib import Path

from app.analysis.example_loaders import load_example_documents
from app.analysis.license_policy import COMMERCIAL_OK, SHAREALIKE_REVIEW
from app.analysis.license_policy import examples_allowed, normalize_license_tier


def test_license_policy_defaults_to_commercial_ok_only() -> None:
    source = {
        "corpus_target": {"examples": True},
        "license_status": "cc_by_sa_4_0_observed_review_required",
    }

    assert normalize_license_tier(source["license_status"]) == SHAREALIKE_REVIEW
    assert not examples_allowed(source)
    assert examples_allowed(source, allowed_license_tiers=(SHAREALIKE_REVIEW,))


def test_beep_loader_maps_labeled_rows_when_sharealike_allowed(tmp_path) -> None:
    dataset_path = tmp_path / "beep"
    labeled_path = dataset_path / "labeled"
    labeled_path.mkdir(parents=True)
    (labeled_path / "train.tsv").write_text(
        "\n".join(
            [
                "comments\tcontain_gender_bias\tbias\thate",
                "성별을 이유로 비하한다\tTrue\tgender\thate",
                "그냥 평범한 댓글\tFalse\tnone\tnone",
            ]
        ),
        encoding="utf-8",
    )
    manifest_path = _write_manifest(
        tmp_path,
        [
            {
                "id": "beep",
                "local_path": str(dataset_path),
                "source_revision": "rev",
                "license_status": "cc_by_sa_4_0_observed_review_required",
                "corpus_target": {"examples": True},
            }
        ],
    )

    blocked = load_example_documents(manifest_path, project_root=tmp_path)
    loaded = load_example_documents(
        manifest_path,
        project_root=tmp_path,
        allowed_license_tiers=(SHAREALIKE_REVIEW,),
    )

    assert blocked == []
    assert len(loaded) == 2
    assert loaded[0].mapped_categories == ("gender",)
    assert loaded[0].is_hate_speech
    assert loaded[1].mapped_categories == ("unclassified",)
    assert not loaded[1].is_hate_speech


def test_k_haters_loader_maps_commercial_rows(tmp_path) -> None:
    dataset_path = tmp_path / "k-haters-hf"
    dataset_path.mkdir()
    (dataset_path / "train.jsonl").write_text(
        "\n".join(
            [
                '{"text": "성별 비하 댓글", "label": "L2_hate", "target_label": ["gender"]}',
                '{"text": "정상 댓글", "label": "normal", "target_label": []}',
            ]
        ),
        encoding="utf-8",
    )
    manifest_path = _write_manifest(
        tmp_path,
        [
            {
                "id": "k-haters",
                "data_local_path": str(dataset_path),
                "source_revision": "rev",
                "license_status": "cc_by_4_0_observed",
                "corpus_target": {"examples": True},
            }
        ],
    )

    loaded = load_example_documents(
        manifest_path,
        project_root=tmp_path,
        allowed_license_tiers=(COMMERCIAL_OK,),
    )

    assert len(loaded) == 2
    assert loaded[0].mapped_categories == ("gender",)
    assert loaded[0].target_labels == ("gender",)
    assert loaded[1].mapped_categories == ("unclassified",)


def test_kodoli_loader_uses_deterministic_split(tmp_path) -> None:
    dataset_path = tmp_path / "kodoli"
    data_path = dataset_path / "data"
    data_path.mkdir(parents=True)
    rows = ["index,sentences,abuse,sentiment,offensiveness"]
    for index in range(1, 31):
        rows.append(f"{index},공격적인 표현 {index},ABU,NEG,OFF")
    (data_path / "kodoli.csv").write_text("\n".join(rows), encoding="utf-8")
    manifest_path = _write_manifest(
        tmp_path,
        [
            {
                "id": "kodoli",
                "local_path": str(dataset_path),
                "source_revision": "rev",
                "license_status": "cc_by_sa_4_0_observed_review_required",
                "corpus_target": {"examples": True},
            }
        ],
    )

    loaded = load_example_documents(
        manifest_path,
        project_root=tmp_path,
        allowed_license_tiers=(SHAREALIKE_REVIEW,),
        split="train",
    )

    assert loaded
    assert {document.source_split for document in loaded} == {"train"}
    assert all(document.mapped_categories == ("profanity",) for document in loaded)


def _write_manifest(tmp_path: Path, datasets: list[dict]) -> Path:
    manifest_path = tmp_path / "dataset_sources.yaml"
    manifest_path.write_text(
        "datasets:\n" + "\n".join(_dataset_yaml(dataset) for dataset in datasets),
        encoding="utf-8",
    )
    return manifest_path


def _dataset_yaml(dataset: dict) -> str:
    lines = ["  -"]
    for key, value in dataset.items():
        if isinstance(value, dict):
            lines.append(f"    {key}:")
            for child_key, child_value in value.items():
                lines.append(f"      {child_key}: {str(child_value).lower()}")
        else:
            lines.append(f"    {key}: {value}")
    return "\n".join(lines)
