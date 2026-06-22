from rag_eval.base import BaseEvaluator
from rag_eval.runner import EvaluationRunner
from rag_eval.schemas import EvalCase, EvalDataset, MetricScore


class DummyEvaluator(BaseEvaluator):
    """A dummy evaluator for testing the runner logic."""

    async def evaluate_case(self, case: EvalCase) -> list[MetricScore]:
        return [MetricScore(name="dummy_metric", score=0.85, reason="Looks good")]


async def test_eval_case_creation():
    case = EvalCase(question="What is Python?", ground_truth="A programming language")
    assert case.question == "What is Python?"
    assert case.ground_truth == "A programming language"
    assert case.answer is None
    assert case.contexts is None


async def test_evaluation_runner_success():
    # Arrange
    dataset = EvalDataset(
        name="test_dataset",
        cases=[EvalCase(question="Q1", ground_truth="GT1"), EvalCase(question="Q2", ground_truth="GT2")],
    )

    # Mock RAG pipeline returning dictionary
    async def mock_pipeline(question: str) -> dict:
        return {"answer": f"Answer to {question}", "contexts": [f"Context for {question}"]}

    evaluator = DummyEvaluator()
    runner = EvaluationRunner(evaluators=[evaluator])

    # Act
    result = await runner.run(dataset, mock_pipeline, concurrency_limit=2)

    # Assert
    assert result.dataset_name == "test_dataset"
    assert len(result.results) == 2
    assert result.results[0].case.answer == "Answer to Q1"
    assert result.results[0].case.contexts == ["Context for Q1"]
    assert result.results[0].metrics[0].name == "dummy_metric"
    assert result.results[0].metrics[0].score == 0.85
    assert result.summary["dummy_metric"] == 0.85
    assert result.total_latency_sec > 0


async def test_evaluation_runner_pipeline_error():
    # Arrange
    dataset = EvalDataset(name="test_dataset_error", cases=[EvalCase(question="Q1", ground_truth="GT1")])

    # Mock pipeline throwing an exception
    async def mock_error_pipeline(question: str) -> dict:
        raise RuntimeError("Pipeline failed!")

    evaluator = DummyEvaluator()
    runner = EvaluationRunner(evaluators=[evaluator])

    # Act
    result = await runner.run(dataset, mock_error_pipeline)

    # Assert
    assert len(result.results) == 1
    assert result.results[0].case.answer is not None
    assert "ERROR: Pipeline failed!" in result.results[0].case.answer
    assert result.results[0].case.contexts == []
    assert result.results[0].metrics[0].name == "dummy_metric"
