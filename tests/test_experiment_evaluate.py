from experiments.evaluate_results import evaluate


def test_evaluate_reports_binary_and_category_metrics() -> None:
    gold = [
        {"item_id": "1", "is_hate_speech": True, "categories": ["gender"]},
        {"item_id": "2", "is_hate_speech": False, "categories": ["unclassified"]},
    ]
    rows = [
        {"item_id": "1", "variant": "dual_rag", "status": "succeeded", "payload": {"is_hate_speech": True, "categories": ["gender"]}},
        {"item_id": "2", "variant": "dual_rag", "status": "succeeded", "payload": {"is_hate_speech": False, "categories": ["unclassified"]}},
    ]

    summary = evaluate(rows, gold)[0]

    assert summary["coverage"] == 1
    assert summary["binary_accuracy"] == 1
    assert summary["category_micro_f1"] == 1


def test_evaluate_measures_repeat_stability_without_inflating_coverage() -> None:
    gold = [{"item_id": "1", "is_hate_speech": True, "categories": ["gender"]}]
    rows = [
        {"item_id": "1", "variant": "dual_rag", "repeat_index": 0, "status": "succeeded", "payload": {"is_hate_speech": True, "categories": ["gender"]}},
        {"item_id": "1", "variant": "dual_rag", "repeat_index": 1, "status": "succeeded", "payload": {"is_hate_speech": False, "categories": ["unclassified"]}},
        {"item_id": "1", "variant": "dual_rag", "repeat_index": 2, "status": "succeeded", "payload": {"is_hate_speech": True, "categories": ["gender"]}},
    ]

    summary = evaluate(rows, gold)[0]

    assert summary["coverage"] == 1
    assert summary["evaluated_predictions"] == 3
    assert summary["repeat_item_count"] == 1
    assert summary["repeat_stability"] == 0
