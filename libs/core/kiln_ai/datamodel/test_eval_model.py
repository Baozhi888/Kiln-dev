import pytest
from pydantic import ValidationError

from kiln_ai.datamodel import BasePrompt
from kiln_ai.datamodel.basemodel import KilnParentModel
from kiln_ai.datamodel.eval import (
    Eval,
    EvalConfig,
    EvalConfigType,
    EvalOutputScore,
    EvalRun,
    EvalState,
)
from kiln_ai.datamodel.task import Task
from kiln_ai.datamodel.task_output import (
    DataSource,
    DataSourceType,
    TaskOutputRatingType,
)


@pytest.fixture
def mock_task():
    return Task(name="Test Task", instruction="Test instruction")


def test_eval_state_values():
    assert EvalState.enabled == "enabled"
    assert EvalState.disabled == "disabled"
    assert len(EvalState) == 2


@pytest.fixture
def valid_eval_config_data():
    return {
        "name": "Test Eval Config",
        "config_type": EvalConfigType.g_eval,
        "properties": {"eval_steps": ["step1", "step2"]},
        "model": DataSource(
            type=DataSourceType.synthetic,
            properties={
                "model_name": "gpt-4",
                "model_provider": "openai",
                "adapter_name": "openai_compatible",
            },
        ),
        "prompt": BasePrompt(
            name="Test Prompt",
            prompt="Test prompt",
        ),
    }


@pytest.fixture
def valid_eval_config(valid_eval_config_data):
    return EvalConfig(**valid_eval_config_data)


def test_eval_config_valid(valid_eval_config):
    assert valid_eval_config.name == "Test Eval Config"
    assert valid_eval_config.config_type == EvalConfigType.g_eval
    assert valid_eval_config.properties["eval_steps"] == ["step1", "step2"]
    assert valid_eval_config.model.type == DataSourceType.synthetic
    assert valid_eval_config.model.properties["model_name"] == "gpt-4"
    assert valid_eval_config.model.properties["model_provider"] == "openai"
    assert valid_eval_config.model.properties["adapter_name"] == "openai_compatible"
    assert valid_eval_config.prompt.name == "Test Prompt"
    assert valid_eval_config.prompt.prompt == "Test prompt"


def test_eval_config_missing_prompt(valid_eval_config):
    with pytest.raises(
        ValueError, match="Input should be a valid dictionary or instance of BasePromp"
    ):
        valid_eval_config.prompt = None


def test_eval_config_missing_eval_steps(valid_eval_config):
    with pytest.raises(
        ValueError, match="eval_steps is required and must be a list for g_eval"
    ):
        valid_eval_config.properties = {}


def test_eval_config_invalid_json(valid_eval_config):
    class InvalidClass:
        pass

    with pytest.raises(ValueError, match="Properties must be JSON serializable"):
        valid_eval_config.properties = {
            "eval_steps": [],
            "invalid_key": InvalidClass(),
        }


def test_eval_config_invalid_eval_steps_type(valid_eval_config):
    with pytest.raises(
        ValueError, match="eval_steps is required and must be a list for g_eval"
    ):
        valid_eval_config.properties = {"eval_steps": "not a list"}


def test_eval_config_invalid_config_type(valid_eval_config):
    # Create an invalid config type using string
    with pytest.raises(ValueError):
        valid_eval_config.config_type = "invalid_type"


def test_human_datasource(valid_eval_config):
    with pytest.raises(ValueError):
        valid_eval_config.model.type = DataSourceType.human
        # Not ideal - error isn'd caught until we try to save or set a root field
        valid_eval_config.name = "Test Config"


def test_eval_basic_properties():
    eval = Eval(
        name="Test Eval",
        description="Test Description",
        state=EvalState.enabled,
        current_config_id="config123",
        eval_set_filter_id="tag::tag1",
        eval_configs_filter_id="tag::tag2",
        output_scores=[
            EvalOutputScore(
                name="accuracy",
                type=TaskOutputRatingType.five_star,
            )
        ],
    )

    assert eval.name == "Test Eval"
    assert eval.description == "Test Description"
    assert eval.state == EvalState.enabled
    assert eval.current_config_id == "config123"
    assert eval.output_scores[0].name == "accuracy"
    assert eval.output_scores[0].type == TaskOutputRatingType.five_star


def test_eval_default_values():
    eval = Eval(
        name="Test Eval",
        eval_set_filter_id="tag::tag1",
        eval_configs_filter_id="tag::tag2",
        output_scores=[
            EvalOutputScore(
                name="quality",
                type=TaskOutputRatingType.pass_fail,
            )
        ],
    )

    assert eval.description is None
    assert eval.state == EvalState.enabled
    assert eval.current_config_id is None


