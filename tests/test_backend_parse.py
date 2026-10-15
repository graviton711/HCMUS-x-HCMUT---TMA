"""Code-first soft metric parsing. Every value needs a verbatim quote."""

from backend.decide.parse import count_activities, count_legs, full_refund_cutoff


def test_count_activities_splits_days_and_segments():
    itinerary = (
        "Ngày 1: Sài Gòn - Đà Lạt, tham quan Dinh Bảo Đại. "
        "Ngày 2: Langbiang, Thung lũng Tình yêu."
    )
    count, quotes = count_activities(itinerary)
    assert count == 4
    assert any("Dinh Bảo Đại" in quote for quote in quotes)
    assert all(quotes)


def test_count_activities_empty_stays_zero():
    assert count_activities("") == (0, [])
    assert count_activities("   ") == (0, [])


def test_count_legs_counts_arrows_only():
    count, quotes = count_legs("Ngày 1: A → B → C")
    assert count == 2
    assert quotes == ["Ngày 1: A → B → C"]


def test_count_legs_without_arrows_stays_zero():
    assert count_legs("Ngày 1: tham quan, ăn trưa.") == (0, [])


def test_full_refund_cutoff_reads_cancel_before_days():
    days, quote = full_refund_cutoff("Hủy trước 7 ngày hoàn 100%, trước 3 ngày hoàn 50%.")
    assert days == 7
    assert quote and "100%" in quote


def test_full_refund_cutoff_without_full_refund_stays_none():
    assert full_refund_cutoff("Hủy trước 10 ngày hoàn 80%.") == (None, None)
    assert full_refund_cutoff("") == (None, None)
