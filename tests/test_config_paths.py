from pathlib import Path

from mtg_rebuilder.config import (
    ENV_DATA_DIR,
    LEGACY_APP_DATA_DIRNAME,
    LEGACY_DATABASE_FILENAME,
    LEGACY_ENV_DATA_DIR,
    alembic_script_location,
    default_user_data_dir,
    is_frozen,
    migrate_legacy_database,
    migrate_legacy_user_data_dir,
    resolve_data_dir,
    resolve_database_path,
    resource_root,
)


def test_resolve_data_dir_env_override(tmp_path: Path) -> None:
    target = tmp_path / "custom-data"
    result = resolve_data_dir(
        environ={ENV_DATA_DIR: str(target)},
        frozen=True,
        project_root=tmp_path / "project",
    )
    assert result == target


def test_resolve_data_dir_legacy_env_override(tmp_path: Path) -> None:
    target = tmp_path / "legacy-custom"
    result = resolve_data_dir(
        environ={LEGACY_ENV_DATA_DIR: str(target)},
        frozen=True,
        project_root=tmp_path / "project",
    )
    assert result == target


def test_resolve_data_dir_new_env_beats_legacy(tmp_path: Path) -> None:
    newer = tmp_path / "new"
    older = tmp_path / "old"
    result = resolve_data_dir(
        environ={
            ENV_DATA_DIR: str(newer),
            LEGACY_ENV_DATA_DIR: str(older),
        },
        frozen=True,
        project_root=tmp_path / "project",
    )
    assert result == newer


def test_resolve_data_dir_env_override_beats_dev_project_data(tmp_path: Path) -> None:
    target = tmp_path / "override"
    result = resolve_data_dir(
        environ={ENV_DATA_DIR: str(target)},
        frozen=False,
        project_root=tmp_path / "project",
    )
    assert result == target


def test_resolve_data_dir_ignores_blank_env_override(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    result = resolve_data_dir(
        environ={ENV_DATA_DIR: "   "},
        frozen=False,
        project_root=project,
    )
    assert result == project / "data"


def test_resolve_data_dir_dev_uses_project_data(tmp_path: Path) -> None:
    project = tmp_path / "MTG-Rebuilder"
    result = resolve_data_dir(environ={}, frozen=False, project_root=project)
    assert result == project / "data"


def test_resolve_data_dir_frozen_linux_xdg(tmp_path: Path) -> None:
    xdg = tmp_path / "xdg-data"
    home = tmp_path / "home"
    result = resolve_data_dir(
        environ={"XDG_DATA_HOME": str(xdg)},
        frozen=True,
        home=home,
        platform="linux",
    )
    assert result == xdg / "mtg-rebuilder"


def test_resolve_data_dir_frozen_linux_default_home(tmp_path: Path) -> None:
    home = tmp_path / "home"
    result = resolve_data_dir(
        environ={},
        frozen=True,
        home=home,
        platform="linux",
    )
    assert result == home / ".local" / "share" / "mtg-rebuilder"


def test_resolve_data_dir_frozen_windows_localappdata(tmp_path: Path) -> None:
    local = tmp_path / "Local"
    result = resolve_data_dir(
        environ={"LOCALAPPDATA": str(local)},
        frozen=True,
        home=tmp_path / "home",
        platform="win32",
    )
    assert result == local / "mtg-rebuilder"


def test_resolve_data_dir_frozen_macos(tmp_path: Path) -> None:
    home = tmp_path / "home"
    result = resolve_data_dir(
        environ={},
        frozen=True,
        home=home,
        platform="darwin",
    )
    assert result == home / "Library" / "Application Support" / "mtg-rebuilder"


def test_default_user_data_dir_windows_without_localappdata(tmp_path: Path) -> None:
    home = tmp_path / "home"
    result = default_user_data_dir(environ={}, home=home, platform="win32")
    assert result == home / "AppData" / "Local" / "mtg-rebuilder"


def test_migrate_legacy_user_data_dir_renames_once(tmp_path: Path) -> None:
    legacy = tmp_path / LEGACY_APP_DATA_DIRNAME
    target = tmp_path / "mtg-rebuilder"
    (legacy / "images").mkdir(parents=True)
    (legacy / LEGACY_DATABASE_FILENAME).write_text("db", encoding="utf-8")
    result = migrate_legacy_user_data_dir(target, legacy)
    assert result == target
    assert target.is_dir()
    assert not legacy.exists()
    assert (target / LEGACY_DATABASE_FILENAME).is_file()


def test_migrate_legacy_user_data_dir_keeps_target_if_present(tmp_path: Path) -> None:
    legacy = tmp_path / LEGACY_APP_DATA_DIRNAME
    target = tmp_path / "mtg-rebuilder"
    legacy.mkdir()
    (legacy / "old.txt").write_text("old", encoding="utf-8")
    target.mkdir()
    (target / "new.txt").write_text("new", encoding="utf-8")
    result = migrate_legacy_user_data_dir(target, legacy)
    assert result == target
    assert legacy.exists()
    assert (target / "new.txt").is_file()


def test_resolve_data_dir_frozen_migrates_legacy_xdg(tmp_path: Path) -> None:
    xdg = tmp_path / "xdg-data"
    legacy = xdg / LEGACY_APP_DATA_DIRNAME
    legacy.mkdir(parents=True)
    (legacy / "marker").write_text("ok", encoding="utf-8")
    result = resolve_data_dir(
        environ={"XDG_DATA_HOME": str(xdg)},
        frozen=True,
        home=tmp_path / "home",
        platform="linux",
    )
    assert result == xdg / "mtg-rebuilder"
    assert (result / "marker").read_text(encoding="utf-8") == "ok"
    assert not legacy.exists()


def test_migrate_legacy_database_renames_file(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    legacy = data / LEGACY_DATABASE_FILENAME
    legacy.write_text("sqlite", encoding="utf-8")
    result = migrate_legacy_database(data)
    assert result == data / "mtg_rebuilder.db"
    assert result.read_text(encoding="utf-8") == "sqlite"
    assert not legacy.exists()


def test_resolve_database_path_migrates_legacy(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    (data / LEGACY_DATABASE_FILENAME).write_text("x", encoding="utf-8")
    path = resolve_database_path(data)
    assert path == data / "mtg_rebuilder.db"
    assert path.is_file()


def test_is_frozen_false_in_dev() -> None:
    assert is_frozen() is False


def test_resource_root_dev_is_package_dir() -> None:
    root = resource_root(frozen=False)
    assert root.name == "mtg_rebuilder"
    assert (root / "database" / "alembic" / "env.py").is_file()


def test_alembic_script_location_dev() -> None:
    location = alembic_script_location(frozen=False)
    assert location.name == "alembic"
    assert (location / "versions").is_dir()
    assert (location / "env.py").is_file()


def test_alembic_script_location_frozen_uses_meipass(tmp_path: Path) -> None:
    meipass = tmp_path / "_MEIPASS"
    bundled = meipass / "mtg_rebuilder" / "database" / "alembic" / "versions"
    bundled.mkdir(parents=True)
    location = alembic_script_location(frozen=True, meipass=meipass)
    assert location == meipass / "mtg_rebuilder" / "database" / "alembic"


def test_resource_root_frozen_uses_meipass(tmp_path: Path) -> None:
    meipass = tmp_path / "_MEIPASS"
    assert resource_root(frozen=True, meipass=meipass) == meipass
