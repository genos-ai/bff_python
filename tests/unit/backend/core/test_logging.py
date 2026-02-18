"""
Unit Tests for Centralized Logging.

Tests the logging configuration and source-based routing.
"""

import logging
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestLogSources:
    """Tests for LOG_SOURCES constant."""

    def test_log_sources_contains_expected_values(self):
        """Should contain all expected log sources."""
        from modules.backend.core.logging import LOG_SOURCES

        expected = {"web", "cli", "mobile", "telegram", "api", "database", "tasks", "internal", "unknown"}
        assert LOG_SOURCES == expected

    def test_log_sources_is_set(self):
        """Should be a set for O(1) lookup."""
        from modules.backend.core.logging import LOG_SOURCES

        assert isinstance(LOG_SOURCES, set)


class TestLoggingConfigLoading:
    """Tests for logging configuration loading from YAML."""

    def test_load_logging_config_reads_yaml_file(self, tmp_path):
        """Should load configuration from logging.yaml."""
        from modules.backend.core import logging as logging_module

        # Create a temporary config structure
        config_dir = tmp_path / "config" / "settings"
        config_dir.mkdir(parents=True)

        logging_yaml = config_dir / "logging.yaml"
        logging_yaml.write_text("""
level: "DEBUG"
format: "console"
handlers:
  console:
    enabled: true
  file:
    enabled: false
    max_bytes: 5242880
    backup_count: 3
""")

        # Create .project_root marker
        (tmp_path / ".project_root").touch()

        # Reset the cached config
        logging_module._logging_config = None

        with patch("modules.backend.core.logging.find_project_root", return_value=tmp_path):
            config = logging_module._load_logging_config()

            assert config["level"] == "DEBUG"
            assert config["format"] == "console"
            assert config["handlers"]["console"]["enabled"] is True
            assert config["handlers"]["file"]["enabled"] is False
            assert config["handlers"]["file"]["max_bytes"] == 5242880
            assert config["handlers"]["file"]["backup_count"] == 3

        # Reset for other tests
        logging_module._logging_config = None

    def test_load_logging_config_raises_if_file_missing(self, tmp_path):
        """Should raise FileNotFoundError if logging.yaml doesn't exist."""
        from modules.backend.core import logging as logging_module

        # Create .project_root marker but no config file
        (tmp_path / ".project_root").touch()
        (tmp_path / "config" / "settings").mkdir(parents=True)

        # Reset the cached config
        logging_module._logging_config = None

        with patch("modules.backend.core.logging.find_project_root", return_value=tmp_path):
            with pytest.raises(FileNotFoundError) as exc_info:
                logging_module._load_logging_config()

            assert "logging.yaml" in str(exc_info.value)

        # Reset for other tests
        logging_module._logging_config = None

    def test_config_is_cached(self, tmp_path):
        """Should cache the configuration after first load."""
        from modules.backend.core import logging as logging_module

        # Create a temporary config structure
        config_dir = tmp_path / "config" / "settings"
        config_dir.mkdir(parents=True)

        logging_yaml = config_dir / "logging.yaml"
        logging_yaml.write_text('level: "INFO"\nformat: "json"')

        # Create .project_root marker
        (tmp_path / ".project_root").touch()

        # Reset the cached config
        logging_module._logging_config = None

        with patch("modules.backend.core.logging.find_project_root", return_value=tmp_path):
            config1 = logging_module._load_logging_config()
            config2 = logging_module._get_logging_config()

            # Should be the same object (cached)
            assert config1 is config2

        # Reset for other tests
        logging_module._logging_config = None


