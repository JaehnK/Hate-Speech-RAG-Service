from experiments.compare_results import summarize


def test_summarize_groups_usage_and_cost_by_variant() -> None:
    summaries = summarize(
        [
            {
                "variant": "three_vector_rag",
                "status": "succeeded",
                "usage": {"input_tokens": 1000, "output_tokens": 100},
                "attempts": 1,
            },
            {
                "variant": "three_vector_rag",
                "status": "failed",
                "usage": {},
                "attempts": 2,
            },
        ]
    )

    summary = summaries[0]

    assert summary["variant"] == "three_vector_rag"
    assert summary["total"] == 2
    assert summary["succeeded"] == 1
    assert summary["failed"] == 1
    assert summary["failure_rate"] == 0.5
    assert summary["retry_rate"] == 0.5
    assert summary["estimated_haiku_cost_usd"] == 0.0015
