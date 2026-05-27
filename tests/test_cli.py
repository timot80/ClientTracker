from ap_radio_monitor import __version__
from ap_radio_monitor.cli import main, parse_args


def test_version_import_is_available():
    assert __version__ == "0.1.0"


def test_parse_args_supports_monitor_options():
    args = parse_args(["--config", "lab.yaml", "--refresh", "15", "--once", "--only-imbalanced"])

    assert args.config == "lab.yaml"
    assert args.refresh == 15
    assert args.once is True
    assert args.only_imbalanced is True


def test_main_returns_clean_error_for_bad_config(tmp_path, capsys):
    missing = tmp_path / "missing.yaml"

    exit_code = main(["--config", str(missing), "--once"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Config file not found" in captured.err
