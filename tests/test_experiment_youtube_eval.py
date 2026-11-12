from experiments.evaluate_youtube import evaluate, predicted_scope


def _row(item_id, is_hate, categories, scope=None, repeat=0):
    payload = {"is_hate_speech": is_hate, "categories": categories}
    if scope:
        payload["target_scope"] = scope
    return {"item_id": item_id, "status": "succeeded", "repeat_index": repeat, "payload": payload}


def test_predicted_scope_uses_field_then_categories() -> None:
    assert predicted_scope({"is_hate_speech": False, "categories": ["unclassified"]}) == "none"
    assert predicted_scope({"is_hate_speech": True, "categories": ["profanity"]}) == "individual"
    assert predicted_scope({"is_hate_speech": True, "categories": ["age", "profanity"]}) == "group"
    assert predicted_scope({"is_hate_speech": True, "categories": ["age"], "target_scope": "individual"}) == "individual"


def test_evaluate_scores_scope_repeats_and_groups() -> None:
    gold = [
        {"item_id": "a", "is_hate_speech": True, "target_scope": "group", "group": "g1"},
        {"item_id": "b", "is_hate_speech": True, "target_scope": "group", "group": "g1"},
        {"item_id": "c", "is_hate_speech": False, "target_scope": "none", "group": "g2"},
    ]
    results = [
        _row("a", True, ["identity"], "group"),
        _row("a", True, ["identity"], "group", repeat=1),
        _row("b", True, ["profanity"], "individual"),
        _row("b", True, ["identity"], "group", repeat=1),
        _row("c", False, ["unclassified"]),
        _row("c", False, ["unclassified"], repeat=1),
    ]
    report = evaluate(results, gold)
    assert report["attack"]["f1"] == 1.0
    assert report["group_hate"]["recall"] == 0.5
    assert report["repeat"]["scope_stable"] == 2 / 3
    assert report["consistency"]["groups"]["g1"]["agreement"] == 0.75
