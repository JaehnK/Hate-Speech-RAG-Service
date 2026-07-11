from app.analysis.definition_ingest import load_manifest_definition_documents


def test_definition_loader_only_includes_allowed_license_tiers(tmp_path) -> None:
    allowed = tmp_path / "allowed"
    blocked = tmp_path / "blocked"
    allowed.mkdir()
    blocked.mkdir()
    (allowed / "README.md").write_text("# Labels\n\nThis guideline defines protected target labels for classification.", encoding="utf-8")
    (blocked / "README.md").write_text("# Private\n\nThis document must not enter the retrieval corpus.", encoding="utf-8")
    manifest = tmp_path / "sources.yaml"
    manifest.write_text(
        f"""datasets:
  - id: allowed
    name: Allowed
    local_path: {allowed}
    source_url: https://example.com/allowed
    license_status: cc_by_4_0_observed_review_required
    corpus_target:
      definitions: true
  - id: blocked
    name: Blocked
    local_path: {blocked}
    license_status: permission_required
    corpus_target:
      definitions: true
""",
        encoding="utf-8",
    )

    documents = load_manifest_definition_documents(manifest, project_root=tmp_path)

    assert documents
    assert {document.source_id for document in documents} == {"allowed"}
