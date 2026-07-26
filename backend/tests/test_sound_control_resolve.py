from song_genres import resolve_sound_control


def test_known_labels_map_to_phrases_in_section_order():
    sc = {"production": "Cinematic", "bass": "808", "drums": "Punchy"}
    desc, instrumental = resolve_sound_control(sc)
    assert desc == ["heavy 808 bass", "punchy hard-hitting drums", "cinematic layered production"]
    assert instrumental is False


def test_custom_and_notes_pass_through_verbatim_notes_last():
    sc = {"bass": "gargantuan earthquake bass", "notes": "make the drop massive"}
    desc, _ = resolve_sound_control(sc)
    assert desc == ["gargantuan earthquake bass", "make the drop massive"]


def test_none_instrumental_sets_flag_and_skips_descriptor():
    sc = {"vocals": "None/Instrumental", "bass": "808"}
    desc, instrumental = resolve_sound_control(sc)
    assert instrumental is True
    assert desc == ["heavy 808 bass"]


def test_full_order_bass_drums_vocals_production_notes():
    sc = {"production": "Vintage", "bass": "Sub Bass", "vocals": "Soft",
          "drums": "Lo-fi", "notes": "warm"}
    desc, _ = resolve_sound_control(sc)
    assert desc == ["deep sub bass", "lo-fi dusty drums", "soft gentle vocals",
                    "warm vintage analog production", "warm"]


def test_length_caps_applied_before_mapping():
    sc = {"bass": "x" * 300, "notes": "y" * 400}
    desc, _ = resolve_sound_control(sc)
    assert len(desc[0]) == 200
    assert len(desc[1]) == 300


def test_empty_inputs():
    assert resolve_sound_control(None) == ([], False)
    assert resolve_sound_control({}) == ([], False)
