from ap_radio_monitor import __version__
from ap_radio_monitor.cli import parse_args


def test_version_import_is_available():
    assert __version__ == "0.1.0"


def test_parse_args_supports_monitor_options():
    args = parse_args(["--config", "lab.yaml", "--refresh", "15", "--once", "--only-imbalanced"])

    assert args.config == "lab.yaml"
    assert args.refresh == 15
    assert args.once is True
    assert args.only_imbalanced is True
