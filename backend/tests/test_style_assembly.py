import logging
from style_assembly import assemble_variant_style


def test_common_case_is_plain_join():
    core = "east coast hip hop, boom bap drums, jazzy samples"
    parts = ["fast double-time rap flow", "heavy 808 bass"]
    out = assemble_variant_style(core, parts, tail="")
    assert out == "fast double-time rap flow, heavy 808 bass, east coast hip hop, boom bap drums, jazzy samples"


def test_no_suffix_parts_returns_core_plus_tail():
    core = "ambient pads, soft textures"
    assert assemble_variant_style(core, [], tail="") == "ambient pads, soft textures"
    assert assemble_variant_style(core, None, tail=", 432 Hz") == "ambient pads, soft textures, 432 Hz"


def test_lowest_priority_dropped_first_and_named(caplog):
    core = "g" * 950
    parts = ["accent_descriptor_kept", "bass_descriptor_drop2", "notes_descriptor_drop1"]
    with caplog.at_level(logging.WARNING):
        out = assemble_variant_style(core, parts, tail="", hard_cap=990, genre="pop")
    assert out == "accent_descriptor_kept, " + core
    assert "bass_descriptor_drop2" not in out
    assert "notes_descriptor_drop1" not in out
    assert "bass_descriptor_drop2" in caplog.text
    assert "notes_descriptor_drop1" in caplog.text


def test_genre_core_never_trimmed_by_suffix():
    core = "c" * 985
    out = assemble_variant_style(core, ["some accent descriptor here"], tail="", hard_cap=990)
    assert core in out
    assert "some accent descriptor here" not in out


def test_final_safety_net_truncates_core_only_overflow():
    core = "d" * 1005
    out = assemble_variant_style(core, [], tail="", hard_cap=990)
    assert len(out) == 990


def test_rapidfire_accent_survives_common_case():
    core = "east coast hip hop, boom bap drums, jazzy piano samples, vinyl crackle"
    rapidfire = "fast double-time rap flow, rapid staccato cadence, sped-up vocals, 170 BPM"
    out = assemble_variant_style(core, [rapidfire, "heavy 808 bass"], tail="")
    assert out == f"{rapidfire}, heavy 808 bass, {core}"


def test_intermittent_cue_kept_soundcontrol_dropped_first():
    core = "e" * 900
    intermittent = "mostly instrumental, brief vocal hooks only, 3 minute duration"
    out = assemble_variant_style(core, [intermittent, "cinematic layered production"], tail="", hard_cap=990)
    assert intermittent in out
    assert "cinematic layered production" not in out
