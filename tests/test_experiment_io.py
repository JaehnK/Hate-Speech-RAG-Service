from experiments.io import append_jsonl, read_inputs, read_jsonl


def test_experiment_io_reads_inputs_and_jsonl(tmp_path) -> None:
    input_path = tmp_path / "inputs.jsonl"
    input_path.write_text(
        '{"item_id":"1","text":"댓글","source_type":"comment"}\n',
        encoding="utf-8",
    )
    output_path = tmp_path / "outputs" / "result.jsonl"

    inputs = read_inputs(input_path)
    append_jsonl(output_path, [{"item_id": inputs[0].item_id, "ok": True}])

    assert inputs[0].text == "댓글"
    assert read_jsonl(output_path) == [{"item_id": "1", "ok": True}]