def test_eval_parent_task_relationship(mock_task, valid_eval_config_data):
    eval = Eval(
        name="Test Eval",
        parent=mock_task,
        eval_set_filter_id="tag::tag1",
        eval_configs_filter_id="tag::tag2",
        output_scores=[
            EvalOutputScore(
                name="score",
                type=TaskOutputRatingType.pass_fail,
            )
        ],
    )
    config = EvalConfig(parent=eval, **valid_eval_config_data)

    assert eval.parent_task() == mock_task
    assert eval.parent == mock_task
    assert config.parent == eval
    assert config.parent_eval() == eval


def test_eval_parent_task_none():
    eval = Eval(
        name="Test Eval",
        eval_set_filter_id="tag::tag1",
        eval_configs_filter_id="tag::tag2",
        output_scores=[
            EvalOutputScore(
                name="score",
                type=TaskOutputRatingType.pass_fail,
            )
        ],
    )
    assert eval.parent_task() is None


def test_eval_parent_task_wrong_type():
    # Create a non-Task parent
    class DummyParent(KilnParentModel, parent_of={}):
        pass

    with pytest.raises(ValueError):
        Eval(name="Test Eval", parent=DummyParent())


def test_eval_with_persisted_children(mock_task, valid_eval_config_data, tmp_path):
    task_path = tmp_path / "task.kiln"
    mock_task.path = task_path
    mock_task.save_to_file()

    eval = Eval(
        name="Test Eval",
        parent=mock_task,
        eval_set_filter_id="tag::tag1",
        eval_configs_filter_id="tag::tag2",
        output_scores=[
            EvalOutputScore(
                name="accuracy",
                type=TaskOutputRatingType.pass_fail,
            )
        ],
    )
    eval.save_to_file()

    # Add config using the parent relationship
    config = EvalConfig(parent=eval, **valid_eval_config_data)
    config.save_to_file()

    run = EvalRun(
        parent=config,
        dataset_id="dataset123",
        task_run_config_id="config456",
        input='{"key": "value"}',
        output='{"result": "success"}',
        scores={"accuracy": 0.95},
    )
    run.save_to_file()

    # Test configs can be retrieved from disk
    evals = mock_task.evals()
    assert len(evals) == 1
    assert evals[0].name == "Test Eval"
    configs = evals[0].configs()
    assert len(configs) == 1
    assert configs[0].model.properties["model_provider"] == "openai"

    # and back up
    assert configs[0].parent_eval().parent_task().path == task_path

    # Test runs can be retrieved from disk
    runs = configs[0].runs()
    assert len(runs) == 1
    assert runs[0].dataset_id == "dataset123"
    assert runs[0].task_run_config_id == "config456"
    assert runs[0].input == '{"key": "value"}'
    assert runs[0].output == '{"result": "success"}'
    assert runs[0].scores == {"accuracy": 0.95}

    # and back up
    assert runs[0].parent_eval_config().parent_eval().parent_task().path == task_path


def test_eval_run_valid_creation():
    """Test creating an EvalRun with valid data"""
    eval_run = EvalRun(
        dataset_id="dataset123",
        task_run_config_id="config456",
        input='{"key": "value"}',  # JSON formatted input
        output='{"result": "success"}',  # JSON formatted output
        scores={"accuracy": 0.95},
    )

    assert eval_run.dataset_id == "dataset123"
    assert eval_run.task_run_config_id == "config456"
    assert eval_run.input == '{"key": "value"}'
    assert eval_run.output == '{"result": "success"}'
    assert eval_run.scores == {"accuracy": 0.95}


def test_eval_run_plaintext():
    """Test creating an EvalRun with plaintext input/output"""
    eval_run = EvalRun(
        dataset_id="dataset123",
        task_run_config_id="config456",
        input="What is the capital of France?",
        output="The capital of France is Paris.",
        scores={"accuracy": 1.0},
    )

    assert eval_run.input == "What is the capital of France?"
    assert eval_run.output == "The capital of France is Paris."


def test_eval_run_missing_required_fields():
    """Test that omitting required fields raises ValidationError"""
    with pytest.raises(ValidationError) as exc_info:
        EvalRun(
            dataset_id="dataset123",
            # missing task_run_config_id
            input="test",
            output="test",
            scores={"score": 1.0},
        )

    assert "task_run_config_id" in str(exc_info.value)


def test_eval_run_invalid_scores():
    """Test that scores must be a dict of floats"""
    with pytest.raises(ValidationError):
        EvalRun(
            dataset_id="dataset123",
            task_run_config_id="config456",
            input="test",
            output="test",
            scores={"score": "not a float"},  # invalid score type
        )


