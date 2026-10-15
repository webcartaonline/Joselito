"""Tests for loading local environment configuration at startup."""

from pathlib import Path

from wiki_enrichment import bootstrap


def _write_bootstrap_at(tmp_root: Path) -> Path:
    module_path = tmp_root / "src" / "wiki_enrichment" / "bootstrap.py"
    module_path.parent.mkdir(parents=True, exist_ok=True)
    module_path.write_text("# bootstrap stub\n", encoding="utf-8")
    return module_path


def test_load_local_env_file_reads_utf8_sig_keys(
    tmp_path: Path, monkeypatch
) -> None:
    module_path = _write_bootstrap_at(tmp_path)
    (tmp_path / ".env").write_text(
        "\ufeffGOOGLE_TRANSLATE_API_KEY=from-dotenv\n", encoding="utf-8"
    )
    monkeypatch.setattr(bootstrap, "__file__", str(module_path))
    monkeypatch.delenv("GOOGLE_TRANSLATE_API_KEY", raising=False)

    bootstrap._load_local_env_file()

    assert bootstrap.os.getenv("GOOGLE_TRANSLATE_API_KEY") == "from-dotenv"


def test_load_local_env_file_does_not_override_existing_values(
    tmp_path: Path, monkeypatch
) -> None:
    module_path = _write_bootstrap_at(tmp_path)
    (tmp_path / ".env").write_text("GOOGLE_TRANSLATE_API_KEY=from-dotenv\n", encoding="utf-8")
    monkeypatch.setattr(bootstrap, "__file__", str(module_path))
    monkeypatch.setenv("GOOGLE_TRANSLATE_API_KEY", "already-set")

    bootstrap._load_local_env_file()

    assert bootstrap.os.getenv("GOOGLE_TRANSLATE_API_KEY") == "already-set"