class TestSourceRoutingHandler:
    """Tests for SourceRoutingHandler."""

    @pytest.fixture
    def mock_formatter(self):
        """Create a mock formatter."""
        formatter = MagicMock()
        formatter.format = MagicMock(return_value='{"message": "test"}')
        return formatter

    @pytest.fixture
    def mock_logging_config(self):
        """Create a mock logging configuration."""
        return {
            "level": "INFO",
            "format": "json",
            "handlers": {
                "console": {"enabled": True},
                "file": {
                    "enabled": True,
                    "max_bytes": 10485760,
                    "backup_count": 5,
                },
            },
        }

    @pytest.fixture
    def temp_logs_dir(self, tmp_path):
        """Create a temporary logs directory."""
        logs_dir = tmp_path / "data" / "logs"
        logs_dir.mkdir(parents=True)
        return logs_dir

    def test_determines_source_from_explicit_source_field(self, mock_formatter, temp_logs_dir, mock_logging_config):
        """Should use explicit source field when present."""
        from modules.backend.core.logging import SourceRoutingHandler

        with patch("modules.backend.core.logging._get_logs_dir", return_value=temp_logs_dir), \
             patch("modules.backend.core.logging._get_logging_config", return_value=mock_logging_config):
            handler = SourceRoutingHandler(mock_formatter)

            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg="test message",
                args=(),
                exc_info=None,
            )
            record.source = "web"

            source = handler._determine_source(record)
            assert source == "web"

    def test_determines_source_from_frontend_field(self, mock_formatter, temp_logs_dir, mock_logging_config):
        """Should use frontend field when source not present."""
        from modules.backend.core.logging import SourceRoutingHandler

        with patch("modules.backend.core.logging._get_logs_dir", return_value=temp_logs_dir), \
             patch("modules.backend.core.logging._get_logging_config", return_value=mock_logging_config):
            handler = SourceRoutingHandler(mock_formatter)

            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg="test message",
                args=(),
                exc_info=None,
            )
            record.frontend = "cli"

            source = handler._determine_source(record)
            assert source == "cli"

    def test_determines_source_from_logger_name_tasks(self, mock_formatter, temp_logs_dir, mock_logging_config):
        """Should detect tasks source from logger name."""
        from modules.backend.core.logging import SourceRoutingHandler

        with patch("modules.backend.core.logging._get_logs_dir", return_value=temp_logs_dir), \
             patch("modules.backend.core.logging._get_logging_config", return_value=mock_logging_config):
            handler = SourceRoutingHandler(mock_formatter)

            record = logging.LogRecord(
                name="modules.backend.tasks.example",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg="test message",
                args=(),
                exc_info=None,
            )

            source = handler._determine_source(record)
            assert source == "tasks"

    def test_determines_source_from_logger_name_database(self, mock_formatter, temp_logs_dir, mock_logging_config):
        """Should detect database source from logger name."""
        from modules.backend.core.logging import SourceRoutingHandler

        with patch("modules.backend.core.logging._get_logs_dir", return_value=temp_logs_dir), \
             patch("modules.backend.core.logging._get_logging_config", return_value=mock_logging_config):
            handler = SourceRoutingHandler(mock_formatter)

            record = logging.LogRecord(
                name="modules.backend.core.database",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg="test message",
                args=(),
                exc_info=None,
            )

            source = handler._determine_source(record)
            assert source == "database"

    def test_determines_source_from_logger_name_telegram(self, mock_formatter, temp_logs_dir, mock_logging_config):
        """Should detect telegram source from logger name."""
        from modules.backend.core.logging import SourceRoutingHandler

        with patch("modules.backend.core.logging._get_logs_dir", return_value=temp_logs_dir), \
             patch("modules.backend.core.logging._get_logging_config", return_value=mock_logging_config):
            handler = SourceRoutingHandler(mock_formatter)

            record = logging.LogRecord(
                name="modules.telegram.bot",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg="test message",
                args=(),
                exc_info=None,
            )

            source = handler._determine_source(record)
            assert source == "telegram"

    def test_defaults_to_unknown_source(self, mock_formatter, temp_logs_dir, mock_logging_config):
        """Should default to unknown when no source can be determined."""
        from modules.backend.core.logging import SourceRoutingHandler

        with patch("modules.backend.core.logging._get_logs_dir", return_value=temp_logs_dir), \
             patch("modules.backend.core.logging._get_logging_config", return_value=mock_logging_config):
            handler = SourceRoutingHandler(mock_formatter)

            record = logging.LogRecord(
                name="some.random.module",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg="test message",
                args=(),
                exc_info=None,
            )

            source = handler._determine_source(record)
            assert source == "unknown"

    def test_explicit_source_takes_priority_over_frontend(self, mock_formatter, temp_logs_dir, mock_logging_config):
        """Explicit source should take priority over frontend field."""
        from modules.backend.core.logging import SourceRoutingHandler

        with patch("modules.backend.core.logging._get_logs_dir", return_value=temp_logs_dir), \
             patch("modules.backend.core.logging._get_logging_config", return_value=mock_logging_config):
            handler = SourceRoutingHandler(mock_formatter)

            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg="test message",
                args=(),
                exc_info=None,
            )
            record.source = "api"
            record.frontend = "web"

            source = handler._determine_source(record)
            assert source == "api"

    def test_ignores_invalid_source_values(self, mock_formatter, temp_logs_dir, mock_logging_config):
        """Should ignore invalid source values and fall back."""
        from modules.backend.core.logging import SourceRoutingHandler

        with patch("modules.backend.core.logging._get_logs_dir", return_value=temp_logs_dir), \
             patch("modules.backend.core.logging._get_logging_config", return_value=mock_logging_config):
            handler = SourceRoutingHandler(mock_formatter)

            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg="test message",
                args=(),
                exc_info=None,
            )
            record.source = "invalid_source"

            source = handler._determine_source(record)
            assert source == "unknown"


