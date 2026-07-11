from app.analysis.embeddings import HashEmbeddingFunction
from app.analysis.llm_client import LlmResponse
from app.analysis.models import ExampleDocument
from app.analysis.rag_classifier import RagClassifier
from app.analysis.rag_ingest import ingest_internal_taxonomy
from app.analysis.vector_store import ingest_example_documents


class FakeLlmClient:
    model = "claude-haiku-4-5-20251001"

    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.calls = []

    def complete(self, prompt: str) -> LlmResponse:
        self.calls.append(prompt)
        return LlmResponse(
            text=self.responses.pop(0),
            model=self.model,
            usage={"input_tokens": 1, "output_tokens": 1},
        )


def test_rag_classifier_returns_valid_payload(tmp_path) -> None:
    embedding = HashEmbeddingFunction()
    ingest_internal_taxonomy(tmp_path, reset=True, embedding_function=embedding)
    ingest_example_documents(
        tmp_path,
        [
            ExampleDocument(
                doc_id="fixture:train:1",
                text="성별을 이유로 비하하는 댓글",
                source_dataset="fixture",
                source_split="train",
                source_revision=None,
                license_tier="commercial_ok",
                mapped_categories=("gender",),
                is_hate_speech=True,
            )
        ],
        reset=True,
        embedding_function=embedding,
    )
    llm = FakeLlmClient(
        [
            """
            {
              "input_text": "성별을 이유로 모욕한다",
              "is_hate_speech": true,
              "categories": ["gender"],
              "target_group": "여성",
              "hate_type": "모욕/비하",
              "reasoning": "성별을 근거로 비하한다.",
              "similar_cases_used": [],
              "definition_docs_used": []
            }
            """
        ]
    )

    result = RagClassifier(tmp_path, llm, embedding_function=embedding).classify_text(
        "성별을 이유로 모욕한다",
        "comment",
    )

    assert result.payload["categories"] == ["gender"]
    assert result.attempts == 1
    assert result.model == "claude-haiku-4-5-20251001"
    assert result.rag_context_status == "complete"
    assert result.example_collection == "hate_speech_examples"
    assert result.definition_collection == "hate_speech_definitions"
    assert result.definition_corpus_version
    assert result.retrieved_examples
    assert result.retrieved_definitions


def test_rag_classifier_retries_invalid_json_contract(tmp_path) -> None:
    embedding = HashEmbeddingFunction()
    ingest_internal_taxonomy(tmp_path, reset=True, embedding_function=embedding)
    ingest_example_documents(tmp_path, [], reset=True, embedding_function=embedding)
    llm = FakeLlmClient(
        [
            '{"input_text": "x", "is_hate_speech": true, "categories": ["unclassified"], '
            '"target_group": null, "hate_type": null, "reasoning": "", '
            '"similar_cases_used": [], "definition_docs_used": []}',
            '{"input_text": "x", "is_hate_speech": false, "categories": ["unclassified"], '
            '"target_group": null, "hate_type": null, "reasoning": "비혐오", '
            '"similar_cases_used": [], "definition_docs_used": []}',
        ]
    )

    result = RagClassifier(tmp_path, llm, embedding_function=embedding).classify_text("x", "comment")

    assert result.attempts == 2
    assert len(llm.calls) == 2
    assert "Previous output failed validation." in llm.calls[1]
