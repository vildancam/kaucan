from __future__ import annotations

import shutil
import unicodedata
from dataclasses import dataclass
from pathlib import Path


SUPPORTED_LOGO_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".svg"}


@dataclass(frozen=True)
class BrandingState:
    logo_url: str | None = None
    chat_logo_url: str | None = None
    logo_path: Path | None = None
    chat_logo_path: Path | None = None


def prepare_branding_assets(
    root_dir: Path,
    desktop_dir: Path | None = None,
) -> BrandingState:
    static_dir = root_dir / "static"
    assets_dir = static_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    desktop_path = desktop_dir or Path.home() / "Desktop"

    header_logo_path = _ensure_logo_asset(
        assets_dir=assets_dir,
        desktop_dir=desktop_path,
        asset_stem="kau_logo",
        desktop_targets={"kau_logo"},
    )
    chat_logo_path = _ensure_logo_asset(
        assets_dir=assets_dir,
        desktop_dir=desktop_path,
        asset_stem="iibf_logo",
        desktop_targets={"iibf_logo"},
    )

    return BrandingState(
        logo_url=_to_static_url(static_dir, header_logo_path),
        chat_logo_url=_to_static_url(static_dir, chat_logo_path),
        logo_path=header_logo_path,
        chat_logo_path=chat_logo_path,
    )


def _ensure_logo_asset(
    assets_dir: Path,
    desktop_dir: Path,
    asset_stem: str,
    desktop_targets: set[str],
) -> Path | None:
    existing_asset = _find_asset_logo(assets_dir, asset_stem)
    if existing_asset:
        return existing_asset

    source_logo = _find_desktop_logo(desktop_dir, desktop_targets)
    if not source_logo:
        return None

    target_path = assets_dir / f"{asset_stem}{source_logo.suffix.lower()}"
    try:
        shutil.copy2(source_logo, target_path)
    except OSError:
        return None
    return target_path


def _find_asset_logo(assets_dir: Path, asset_stem: str) -> Path | None:
    if not assets_dir.exists():
        return None

    for path in sorted(assets_dir.iterdir()):
        if not path.is_file():
            continue
        if path.suffix.lower() not in SUPPORTED_LOGO_EXTENSIONS:
            continue
        if _normalized_stem(path) == asset_stem:
            return path
    return None


def _find_desktop_logo(desktop_dir: Path, targets: set[str]) -> Path | None:
    if not desktop_dir.exists():
        return None

    for path in sorted(desktop_dir.iterdir()):
        if not path.is_file():
            continue
        if path.suffix.lower() not in SUPPORTED_LOGO_EXTENSIONS:
            continue
        if _normalized_stem(path) in targets:
            return path
    return None


def _normalized_stem(path: Path) -> str:
    value = unicodedata.normalize("NFKD", path.stem.lower())
    value = "".join(char for char in value if not unicodedata.combining(char))
    return value.replace("ı", "i").replace(" ", "_")


def _to_static_url(static_dir: Path, path: Path | None) -> str | None:
    if path is None:
        return None
    relative_logo = path.relative_to(static_dir).as_posix()
    return f"/static/{relative_logo}"