def test_eval_missing_output_scores():
    """Test that eval creation fails when output_scores is missing"""
    with pytest.raises(ValidationError) as exc_info:
        Eval(
            name="Test Eval",
            eval_set_filter_id="tag::tag1",
            eval_configs_filter_id="tag::tag2",
        )
    assert "output_scores" in str(exc_info.value)


def test_eval_empty_output_scores():
    """Test that eval creation fails when output_scores is empty"""
    with pytest.raises(
        ValueError, match="output_scores are required, and must have at least one score"
    ):
        Eval(
            name="Test Eval",
            eval_set_filter_id="tag::tag1",
            eval_configs_filter_id="tag::tag2",
            output_scores=[],
        )


def test_eval_duplicate_output_scores():
    """Test that eval creation fails when output_scores has duplicate names"""
    with pytest.raises(
        ValueError,
        match="must have unique names",
    ):
        Eval(
            name="Test Eval",
            eval_set_filter_id="tag::tag1",
            eval_configs_filter_id="tag::tag2",
            output_scores=[
                EvalOutputScore(
                    name="score",
                    type=TaskOutputRatingType.five_star,
                ),
                EvalOutputScore(name="SCORE", type=TaskOutputRatingType.pass_fail),
            ],
        )


def test_eval_invalid_score_type():
    """Test that eval creation fails with invalid rating type in output_scores"""
    with pytest.raises(
        ValueError,
        match="Input should be 'five_star', 'pass_fail', 'pass_fail_critical'",
    ):
        Eval(
            name="Test Eval",
            eval_set_filter_id="tag::tag1",
            eval_configs_filter_id="tag::tag2",
            output_scores=[
                EvalOutputScore(
                    name="score",
                    type="invalid_type",
                )
            ],
        )


def test_eval_valid_output_scores():
    """Test that eval creation succeeds with valid output_scores"""
    eval = Eval(
        name="Test Eval",
        eval_set_filter_id="tag::tag1",
        eval_configs_filter_id="tag::tag2",
        output_scores=[
            EvalOutputScore(
                name="accuracy",
                type=TaskOutputRatingType.five_star,
            ),
            EvalOutputScore(
                name="critical_check",
                type=TaskOutputRatingType.pass_fail_critical,
            ),
            EvalOutputScore(name="basic_check", type=TaskOutputRatingType.pass_fail),
        ],
    )
    assert len(eval.output_scores) == 3
    assert eval.output_scores[0].type == TaskOutputRatingType.five_star
    assert eval.output_scores[0].name == "accuracy"
    assert eval.output_scores[1].type == TaskOutputRatingType.pass_fail_critical
    assert eval.output_scores[1].name == "critical_check"
    assert eval.output_scores[2].type == TaskOutputRatingType.pass_fail
    assert eval.output_scores[2].name == "basic_check"


@pytest.fixture
def valid_eval_run_data():
    return {
        "dataset_id": "dataset123",
        "task_run_config_id": "config456",
        "input": "test input",
        "output": "test output",
        "scores": {"accuracy": 4.5},
    }


def test_eval_run_five_star_score_validation(valid_eval_config, valid_eval_run_data):
    # Setup eval with five_star rating
    eval = Eval(
        name="Test Eval",
        eval_set_filter_id="tag::tag1",
        eval_configs_filter_id="tag::tag2",
        output_scores=[
            EvalOutputScore(
                name="accuracy",
                type=TaskOutputRatingType.five_star,
            )
        ],
    )
    valid_eval_config.parent = eval

    # Valid score
    run = EvalRun(parent=valid_eval_config, **valid_eval_run_data)
    assert run.scores["accuracy"] == 4.5

    # Invalid scores
    with pytest.raises(ValueError, match="must be a float between 1.0 and 5.0"):
        run = EvalRun(
            parent=valid_eval_config,
            **{**valid_eval_run_data, "scores": {"accuracy": 0.5}},
        )

    with pytest.raises(ValueError, match="must be a float between 1.0 and 5.0"):
        run = EvalRun(
            parent=valid_eval_config,
            **{**valid_eval_run_data, "scores": {"accuracy": 5.5}},
        )


