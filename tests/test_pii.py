from app.pii import scrub_text


def test_scrub_email() -> None:
    out = scrub_text("Email me at student@vinuni.edu.vn")
    assert "student@" not in out
    assert "REDACTED_EMAIL" in out


def test_scrub_common_vietnamese_phone_formats() -> None:
    phone_numbers = (
        "0901234567",
        "090 123 4567",
        "090.123.4567",
        "090-123-4567",
        "+84 90 123 4567",
    )

    for phone_number in phone_numbers:
        out = scrub_text(f"Contact: {phone_number}")
        assert phone_number not in out
        assert "REDACTED_PHONE_VN" in out


def test_scrub_cccd() -> None:
    # CCCD có đúng 12 chữ số; pattern phone_vn không được nuốt nhầm
    # nhờ lookaround (?<!\d)/(?!\d) ở hai đầu.
    cccd_numbers = ("001234567890", "079301234567")

    for cccd_number in cccd_numbers:
        out = scrub_text(f"CCCD {cccd_number}")
        assert cccd_number not in out
        assert "REDACTED_CCCD" in out


def test_scrub_credit_card() -> None:
    card_numbers = (
        "4111 1111 1111 1111",
        "4111-1111-1111-1111",
        "4111111111111111",
    )

    for card_number in card_numbers:
        out = scrub_text(f"Card {card_number}")
        assert card_number not in out
        assert "REDACTED_CREDIT_CARD" in out
