from app.config import Settings
from app.clients.tracing import Tracer


def test_arize_enabled_without_credentials_disables_tracing(capsys) -> None:
    settings = Settings(
        _env_file=None,
        arize_enabled=True,
        arize_space_id=None,
        arize_api_key=None,
        phoenix_enabled=False,
    )

    tracer = Tracer(settings)

    assert tracer.enabled is False
    captured = capsys.readouterr().out
    assert "arize enabled=true" in captured
    assert "space_id_configured=False" in captured
    assert "api_key_configured=False" in captured
    assert "ARIZE_SPACE_ID and ARIZE_API_KEY are required" in captured
