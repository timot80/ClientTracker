from ap_filesystem_audit.parser import parse_filesystems


SAMPLE = """
MBY-CON-SCC1_BAYSIDE_D-7#sh filesystems
Filesystem Size Used Available Use% Mounted on
devtmpfs 883.0M 0 883.0M 0% /dev
/sysroot 885.6M 202.0M 683.5M 23% /
tmpfs 1.0M 44.0K 980.0K 4% /dev/shm
/dev/ubivol/part1 372.1M 79.7M 292.5M 21% /part1
/dev/ubivol/part2 520.1M 81.2M 438.9M 16% /part2
none 95.4M 95.0M 376.0K 100% /tmp
MBY-CON-SCC1_BAYSIDE_D-7#
"""


def test_parse_filesystems_reads_rows_and_ignores_prompts():
    snapshot = parse_filesystems(SAMPLE)

    assert len(snapshot.rows) == 6
    tmp = snapshot.rows[-1]
    assert tmp.filesystem == "none"
    assert tmp.size == "95.4M"
    assert tmp.used == "95.0M"
    assert tmp.available == "376.0K"
    assert tmp.used_percent == 100
    assert tmp.mount == "/tmp"
    assert snapshot.parser_warnings == []


def test_parse_filesystems_records_malformed_table_rows():
    output = """
Filesystem Size Used Available Use% Mounted on
bad row that should not parse
none 95.4M 95.0M 376.0K 100% /tmp
"""

    snapshot = parse_filesystems(output)

    assert len(snapshot.rows) == 1
    assert snapshot.parser_warnings
    assert "bad row" in snapshot.parser_warnings[0]
