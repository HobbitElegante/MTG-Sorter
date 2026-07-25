from pathlib import Path

from mtg_sorter.config import (
    ENV_DATA_DIR,
    alembic_script_location,
    default_user_data_dir,
    is_frozen,
    resolve_data_dir,
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
    project = tmp_path / "MTG-Sorter"
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
    assert result == xdg / "mtg-sorter"


def test_resolve_data_dir_frozen_linux_default_home(tmp_path: Path) -> None:
    home = tmp_path / "home"
    result = resolve_data_dir(
        environ={},
        frozen=True,
        home=home,
        platform="linux",
    )
    assert result == home / ".local" / "share" / "mtg-sorter"


def test_resolve_data_dir_frozen_windows_localappdata(tmp_path: Path) -> None:
    local = tmp_path / "Local"
    result = resolve_data_dir(
        environ={"LOCALAPPDATA": str(local)},
        frozen=True,
        home=tmp_path / "home",
        platform="win32",
    )
    assert result == local / "mtg-sorter"


def test_resolve_data_dir_frozen_macos(tmp_path: Path) -> None:
    home = tmp_path / "home"
    result = resolve_data_dir(
        environ={},
        frozen=True,
        home=home,
        platform="darwin",
    )
    assert result == home / "Library" / "Application Support" / "mtg-sorter"


def test_default_user_data_dir_windows_without_localappdata(tmp_path: Path) -> None:
    home = tmp_path / "home"
    result = default_user_data_dir(environ={}, home=home, platform="win32")
    assert result == home / "AppData" / "Local" / "mtg-sorter"


def test_is_frozen_false_in_dev() -> None:
    assert is_frozen() is False


def test_resource_root_dev_is_package_dir() -> None:
    root = resource_root(frozen=False)
    assert root.name == "mtg_sorter"
    assert (root / "database" / "alembic" / "env.py").is_file()


def test_alembic_script_location_dev() -> None:
    location = alembic_script_location(frozen=False)
    assert location.name == "alembic"
    assert (location / "versions").is_dir()
    assert (location / "env.py").is_file()


def test_alembic_script_location_frozen_uses_meipass(tmp_path: Path) -> None:
    meipass = tmp_path / "_MEIPASS"
    bundled = meipass / "mtg_sorter" / "database" / "alembic" / "versions"
    bundled.mkdir(parents=True)
    location = alembic_script_location(frozen=True, meipass=meipass)
    assert location == meipass / "mtg_sorter" / "database" / "alembic"


def test_resource_root_frozen_uses_meipass(tmp_path: Path) -> None:
    meipass = tmp_path / "_MEIPASS"
    assert resource_root(frozen=True, meipass=meipass) == meipass
