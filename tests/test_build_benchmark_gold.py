import json

import yaml

from experiments.build_benchmark_gold import build_benchmark


def _write_k_haters(tmp_path, split: str, rows: list[dict]) -> None:
    data = tmp_path / "k-haters-hf"
    data.mkdir(exist_ok=True)
    (data / f"{split}.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def test_build_benchmark_drops_train_overlap_and_keeps_category_floor(tmp_path) -> None:
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(yaml.safe_dump({"datasets": [{"id": "k-haters", "local_path": "k-haters", "data_local_path": "k-haters-hf"}]}))
    _write_k_haters(tmp_path, "train", [{"text": "중복 문장", "label": "normal", "target_label": []}])
    test_rows = [{"text": "중복 문장", "label": "normal", "target_label": []}]
    test_rows += [{"text": f"욕설 {i}", "label": "offensive", "target_label": []} for i in range(40)]
    test_rows += [{"text": f"나이 {i}", "label": "L1_hate", "target_label": ["age"]} for i in range(3)]
    _write_k_haters(tmp_path, "test", test_rows)

    inputs, gold, summary = build_benchmark("k-haters", "test", 10, min_per_category=3, manifest_path=manifest, project_root=tmp_path)

    assert summary["dropped_train_overlap"] == 1
    assert summary["categories"]["age"] == 3
    assert len(gold) == len(inputs) == 10
    assert {row["item_id"] for row in inputs} == {row["item_id"] for row in gold}
    assert all(row["text"] != "중복 문장" for row in inputs)


def test_build_benchmark_marks_political_targets_for_scoring(tmp_path) -> None:
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(yaml.safe_dump({"datasets": [{"id": "k-haters", "local_path": "k-haters", "data_local_path": "k-haters-hf"}]}))
    _write_k_haters(tmp_path, "train", [])
    _write_k_haters(tmp_path, "test", [
        {"text": "정치 혐오", "label": "L2_hate", "target_label": ["political"]},
        {"text": "지역 혐오", "label": "L1_hate", "target_label": ["region"]},
    ])

    _, gold, _ = build_benchmark("k-haters", "test", None, manifest_path=manifest, project_root=tmp_path)

    assert [row["categories"] for row in gold] == [["political"], ["identity"]]
