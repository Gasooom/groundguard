from groundguard.domain.pii import detect_pii


def test_detects_email():
    result = detect_pii(
        "Contact the user at user@example.com."
    )

    assert result.detected is True
    assert "EMAIL" in result.categories
    assert "user@example.com" in result.evidence


def test_detects_phone_number():
    result = detect_pii(
        "Call me at +250 788 123 456."
    )

    assert result.detected is True
    assert "PHONE" in result.categories


def test_detects_ip_address():
    result = detect_pii(
        "The request came from 192.168.1.20."
    )

    assert result.detected is True
    assert "IP_ADDRESS" in result.categories
    assert "192.168.1.20" in result.evidence


def test_detects_credit_card_like_number():
    result = detect_pii(
        "Card: 4111 1111 1111 1111."
    )

    assert result.detected is True
    assert "CREDIT_CARD" in result.categories


def test_normal_text_has_no_pii():
    result = detect_pii(
        "GroundGuard evaluates answer reliability."
    )

    assert result.detected is False
    assert result.categories == []
    assert result.evidence == []


def test_detects_multiple_pii_types():
    result = detect_pii(
        "Email user@example.com, "
        "phone +250 788 123 456, "
        "IP 10.0.0.5."
    )

    assert result.detected is True

    assert "EMAIL" in result.categories
    assert "PHONE" in result.categories
    assert "IP_ADDRESS" in result.categories

    assert len(result.evidence) == 3


def test_empty_text_has_no_pii():
    result = detect_pii("")

    assert result.detected is False
    assert result.categories == []
    assert result.evidence == []


def test_ordinary_numbers_are_not_credit_cards():
    result = detect_pii(
        "The company has 250 employees in 2026."
    )

    assert result.detected is False


def test_invalid_ip_is_not_detected():
    result = detect_pii(
        "Example address: 999.999.999.999."
    )

    assert "IP_ADDRESS" not in result.categories