"""Small, bounded primitives for inspecting untrusted Office ZIP archives."""

from struct import Struct
from typing import NamedTuple
from zipfile import ZipFile, ZipInfo

_EOCD_SIGNATURE = b"PK\x05\x06"
_ZIP64_EOCD_SIGNATURE = b"PK\x06\x06"
_ZIP64_LOCATOR_SIGNATURE = b"PK\x06\x07"
_CENTRAL_DIRECTORY_SIGNATURE = b"PK\x01\x02"
_EOCD = Struct("<4s4H2LH")
_ZIP64_EOCD = Struct("<4sQ2H2L4Q")
_ZIP64_LOCATOR = Struct("<4sLQL")
_CENTRAL_DIRECTORY_HEADER = Struct("<4s6H3L5H2L")
_MAX_ZIP_COMMENT_BYTES = 65_535
_MAX_ZIP64_EXTENSIBLE_DATA_BYTES = 65_535
_ZIP64_MIN_RECORD_BYTES = 44
_ZIP64_RECORD_PREFIX_BYTES = 12


class OfficeArchiveLimitError(ValueError):
    """An Office archive or member exceeded its inspection budget."""


class OfficeArchiveInvalidError(ValueError):
    """An Office archive has inconsistent or unsupported directory metadata."""


class _DirectoryMetadata(NamedTuple):
    end: int
    disk_number: int
    directory_disk: int
    entries_on_disk: int
    entries_total: int
    size: int
    offset: int


def preflight_office_archive(
    content: bytes,
    *,
    max_members: int,
    max_directory_bytes: int,
) -> None:
    """Walk a bounded central directory before ``ZipFile`` creates ``ZipInfo`` objects."""
    metadata = _directory_metadata(content)
    _validate_directory_metadata(metadata, max_members, max_directory_bytes)
    directory_start = metadata.end - metadata.size
    if directory_start < 0 or directory_start - metadata.offset < 0:
        raise OfficeArchiveInvalidError("Office archive has an invalid central directory offset.")
    _walk_central_directory(
        content, directory_start, metadata.end, metadata.entries_total, max_members
    )


def _directory_metadata(content: bytes) -> _DirectoryMetadata:
    eocd_offset = _find_eocd(content)
    eocd = _EOCD.unpack_from(content, eocd_offset)
    metadata = _DirectoryMetadata(eocd_offset, *eocd[1:7])
    locator_offset = metadata.end - _ZIP64_LOCATOR.size
    if (
        locator_offset >= 0
        and content[locator_offset : locator_offset + 4] == _ZIP64_LOCATOR_SIGNATURE
    ):
        return _zip64_metadata(content, locator_offset)
    if (
        metadata.entries_on_disk == 0xFFFF
        or metadata.entries_total == 0xFFFF
        or metadata.size == 0xFFFFFFFF
        or metadata.offset == 0xFFFFFFFF
    ):
        raise OfficeArchiveInvalidError("Office archive has incomplete ZIP64 metadata.")
    return metadata


def _validate_directory_metadata(
    metadata: _DirectoryMetadata,
    max_members: int,
    max_directory_bytes: int,
) -> None:
    if (
        metadata.disk_number != 0
        or metadata.directory_disk != 0
        or metadata.entries_on_disk != metadata.entries_total
    ):
        raise OfficeArchiveInvalidError("Multi-disk Office archives are not supported.")
    if metadata.entries_total > max_members:
        raise OfficeArchiveLimitError("Office archive contains too many members.")
    if metadata.size > max_directory_bytes:
        raise OfficeArchiveLimitError("Office archive central directory is too large.")


def _walk_central_directory(
    content: bytes,
    directory_start: int,
    directory_end: int,
    expected_members: int,
    max_members: int,
) -> None:
    position = directory_start
    member_count = 0
    while position < directory_end:
        if position + _CENTRAL_DIRECTORY_HEADER.size > directory_end:
            raise OfficeArchiveInvalidError("Office archive has a truncated central directory.")
        header = _CENTRAL_DIRECTORY_HEADER.unpack_from(content, position)
        if header[0] != _CENTRAL_DIRECTORY_SIGNATURE:
            raise OfficeArchiveInvalidError(
                "Office archive has invalid central directory metadata."
            )
        entry_size = _CENTRAL_DIRECTORY_HEADER.size + header[10] + header[11] + header[12]
        position += entry_size
        if position > directory_end:
            raise OfficeArchiveInvalidError(
                "Office archive has a truncated central directory entry."
            )
        member_count += 1
        if member_count > max_members:
            raise OfficeArchiveLimitError("Office archive contains too many members.")

    if member_count != expected_members:
        raise OfficeArchiveInvalidError("Office archive central directory count is inconsistent.")


def _find_eocd(content: bytes) -> int:
    minimum = max(0, len(content) - _EOCD.size - _MAX_ZIP_COMMENT_BYTES)
    search_end = len(content)
    while search_end > minimum:
        offset = content.rfind(_EOCD_SIGNATURE, minimum, search_end)
        if offset < 0:
            break
        if offset + _EOCD.size <= len(content):
            record = _EOCD.unpack_from(content, offset)
            if offset + _EOCD.size + record[7] == len(content):
                return offset
        search_end = offset
    raise OfficeArchiveInvalidError("Office archive end record is missing or malformed.")


def _zip64_metadata(
    content: bytes,
    locator_offset: int,
) -> _DirectoryMetadata:
    _signature, locator_disk, record_offset, disk_count = _ZIP64_LOCATOR.unpack_from(
        content, locator_offset
    )
    if locator_disk != 0 or disk_count != 1:
        raise OfficeArchiveInvalidError("Multi-disk Office archives are not supported.")
    record_span = locator_offset - record_offset
    if record_span < _ZIP64_EOCD.size:
        raise OfficeArchiveInvalidError("Office archive ZIP64 metadata is truncated.")
    if record_span > _ZIP64_EOCD.size + _MAX_ZIP64_EXTENSIBLE_DATA_BYTES:
        raise OfficeArchiveLimitError("Office archive ZIP64 metadata exceeds its byte budget.")
    record = _ZIP64_EOCD.unpack_from(content, record_offset)
    record_size = record[1]
    if (
        record[0] != _ZIP64_EOCD_SIGNATURE
        or record_size < _ZIP64_MIN_RECORD_BYTES
        or record_offset + _ZIP64_RECORD_PREFIX_BYTES + record_size != locator_offset
    ):
        raise OfficeArchiveInvalidError("Office archive ZIP64 metadata is malformed.")
    return _DirectoryMetadata(record_offset, *record[4:10])


def validate_office_archive(
    archive: ZipFile,
    *,
    max_members: int,
    max_expanded_bytes: int,
) -> tuple[ZipInfo, ...]:
    """Validate central-directory limits before deriving names or reading members."""
    members = tuple(archive.infolist())
    if len(members) > max_members:
        raise OfficeArchiveLimitError("Office archive contains too many members.")
    if sum(member.file_size for member in members) > max_expanded_bytes:
        raise OfficeArchiveLimitError("Office archive expands beyond its byte budget.")
    return members


def read_bounded_member(archive: ZipFile, member: ZipInfo, maximum: int) -> bytes:
    """Read no more than a fixed expanded-byte budget from one ZIP member."""
    if member.file_size > maximum:
        raise OfficeArchiveLimitError("Office archive member exceeds its byte budget.")
    with archive.open(member) as source:
        content = source.read(maximum + 1)
    if len(content) > maximum:
        raise OfficeArchiveLimitError("Office archive member exceeds its byte budget.")
    return content
