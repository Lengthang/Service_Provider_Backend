"""Unit tests for platform commission splitting (services.wallet_service.split_commission).

Focuses on tricky decimal amounts where naive float math would drift, e.g. $33.33.

Runs two ways:
  * standalone:  python tests/test_commission.py
  * pytest:      pytest tests/test_commission.py
"""
import os
import sys
from contextlib import contextmanager
from decimal import Decimal

# Make the project root importable and satisfy core.config's required env vars
# before it is imported (these tests never touch the DB).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
os.environ.setdefault("SECRET_KEY", "test-secret-key")

from core.config import settings
from services.wallet_service import split_commission


@contextmanager
def commission_rate(rate):
    """Temporarily override the platform commission rate."""
    original = settings.PLATFORM_COMMISSION_RATE
    settings.PLATFORM_COMMISSION_RATE = Decimal(str(rate))
    try:
        yield
    finally:
        settings.PLATFORM_COMMISSION_RATE = original


# (rate, gross, expected_commission, expected_provider_net)
KNOWN_CASES = [
    # $33.33 @ 15%: 4.9995 -> rounds half-up to 5.00, provider keeps the rest
    ("0.15", "33.33", "5.00", "28.33"),
    ("0.15", "100.00", "15.00", "85.00"),
    ("0.15", "99.99", "15.00", "84.99"),   # 14.9985 -> 15.00
    ("0.15", "66.67", "10.00", "56.67"),   # 10.0005 -> 10.00
    ("0.15", "0.10", "0.02", "0.08"),      # 0.0150 -> half-up 0.02
    ("0.15", "0.01", "0.00", "0.01"),      # 0.0015 -> 0.00 (too small to bill)
    ("0.15", "1234.56", "185.18", "1049.38"),  # 185.184 -> 185.18
    ("0.10", "33.33", "3.33", "30.00"),
    ("0.10", "99.99", "10.00", "89.99"),   # 9.999 -> 10.00
    ("0.20", "33.33", "6.67", "26.66"),    # 6.666 -> 6.67
    ("0.00", "33.33", "0.00", "33.33"),    # zero rate takes nothing
]


def test_split_commission_known_cases():
    for rate, gross, exp_commission, exp_net in KNOWN_CASES:
        with commission_rate(rate):
            commission, net = split_commission(Decimal(gross))
        assert commission == Decimal(exp_commission), (
            f"rate={rate} gross={gross}: commission {commission} != {exp_commission}"
        )
        assert net == Decimal(exp_net), (
            f"rate={rate} gross={gross}: net {net} != {exp_net}"
        )


def test_commission_is_rounded_to_cents():
    # Commission must never carry sub-cent precision.
    with commission_rate("0.15"):
        for gross in ["33.33", "0.10", "1234.56", "7.77", "0.07"]:
            commission, _ = split_commission(Decimal(gross))
            assert commission == commission.quantize(Decimal("0.01")), (
                f"commission {commission} for gross {gross} is not in whole cents"
            )


def test_parts_always_sum_back_to_gross():
    # No money is created or lost by rounding: commission + net == gross, exactly.
    for rate in ["0.00", "0.10", "0.15", "0.20", "0.33"]:
        with commission_rate(rate):
            cents = 1
            while cents <= 20000:  # $0.01 .. $200.00
                gross = (Decimal(cents) / Decimal(100)).quantize(Decimal("0.01"))
                commission, net = split_commission(gross)
                assert commission + net == gross, (
                    f"rate={rate} gross={gross}: {commission} + {net} != {gross}"
                )
                assert commission >= 0 and net >= 0
                cents += 1


def test_zero_rate_takes_no_commission():
    with commission_rate("0.00"):
        commission, net = split_commission(Decimal("49.95"))
    assert commission == Decimal("0.00")
    assert net == Decimal("49.95")


def test_tiny_amount_rounds_commission_to_zero():
    # 0.01 * 0.15 = 0.0015 -> rounds to 0.00, so the provider keeps the cent.
    with commission_rate("0.15"):
        commission, net = split_commission(Decimal("0.01"))
    assert commission == Decimal("0.00")
    assert net == Decimal("0.01")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failures = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except AssertionError as e:
            failures += 1
            print(f"FAIL  {t.__name__}: {e}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    sys.exit(1 if failures else 0)
