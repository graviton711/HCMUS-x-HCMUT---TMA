"""fold_vi: Vietnamese text folding for matching."""

from shared.text import fold_vi


def test_fold_vi_strips_accents_and_case():
    assert fold_vi("Đà Lạt") == "dalat"
    assert fold_vi("SÀI GÒN") == "saigon"
    assert fold_vi("Mỹ Tho - Cần Thơ") == "mythocantho"


def test_fold_vi_drops_punctuation_and_spacing():
    assert fold_vi("  Hạ-Long... ") == "halong"
    assert fold_vi("") == ""


def test_fold_vi_treats_equivalent_labels_equal():
    assert fold_vi("TP.HCM") == fold_vi("tp hcm")
    assert fold_vi("Sài Gòn") == fold_vi("sai gon")
