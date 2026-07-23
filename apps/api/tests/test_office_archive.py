from io import BytesIO
from struct import pack, pack_into, unpack_from
from zipfile import ZIP_STORED, ZipFile, ZipInfo

import pytest

from coeus.services.office_archive import (
    OfficeArchiveInvalidError,
    OfficeArchiveLimitError,
    preflight_office_archive,
    read_bounded_member,
    validate_office_archive,
)


def _archive(*names: str) -> bytes:
    stream = BytesIO()
    with ZipFile(stream, "w", ZIP_STORED) as archive:
        for name in names:
            archive.writestr(name, b"")
    return stream.getvalue()


def _as_zip64(content: bytes, extensible_data: bytes = b"") -> bytes:
    result = bytearray(content)
    eocd = result.rfind(b"PK\x05\x06")
    entries = unpack_from("<H", result, eocd + 10)[0]
    directory_size = unpack_from("<L", result, eocd + 12)[0]
    directory_offset = unpack_from("<L", result, eocd + 16)[0]
    zip64_record = pack(
        "<4sQ2H2L4Q",
        b"PK\x06\x06",
        44 + len(extensible_data),
        45,
        45,
        0,
        0,
        entries,
        entries,
        directory_size,
        directory_offset,
    )
    zip64_locator = pack("<4sLQL", b"PK\x06\x07", 0, eocd, 1)
    result[eocd:eocd] = zip64_record + extensible_data + zip64_locator
    shifted_eocd = eocd + len(zip64_record) + len(extensible_data) + len(zip64_locator)
    pack_into("<HHLL", result, shifted_eocd + 8, 0xFFFF, 0xFFFF, 0xFFFFFFFF, 0xFFFFFFFF)
    return bytes(result)


def test_preflight_accepts_a_regular_bounded_central_directory() -> None:
    content = _archive("word/document.xml", "word/styles.xml")

    preflight_office_archive(content, max_members=2, max_directory_bytes=len(content))

    commented = BytesIO()
    with ZipFile(commented, "w", ZIP_STORED) as archive:
        archive.writestr("word/document.xml", b"")
        archive.comment = b"synthetic PK\x05\x06 non-record"
    preflight_office_archive(
        commented.getvalue(), max_members=1, max_directory_bytes=len(commented.getvalue())
    )


def test_preflight_rejects_member_budget_before_materialising_entries() -> None:
    content = _archive("word/document.xml", "word/styles.xml")

    with pytest.raises(OfficeArchiveLimitError, match="too many members"):
        preflight_office_archive(content, max_members=1, max_directory_bytes=len(content))


def test_preflight_walks_records_instead_of_trusting_eocd_count() -> None:
    content = bytearray(_archive("word/document.xml", "word/styles.xml"))
    eocd = content.rfind(b"PK\x05\x06")
    pack_into("<HH", content, eocd + 8, 1, 1)

    with pytest.raises(OfficeArchiveLimitError, match="too many members"):
        preflight_office_archive(bytes(content), max_members=1, max_directory_bytes=len(content))


def test_preflight_rejects_inconsistent_central_directory_metadata() -> None:
    content = bytearray(_archive("word/document.xml"))
    eocd = content.rfind(b"PK\x05\x06")
    pack_into("<L", content, eocd + 12, 1)

    with pytest.raises(OfficeArchiveInvalidError, match="central directory"):
        preflight_office_archive(bytes(content), max_members=5, max_directory_bytes=len(content))


def test_preflight_rejects_missing_or_incomplete_end_metadata() -> None:
    with pytest.raises(OfficeArchiveInvalidError, match="end record"):
        preflight_office_archive(b"PK-not-an-archive", max_members=5, max_directory_bytes=100)

    content = bytearray(_archive("word/document.xml"))
    eocd = content.rfind(b"PK\x05\x06")
    pack_into("<HH", content, eocd + 8, 0xFFFF, 0xFFFF)
    with pytest.raises(OfficeArchiveInvalidError, match="incomplete ZIP64"):
        preflight_office_archive(bytes(content), max_members=5, max_directory_bytes=len(content))


def test_preflight_rejects_multi_disk_and_overlong_directory_metadata() -> None:
    content = bytearray(_archive("word/document.xml"))
    eocd = content.rfind(b"PK\x05\x06")
    pack_into("<H", content, eocd + 4, 1)
    with pytest.raises(OfficeArchiveInvalidError, match="Multi-disk"):
        preflight_office_archive(bytes(content), max_members=5, max_directory_bytes=len(content))

    content = _archive("word/document.xml")
    with pytest.raises(OfficeArchiveLimitError, match="central directory is too large"):
        preflight_office_archive(content, max_members=5, max_directory_bytes=0)


