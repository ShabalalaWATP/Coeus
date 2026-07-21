"""Small, bounded primitives for inspecting untrusted Office ZIP archives."""

from zipfile import ZipFile, ZipInfo


class OfficeArchiveLimitError(ValueError):
    """An Office archive or member exceeded its inspection budget."""


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
