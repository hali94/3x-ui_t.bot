"""Persian number and text utilities."""

_FA_DIGITS = "۰۱۲۳۴۵۶۷۸۹"


def to_persian_digits(text: str | int | float) -> str:
    s = str(text)
    return s.translate(str.maketrans("0123456789", _FA_DIGITS))


def format_gb(gb: float | int) -> str:
    if gb == int(gb):
        return f"{to_persian_digits(int(gb))} گیگابایت"
    return f"{to_persian_digits(f'{gb:.2f}')} گیگابایت"


def format_price(amount: float | int) -> str:
    formatted = f"{int(amount):,}"
    return f"{to_persian_digits(formatted)} تومان"


def status_emoji(status: str) -> str:
    mapping = {
        "ACTIVE": "✅",
        "EXPIRED": "⏰",
        "DISABLED": "🚫",
        "TRAFFIC_EXHAUSTED": "📵",
        "INACTIVE": "❌",
        "BANNED": "🔴",
    }
    return mapping.get(status, "❓")