def test_preflight_rejects_invalid_or_truncated_directory_records() -> None:
    invalid_offset = bytearray(_archive("word/document.xml"))
    eocd = invalid_offset.rfind(b"PK\x05\x06")
    pack_into("<L", invalid_offset, eocd + 16, eocd + 1)
    with pytest.raises(OfficeArchiveInvalidError, match="directory offset"):
        preflight_office_archive(
            bytes(invalid_offset), max_members=5, max_directory_bytes=len(invalid_offset)
        )

    truncated_header = bytearray(_archive("word/document.xml"))
    eocd = truncated_header.rfind(b"PK\x05\x06")
    pack_into("<LL", truncated_header, eocd + 12, 1, eocd - 1)
    with pytest.raises(OfficeArchiveInvalidError, match="truncated central directory"):
        preflight_office_archive(
            bytes(truncated_header), max_members=5, max_directory_bytes=len(truncated_header)
        )

    invalid_signature = bytearray(_archive("word/document.xml"))
    eocd = invalid_signature.rfind(b"PK\x05\x06")
    directory = unpack_from("<L", invalid_signature, eocd + 16)[0]
    invalid_signature[directory : directory + 4] = b"FAIL"
    with pytest.raises(OfficeArchiveInvalidError, match="invalid central directory"):
        preflight_office_archive(
            bytes(invalid_signature), max_members=5, max_directory_bytes=len(invalid_signature)
        )

    truncated_entry = bytearray(_archive("word/document.xml"))
    eocd = truncated_entry.rfind(b"PK\x05\x06")
    directory = unpack_from("<L", truncated_entry, eocd + 16)[0]
    pack_into("<H", truncated_entry, directory + 28, 0xFFFF)
    with pytest.raises(OfficeArchiveInvalidError, match="truncated central directory entry"):
        preflight_office_archive(
            bytes(truncated_entry), max_members=5, max_directory_bytes=len(truncated_entry)
        )


def test_preflight_rejects_inconsistent_walked_member_count() -> None:
    content = bytearray(_archive("word/document.xml"))
    eocd = content.rfind(b"PK\x05\x06")
    pack_into("<HH", content, eocd + 8, 2, 2)

    with pytest.raises(OfficeArchiveInvalidError, match="count is inconsistent"):
        preflight_office_archive(bytes(content), max_members=2, max_directory_bytes=len(content))


def test_preflight_accepts_zip64_directory_metadata() -> None:
    content = _as_zip64(_archive("word/document.xml"))

    preflight_office_archive(content, max_members=1, max_directory_bytes=len(content))


def test_preflight_accepts_bounded_zip64_extensible_data() -> None:
    content = _as_zip64(_archive("word/document.xml"), b"synthetic-extension")

    preflight_office_archive(content, max_members=1, max_directory_bytes=len(content))


def test_preflight_rejects_invalid_zip64_metadata() -> None:
    multi_disk = bytearray(_as_zip64(_archive("word/document.xml")))
    eocd = multi_disk.rfind(b"PK\x05\x06")
    locator = eocd - 20
    pack_into("<L", multi_disk, locator + 4, 1)
    with pytest.raises(OfficeArchiveInvalidError, match="Multi-disk"):
        preflight_office_archive(
            bytes(multi_disk), max_members=1, max_directory_bytes=len(multi_disk)
        )

    malformed = bytearray(_as_zip64(_archive("word/document.xml")))
    zip64_record = malformed.rfind(b"PK\x06\x06")
    pack_into("<Q", malformed, zip64_record + 4, 43)
    with pytest.raises(OfficeArchiveInvalidError, match="ZIP64 metadata"):
        preflight_office_archive(
            bytes(malformed), max_members=1, max_directory_bytes=len(malformed)
        )

    locator_only = pack("<4sLQL", b"PK\x06\x07", 0, 0, 1) + pack(
        "<4s4H2LH", b"PK\x05\x06", 0, 0, 0xFFFF, 0xFFFF, 0xFFFFFFFF, 0xFFFFFFFF, 0
    )
    with pytest.raises(OfficeArchiveInvalidError, match="ZIP64 metadata is truncated"):
        preflight_office_archive(locator_only, max_members=1, max_directory_bytes=100)

    inconsistent_offset = bytearray(_as_zip64(_archive("word/document.xml")))
    eocd = inconsistent_offset.rfind(b"PK\x05\x06")
    locator = eocd - 20
    record_offset = unpack_from("<Q", inconsistent_offset, locator + 8)[0]
    pack_into("<Q", inconsistent_offset, locator + 8, record_offset + 1)
    with pytest.raises(OfficeArchiveInvalidError, match="ZIP64 metadata"):
        preflight_office_archive(
            bytes(inconsistent_offset),
            max_members=1,
            max_directory_bytes=len(inconsistent_offset),
        )


def test_preflight_bounds_zip64_extensible_data() -> None:
    content = _as_zip64(_archive("word/document.xml"), b"x" * 65_536)

    with pytest.raises(OfficeArchiveLimitError, match="ZIP64 metadata exceeds"):
        preflight_office_archive(content, max_members=1, max_directory_bytes=len(content))


def test_post_parse_archive_and_member_limits_remain_enforced() -> None:
    content = _archive("word/document.xml")
    with ZipFile(BytesIO(content)) as archive:
        members = validate_office_archive(archive, max_members=1, max_expanded_bytes=1)
        assert read_bounded_member(archive, members[0], 1) == b""

        with pytest.raises(OfficeArchiveLimitError, match="too many members"):
            validate_office_archive(archive, max_members=0, max_expanded_bytes=1)

    expanded = BytesIO()
    with ZipFile(expanded, "w", ZIP_STORED) as archive:
        archive.writestr("word/document.xml", b"large")
    with ZipFile(BytesIO(expanded.getvalue())) as archive:
        member = archive.infolist()[0]
        with pytest.raises(OfficeArchiveLimitError, match="expands beyond"):
            validate_office_archive(archive, max_members=1, max_expanded_bytes=1)
        with pytest.raises(OfficeArchiveLimitError, match="member exceeds"):
            read_bounded_member(archive, member, 1)

    class InconsistentArchive:
        def open(self, _member: ZipInfo) -> BytesIO:
            return BytesIO(b"larger than declared")

    metadata = ZipInfo("word/document.xml")
    metadata.file_size = 0
    with pytest.raises(OfficeArchiveLimitError, match="member exceeds"):
        read_bounded_member(InconsistentArchive(), metadata, 1)  # type: ignore[arg-type]
