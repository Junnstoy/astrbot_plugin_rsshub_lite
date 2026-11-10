"""Package the trimmed upstream plugin without local/reference/runtime data."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
NAME = "astrbot_plugin_rsshub"
VERSION = "2.1.4-lite.3"
DIRECTORIES = ("src", "pages", "assets", "docs", "scripts")
FILES = (
    "main.py",
    "bootstrap.py",
    "metadata.yaml",
    "_conf_schema.json",
    "requirements.txt",
    "README.md",
    "NOTICE.md",
    "LICENSE",
    "logo.png",
    "UPSTREAM.json",
)


def main():
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
    destination = ROOT / "dist" / f"{NAME}-{VERSION}.zip"
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
