import pytest

from refact.verify_check import fmt_val


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, "NULL"),
        (123, "123"),
        (0, "0"),
        (-1, "-1"),
        (3.14159, "3.141590"),
        (0.0, "0.000000"),
        (-1.5, "-1.500000"),
        ("hello", "hello"),
        ("", ""),
        (True, "True"),
        (False, "False"),
    ],
)
def test_fmt_val_formats_supported_scalar_values(value, expected):
    assert fmt_val(value) == expected
