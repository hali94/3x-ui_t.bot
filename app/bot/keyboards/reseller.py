from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)


# ── Main menus ───────────────────────────────────────────────────────────────

def reseller_l1_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ فروش اشتراک"), KeyboardButton(text="🔄 تمدید اشتراک")],
            [KeyboardButton(text="👥 مشتری‌های من"), KeyboardButton(text="👥 نمایندگان زیرمجموعه")],
            [KeyboardButton(text="➕ ساخت نماینده سطح ۲"), KeyboardButton(text="💳 اعتبار")],
            [KeyboardButton(text="📊 گزارش فروش"), KeyboardButton(text="🔔 اعلان‌ها")],
        ],
        resize_keyboard=True,
    )


def reseller_l2_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ فروش اشتراک"), KeyboardButton(text="🔄 تمدید اشتراک")],
            [KeyboardButton(text="👥 مشتری‌های من"), KeyboardButton(text="💳 اعتبار")],
            [KeyboardButton(text="📊 گزارش فروش"), KeyboardButton(text="🔔 اعلان‌ها")],
        ],
        resize_keyboard=True,
    )


# ── Duration picker ──────────────────────────────────────────────────────────

def duration_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="۳۰ روز", callback_data="duration:30"),
                InlineKeyboardButton(text="۶۰ روز", callback_data="duration:60"),
            ],
            [
                InlineKeyboardButton(text="۹۰ روز", callback_data="duration:90"),
                InlineKeyboardButton(text="۱۸۰ روز", callback_data="duration:180"),
            ],
            [InlineKeyboardButton(text="❌ انصراف", callback_data="cancel")],
        ]
    )


# ── Confirmation ─────────────────────────────────────────────────────────────

def confirm_keyboard(yes_data: str = "confirm:yes", no_data: str = "cancel") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ تأیید", callback_data=yes_data),
                InlineKeyboardButton(text="❌ انصراف", callback_data=no_data),
            ]
        ]
    )


# ── Customer list / detail ───────────────────────────────────────────────────

def customer_list_keyboard(
    customers: list, page: int = 0, per_page: int = 10
) -> InlineKeyboardMarkup:
    start = page * per_page
    end = start + per_page
    page_customers = customers[start:end]

    _status_icon = {
        "ACTIVE": "✅", "EXPIRED": "⏰",
        "DISABLED": "🚫", "TRAFFIC_EXHAUSTED": "📵",
    }
    buttons = [
        [
            InlineKeyboardButton(
                text=f"{_status_icon.get(c.status, '❓')} {c.name} — {c.volume_gb:.0f}GB",
                callback_data=f"customer:detail:{c.id}",
            )
        ]
        for c in page_customers
    ]

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️ قبلی", callback_data=f"customer:page:{page-1}"))
    if end < len(customers):
        nav.append(InlineKeyboardButton(text="بعدی ▶️", callback_data=f"customer:page:{page+1}"))
    if nav:
        buttons.append(nav)
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="reseller:back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def customer_detail_keyboard(customer_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 تمدید اشتراک", callback_data=f"customer:renew:{customer_id}")],
            [InlineKeyboardButton(text="📋 دریافت لینک", callback_data=f"customer:link:{customer_id}")],
            [InlineKeyboardButton(text="🔙 بازگشت به لیست", callback_data="reseller:customers")],
        ]
    )


# ── Child reseller list ───────────────────────────────────────────────────────

def child_reseller_list_keyboard(children: list) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text=f"{'✅' if c.active else '❌'} {c.user.full_name if c.user else f'ID:{c.id}'} "
                     f"({c.remaining_credit_gb:.1f}GB باقی)",
                callback_data=f"child:detail:{c.id}",
            )
        ]
        for c in children
    ]
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="reseller:back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def child_reseller_detail_keyboard(child_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 افزایش اعتبار", callback_data=f"child:credit:{child_id}")],
            [InlineKeyboardButton(text="📊 گزارش فروش", callback_data=f"child:sales:{child_id}")],
            [InlineKeyboardButton(text="🔙 بازگشت به لیست", callback_data="reseller:children")],
        ]
    )


# ── Cancel ────────────────────────────────────────────────────────────────────

def cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="❌ انصراف", callback_data="cancel")]]
    )