def test_eval_run_pass_fail_score_validation(valid_eval_config, valid_eval_run_data):
    # Setup eval with pass_fail rating
    eval = Eval(
        name="Test Eval",
        eval_set_filter_id="tag::tag1",
        eval_configs_filter_id="tag::tag2",
        output_scores=[
            EvalOutputScore(
                name="check",
                type=TaskOutputRatingType.pass_fail,
            )
        ],
    )
    valid_eval_config.parent = eval

    # Valid scores
    run = EvalRun(
        parent=valid_eval_config, **{**valid_eval_run_data, "scores": {"check": 1.0}}
    )
    assert run.scores["check"] == 1.0

    run = EvalRun(
        parent=valid_eval_config, **{**valid_eval_run_data, "scores": {"check": 0.0}}
    )
    assert run.scores["check"] == 0.0

    # Invalid scores
    with pytest.raises(ValueError, match="must be a float between 0.0 and 1.0"):
        run = EvalRun(
            parent=valid_eval_config,
            **{**valid_eval_run_data, "scores": {"check": -0.1}},
        )

    with pytest.raises(ValueError, match="must be a float between 0.0 and 1.0"):
        run = EvalRun(
            parent=valid_eval_config,
            **{**valid_eval_run_data, "scores": {"check": 1.1}},
        )


def test_eval_run_pass_fail_critical_score_validation(
    valid_eval_config, valid_eval_run_data
):
    # Setup eval with pass_fail_critical rating
    eval = Eval(
        name="Test Eval",
        eval_set_filter_id="tag::tag1",
        eval_configs_filter_id="tag::tag2",
        output_scores=[
            EvalOutputScore(
                name="critical",
                type=TaskOutputRatingType.pass_fail_critical,
            )
        ],
    )
    valid_eval_config.parent = eval

    # Valid scores
    run = EvalRun(
        parent=valid_eval_config, **{**valid_eval_run_data, "scores": {"critical": 1.0}}
    )
    assert run.scores["critical"] == 1.0

    run = EvalRun(
        parent=valid_eval_config,
        **{**valid_eval_run_data, "scores": {"critical": -1.0}},
    )
    assert run.scores["critical"] == -1.0

    # Invalid scores
    with pytest.raises(ValueError, match="must be a float between -1.0 and 1.0"):
        run = EvalRun(
            parent=valid_eval_config,
            **{**valid_eval_run_data, "scores": {"critical": -1.1}},
        )

    with pytest.raises(ValueError, match="must be a float between -1.0 and 1.0"):
        run = EvalRun(
            parent=valid_eval_config,
            **{**valid_eval_run_data, "scores": {"critical": 1.1}},
        )


def test_eval_run_score_keys_must_match(valid_eval_config, valid_eval_run_data):
    eval = Eval(
        name="Test Eval",
        eval_set_filter_id="tag::tag1",
        eval_configs_filter_id="tag::tag2",
        output_scores=[
            EvalOutputScore(
                name="accuracy",
                type=TaskOutputRatingType.five_star,
            ),
            EvalOutputScore(
                name="critical",
                type=TaskOutputRatingType.pass_fail_critical,
            ),
        ],
    )
    valid_eval_config.parent = eval

    # Correct
    run = EvalRun(
        parent=valid_eval_config,
        **{**valid_eval_run_data, "scores": {"accuracy": 4.5, "critical": 1.0}},
    )

    # Correct but wrong order still okay
    run = EvalRun(
        parent=valid_eval_config,
        **{**valid_eval_run_data, "scores": {"critical": 1.0, "accuracy": 4.5}},
    )

    # Missing score
    with pytest.raises(
        ValueError,
        match="The scores produced by the evaluator must match the scores expected by the eval",
    ):
        run = EvalRun(
            parent=valid_eval_config,
            **{**valid_eval_run_data, "scores": {"accuracy": 4.5}},
        )

    # Extra score
    with pytest.raises(
        ValueError,
        match="The scores produced by the evaluator must match the scores expected by the eval",
    ):
        run = EvalRun(
            parent=valid_eval_config,
            **{
                **valid_eval_run_data,
                "scores": {"accuracy": 4.5, "critical": 1.0, "extra": 1.0},
            },
        )

    # Missing score w matching count
    with pytest.raises(
        ValueError,
        match="The scores produced by the evaluator must match the scores expected by the eval",
    ):
        run = EvalRun(
            parent=valid_eval_config,
            **{**valid_eval_run_data, "scores": {"accuracy": 4.5, "wrong": 1.0}},
        )


def test_eval_run_custom_scores_not_allowed(valid_eval_config, valid_eval_run_data):
    with pytest.raises(
        ValueError, match="Custom scores are not supported in evaluators"
    ):
        eval = Eval(
            name="Test Eval",
            eval_set_filter_id="tag::tag1",
            eval_configs_filter_id="tag::tag2",
            output_scores=[
                EvalOutputScore(
                    name="custom",
                    type=TaskOutputRatingType.custom,
                )
            ],
        )
