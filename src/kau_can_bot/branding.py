from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path


SUPPORTED_LOGO_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".svg"}


@dataclass(frozen=True)
class BrandingState:
    logo_url: str | None = None
    logo_path: Path | None = None
    source_path: Path | None = None


def prepare_branding_assets(
    root_dir: Path,
    desktop_dir: Path | None = None,
) -> BrandingState:
    static_dir = root_dir / "static"
    assets_dir = static_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    existing_asset = _find_existing_logo(assets_dir)
    if existing_asset:
        return _branding_state(static_dir, existing_asset)

    desktop_path = desktop_dir or Path.home() / "Desktop"
    source_logo = _find_desktop_logo(desktop_path)
    if not source_logo:
        return BrandingState()

    target_path = assets_dir / f"kau_logo{source_logo.suffix.lower()}"
    try:
        shutil.copy2(source_logo, target_path)
    except OSError:
        return BrandingState()

    return _branding_state(static_dir, target_path, source_logo)


def _find_existing_logo(assets_dir: Path) -> Path | None:
    for path in sorted(assets_dir.iterdir()) if assets_dir.exists() else []:
        if path.is_file() and path.stem.lower() == "kau_logo":
            if path.suffix.lower() in SUPPORTED_LOGO_EXTENSIONS:
                return path
    return None


def _find_desktop_logo(desktop_dir: Path) -> Path | None:
    if not desktop_dir.exists():
        return None

    for path in sorted(desktop_dir.iterdir()):
        if not path.is_file():
            continue
        if path.suffix.lower() not in SUPPORTED_LOGO_EXTENSIONS:
            continue
        if path.stem.lower() == "kau_logo":
            return path
    return None


def _branding_state(
    static_dir: Path,
    logo_path: Path,
    source_path: Path | None = None,
) -> BrandingState:
    relative_logo = logo_path.relative_to(static_dir).as_posix()
    return BrandingState(
        logo_url=f"/static/{relative_logo}",
        logo_path=logo_path,
        source_path=source_path,
    )
