from refact.verify_check import fmt_val


def test_fmt_val_none():
    assert fmt_val(None) == "NULL"


def test_fmt_val_int():
    assert fmt_val(123) == "123"
    assert fmt_val(0) == "0"
    assert fmt_val(-1) == "-1"


def test_fmt_val_float():
    assert fmt_val(3.14159) == "3.141590"
    assert fmt_val(0.0) == "0.000000"
    assert fmt_val(-1.5) == "-1.500000"


def test_fmt_val_str():
    assert fmt_val("hello") == "hello"
    assert fmt_val("") == ""


def test_fmt_val_bool():
    assert fmt_val(True) == "True"
    assert fmt_val(False) == "False"
