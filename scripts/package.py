"""Package RssHub lite without local, reference or runtime data."""

import argparse
import re
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
NAME = "astrbot_plugin_rsshub_lite"
DIRECTORIES = ("src", "pages", "assets", "docs", "scripts")
FILES = (
    "main.py",
    "bootstrap.py",
    "metadata.yaml",
    "_conf_schema.json",
    "requirements.txt",
    "README.md",
    "CHANGELOG.md",
    "NOTICE.md",
    "LICENSE",
    "logo.png",
    "UPSTREAM.json",
)


def release_version() -> str:
    """Read the release identity from metadata without third-party dependencies."""
    metadata = (ROOT / "metadata.yaml").read_text(encoding="utf-8-sig")
    name = re.search(r"^name:\s*(\S+)\s*$", metadata, re.MULTILINE)
    version = re.search(r"^version:\s*v(\d+\.\d+\.\d+)\s*$", metadata, re.MULTILINE)
    if name is None or name.group(1) != NAME or version is None:
        raise ValueError(
            "metadata.yaml must declare astrbot_plugin_rsshub_lite and a vX.Y.Z release"
        )
    return version.group(1)


def main():
    parser = argparse.ArgumentParser(description="Package RssHub lite")
    parser.add_argument(
        "--expected-tag", help="Require the metadata version to match this Git tag"
    )
    args = parser.parse_args()
    version = release_version()
    if args.expected_tag is not None and args.expected_tag != f"v{version}":
        parser.error(
            f"tag {args.expected_tag!r} does not match metadata version v{version}"
        )
    sources = [ROOT / name for name in FILES]
    for name in DIRECTORIES:
        sources.extend(
            path
            for path in (ROOT / name).rglob("*")
            if path.is_file()
            and "__pycache__" not in path.parts
            and path.suffix not in {".pyc", ".db", ".log"}
        )
    for path in sources:
        if not path.is_file():
            raise FileNotFoundError(path)
        if path.suffix == ".py":
            compile(path.read_text(encoding="utf-8-sig"), str(path), "exec")
    size = sum(path.stat().st_size for path in sources)
    if size > 16 * 1024 * 1024:
        raise RuntimeError("Plugin contents exceed the upstream 16 MiB size limit")
    destination = ROOT / "dist" / f"{NAME}-{version}.zip"
    destination.parent.mkdir(exist_ok=True)
    with ZipFile(destination, "w", ZIP_DEFLATED) as archive:
        for path in sorted(sources):
            archive.write(path, f"{NAME}/{path.relative_to(ROOT).as_posix()}")
    with ZipFile(destination) as archive:
        assert archive.testzip() is None
        assert len(archive.namelist()) == len(sources)
    print(f"{destination}: {len(sources)} files, {size} uncompressed bytes")


if __name__ == "__main__":
    main()
