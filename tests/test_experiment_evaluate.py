from experiments.evaluate_results import evaluate


def test_evaluate_reports_binary_and_category_metrics() -> None:
    gold = [
        {"item_id": "1", "is_hate_speech": True, "categories": ["gender"]},
        {"item_id": "2", "is_hate_speech": False, "categories": ["unclassified"]},
    ]
    rows = [
        {"item_id": "1", "variant": "three_vector_rag", "status": "succeeded", "payload": {"is_hate_speech": True, "categories": ["gender"]}},
        {"item_id": "2", "variant": "three_vector_rag", "status": "succeeded", "payload": {"is_hate_speech": False, "categories": ["unclassified"]}},
    ]

    summary = evaluate(rows, gold)[0]

    assert summary["coverage"] == 1
    assert summary["binary_accuracy"] == 1
    assert summary["category_micro_f1"] == 1


def test_evaluate_measures_repeat_stability_without_inflating_coverage() -> None:
    gold = [{"item_id": "1", "is_hate_speech": True, "categories": ["gender"]}]
    rows = [
        {"item_id": "1", "variant": "three_vector_rag", "repeat_index": 0, "status": "succeeded", "payload": {"is_hate_speech": True, "categories": ["gender"]}},
        {"item_id": "1", "variant": "three_vector_rag", "repeat_index": 1, "status": "succeeded", "payload": {"is_hate_speech": False, "categories": ["unclassified"]}},
        {"item_id": "1", "variant": "three_vector_rag", "repeat_index": 2, "status": "succeeded", "payload": {"is_hate_speech": True, "categories": ["gender"]}},
    ]

    summary = evaluate(rows, gold)[0]

    assert summary["coverage"] == 1
    assert summary["evaluated_predictions"] == 3
    assert summary["repeat_item_count"] == 1
    assert summary["repeat_stability"] == 0


def test_evaluate_folds_finer_predictions_into_benchmark_other() -> None:
    gold = [
        {"item_id": "1", "is_hate_speech": True, "categories": ["other"]},
        {"item_id": "2", "is_hate_speech": True, "categories": ["gender"]},
    ]
    rows = [
        {"item_id": "1", "variant": "v", "status": "succeeded", "payload": {"is_hate_speech": True, "categories": ["state_regime"]}},
        {"item_id": "2", "variant": "v", "status": "succeeded", "payload": {"is_hate_speech": True, "categories": ["gender"]}},
    ]

    summary = evaluate(rows, gold, bootstrap_samples=0)[0]

    assert summary["category_micro_f1"] == 1
    assert summary["category_macro_f1"] == 1
    assert summary["per_category"]["other"]["support"] == 1


def test_evaluate_reports_binary_prf_ci_and_mcnemar() -> None:
    gold = [{"item_id": str(i), "is_hate_speech": i % 2 == 0, "categories": ["profanity"] if i % 2 == 0 else ["unclassified"]} for i in range(20)]
    reference = [
        {"item_id": str(i), "variant": "three_vector_rag", "status": "succeeded", "payload": {"is_hate_speech": i % 2 == 0, "categories": []}}
        for i in range(20)
    ]
    baseline = [
        {"item_id": str(i), "variant": "haiku_only", "status": "succeeded", "payload": {"is_hate_speech": True, "categories": []}}
        for i in range(20)
    ]

    summaries = {s["variant"]: s for s in evaluate(reference + baseline, gold, bootstrap_samples=50)}

    assert summaries["three_vector_rag"]["binary_f1"] == 1
    assert summaries["haiku_only"]["binary_precision"] == 0.5
    assert summaries["haiku_only"]["binary_recall"] == 1
    low, high = summaries["haiku_only"]["ci95"]["binary_accuracy"]
    assert low <= 0.5 <= high
    test = summaries["haiku_only"]["mcnemar_vs_reference"]
    assert test["reference_only_correct"] == 10
    assert test["variant_only_correct"] == 0
    assert test["p_value"] < 0.01
    assert "mcnemar_vs_reference" not in summaries["three_vector_rag"]


def test_evaluate_counts_failures_separately_from_coverage() -> None:
    gold = [{"item_id": "1", "is_hate_speech": True, "categories": ["gender"]}, {"item_id": "2", "is_hate_speech": False, "categories": []}]
    rows = [
        {"item_id": "1", "variant": "v", "status": "succeeded", "payload": {"is_hate_speech": True, "categories": ["gender"]}},
        {"item_id": "2", "variant": "v", "status": "failed", "payload": None},
    ]

    summary = evaluate(rows, gold, bootstrap_samples=0)[0]

    assert summary["coverage"] == 0.5
    assert summary["failure_rate"] == 0.5
