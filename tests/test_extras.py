from rmp_client.extras.dedupe import is_valid_comment, normalize_comment


def test_normalize_comment_and_validity() -> None:
    raw = "  Hello   World!  "
    normalized = normalize_comment(raw)
    assert normalized == "hello world!"
    assert is_valid_comment(normalized, min_len=5)