class TestSetupLogging:
    """Tests for setup_logging function."""

    @pytest.fixture
    def mock_logging_config(self):
        """Create a mock logging configuration."""
        return {
            "level": "INFO",
            "format": "json",
            "handlers": {
                "console": {"enabled": True},
                "file": {
                    "enabled": True,
                    "max_bytes": 10485760,
                    "backup_count": 5,
                },
            },
        }

    def test_setup_logging_configures_root_logger(self, tmp_path, mock_logging_config):
        """Should configure the root logger with correct level."""
        from modules.backend.core.logging import setup_logging

        logs_dir = tmp_path / "data" / "logs"
        logs_dir.mkdir(parents=True)

        with patch("modules.backend.core.logging._get_logs_dir", return_value=logs_dir), \
             patch("modules.backend.core.logging._get_logging_config", return_value=mock_logging_config):
            setup_logging(level="DEBUG", format_type="json", enable_file_logging=False)

            root_logger = logging.getLogger()
            assert root_logger.level == logging.DEBUG

    def test_setup_logging_with_file_logging_disabled(self, mock_logging_config):
        """Should work without file logging."""
        from modules.backend.core.logging import setup_logging

        with patch("modules.backend.core.logging._get_logging_config", return_value=mock_logging_config):
            # Should not raise even without file logging
            setup_logging(level="INFO", format_type="console", enable_file_logging=False)

            root_logger = logging.getLogger()
            # Should only have console handler
            handler_types = [type(h).__name__ for h in root_logger.handlers]
            assert "StreamHandler" in handler_types

    def test_setup_logging_uses_config_defaults(self, tmp_path, mock_logging_config):
        """Should use values from logging.yaml when not overridden."""
        from modules.backend.core.logging import setup_logging

        logs_dir = tmp_path / "data" / "logs"
        logs_dir.mkdir(parents=True)

        # Config has level="INFO" and format="json"
        with patch("modules.backend.core.logging._get_logs_dir", return_value=logs_dir), \
             patch("modules.backend.core.logging._get_logging_config", return_value=mock_logging_config):
            setup_logging(enable_file_logging=False)

            root_logger = logging.getLogger()
            assert root_logger.level == logging.INFO

    def test_setup_logging_override_takes_precedence(self, tmp_path, mock_logging_config):
        """Explicit parameters should override config values."""
        from modules.backend.core.logging import setup_logging

        logs_dir = tmp_path / "data" / "logs"
        logs_dir.mkdir(parents=True)

        # Config has level="INFO" but we override with DEBUG
        with patch("modules.backend.core.logging._get_logs_dir", return_value=logs_dir), \
             patch("modules.backend.core.logging._get_logging_config", return_value=mock_logging_config):
            setup_logging(level="DEBUG", enable_file_logging=False)

            root_logger = logging.getLogger()
            assert root_logger.level == logging.DEBUG


class TestGetLogger:
    """Tests for get_logger function."""

    def test_get_logger_returns_structlog_logger(self):
        """Should return a structlog logger."""
        from modules.backend.core.logging import get_logger

        logger = get_logger("test.module")
        # structlog loggers have bind method
        assert hasattr(logger, "bind")
        assert hasattr(logger, "info")
        assert hasattr(logger, "error")


class TestLogWithSource:
    """Tests for log_with_source helper function."""

    def test_log_with_source_adds_source_field(self):
        """Should add source field to log call."""
        from modules.backend.core.logging import get_logger, log_with_source

        logger = get_logger("test")
        mock_info = MagicMock()

        with patch.object(logger, "info", mock_info):
            log_with_source(logger, "database", "info", "Test message", extra_field="value")

            mock_info.assert_called_once_with(
                "Test message",
                source="database",
                extra_field="value",
            )

    def test_log_with_source_supports_different_levels(self):
        """Should support different log levels."""
        from modules.backend.core.logging import get_logger, log_with_source

        logger = get_logger("test")

        for level in ["debug", "info", "warning", "error", "critical"]:
            mock_method = MagicMock()
            with patch.object(logger, level, mock_method):
                log_with_source(logger, "web", level, f"Test {level}")
                mock_method.assert_called_once()
