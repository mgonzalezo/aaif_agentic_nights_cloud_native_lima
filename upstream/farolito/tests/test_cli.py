from farolito.cli import main


def test_greets_from_config(tmp_path, capsys):
    cfg = tmp_path / "farolito.toml"
    cfg.write_text('name = "Lima"\n')
    assert main(["--config", str(cfg)]) == 0
    assert "Hello, Lima!" in capsys.readouterr().out


def test_missing_config_is_friendly(tmp_path, capsys):
    missing = tmp_path / "nope.toml"
    assert main(["--config", str(missing)]) == 2
    err = capsys.readouterr().err
    assert err.startswith("farolito: ")
    assert "config file not found" in err
