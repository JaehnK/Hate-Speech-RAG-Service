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
