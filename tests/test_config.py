from meshtastic_llm_bridge.config import Settings


def test_settings_parsing_lists_and_log_level() -> None:
    settings = Settings(
        _env_file=None,
        allowed_channels="1, 2",
        allowed_senders="!abcd1234, 9876",
        log_level="debug",
    )

    assert settings.allowed_channels == [1, 2]
    assert settings.allowed_senders == ["!abcd1234", "9876"]
    assert settings.log_level == "DEBUG"
