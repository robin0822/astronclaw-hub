def test_team_execution_table_matches_delivery_schema():
    import app.models  # noqa: F401
    from app.db import Base

    table = Base.metadata.tables["agent_team_executions"]

    assert {
        "id",
        "team_id",
        "execution_id",
        "task_name",
        "status",
        "output_paths",
        "created_at",
        "updated_at",
    } <= set(table.columns.keys())


def test_channel_audit_log_table_matches_delivery_schema():
    import app.models  # noqa: F401
    from app.db import Base

    table = Base.metadata.tables["channel_audit_logs"]

    assert {
        "id",
        "channel_id",
        "module",
        "action",
        "object_type",
        "object_id",
        "actor_id",
        "result",
        "detail",
        "created_at",
    } <= set(table.columns.keys())


def test_message_channel_table_reserves_rate_limit_fields():
    import app.models  # noqa: F401
    from app.db import Base

    table = Base.metadata.tables["message_channels"]

    assert {
        "user_rate_limit_per_minute",
        "qps_limit",
        "daily_message_limit",
    } <= set(table.columns.keys())


def test_fix_task_table_matches_delivery_schema():
    import app.models  # noqa: F401
    from app.db import Base

    table = Base.metadata.tables["fix_tasks"]

    assert {
        "id",
        "diagnosis_id",
        "self_heal_task_id",
        "task_type",
        "target_type",
        "target_id",
        "status",
        "result",
        "operator_id",
        "started_at",
        "ended_at",
        "created_at",
    } <= set(table.columns.keys())


def test_llm_model_table_covers_ledger_fields():
    import app.models  # noqa: F401
    from app.db import Base

    table = Base.metadata.tables["llm_models"]

    assert {
        "applicable_scenarios",
        "error_rate",
    } <= set(table.columns.keys())


def test_model_call_log_table_supports_project_cost_dimension():
    import app.models  # noqa: F401
    from app.db import Base

    table = Base.metadata.tables["model_call_logs"]

    assert "project_id" in table.columns.keys()
