"""Validate and safely unpack a Power Platform solution export archive."""

from __future__ import annotations

import argparse
import os
from pathlib import Path, PurePosixPath
from zipfile import BadZipFile, ZipFile, is_zipfile

DEFAULT_OUTPUT_DIRECTORY = Path(os.getenv("PPM_UNPACK_DIRECTORY", "data/unpacked"))
DEFAULT_MAX_SIZE_MB = int(os.getenv("PPM_MAX_IMPORT_SIZE_MB", "100"))


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path, help="Path to a solution export zip file.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIRECTORY)
    parser.add_argument("--max-size-mb", type=int, default=DEFAULT_MAX_SIZE_MB)
    return parser.parse_args()


def is_safe_member(member_name: str) -> bool:
    path = PurePosixPath(member_name)
    return not path.is_absolute() and ".." not in path.parts


def unpack_solution(archive: Path, output_directory: Path, max_size_mb: int) -> Path:
    if archive.suffix.lower() != ".zip" or not archive.is_file() or not is_zipfile(archive):
        raise ValueError(f"{archive} is not a valid zip archive.")
    if max_size_mb <= 0:
        raise ValueError("max-size-mb must be greater than zero.")
    max_size_bytes = max_size_mb * 1024 * 1024
    if archive.stat().st_size > max_size_bytes:
        raise ValueError(f"Archive exceeds the configured {max_size_mb} MB limit.")
    try:
        with ZipFile(archive) as solution_zip:
            members = solution_zip.infolist()
            if sum(member.file_size for member in members) > max_size_bytes:
                raise ValueError(f"Unpacked archive exceeds the configured {max_size_mb} MB limit.")
            if any(not is_safe_member(member.filename) for member in members):
                raise ValueError("Archive contains an unsafe extraction path.")
            if any((member.external_attr >> 16) & 0o170000 == 0o120000 for member in members):
                raise ValueError("Archive contains a symbolic link, which is not allowed.")
            destination = output_directory / archive.stem
            destination.mkdir(parents=True, exist_ok=True)
            solution_zip.extractall(destination)
    except BadZipFile as error:
        raise ValueError(f"Unable to read archive: {error}") from error
    return destination


def main() -> None:
    arguments = parse_arguments()
    destination = unpack_solution(arguments.archive, arguments.output_dir, arguments.max_size_mb)
    print(f"Validated and unpacked solution to: {destination}")


if __name__ == "__main__":
    main()