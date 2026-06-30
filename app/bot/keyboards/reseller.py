from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton


def reseller_main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ ساخت اشتراک"), KeyboardButton(text="👥 مشتری‌های من")],
            [KeyboardButton(text="🔄 تمدید اشتراک"), KeyboardButton(text="📊 گزارش فروش")],
            [KeyboardButton(text="💰 اعتبار من"), KeyboardButton(text="🔔 اعلان‌ها")],
        ],
        resize_keyboard=True,
    )


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


def customer_list_keyboard(customers: list, page: int = 0, per_page: int = 10) -> InlineKeyboardMarkup:
    start = page * per_page
    end = start + per_page
    page_customers = customers[start:end]
    buttons = []
    for c in page_customers:
        status_icon = {"ACTIVE": "✅", "EXPIRED": "⏰", "DISABLED": "🚫", "TRAFFIC_EXHAUSTED": "📵"}.get(c.status, "❓")
        buttons.append([
            InlineKeyboardButton(
                text=f"{status_icon} {c.name} — {c.volume_gb:.0f}GB",
                callback_data=f"customer:detail:{c.id}",
            )
        ])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️ قبلی", callback_data=f"customer:page:{page-1}"))
    if end < len(customers):
        nav.append(InlineKeyboardButton(text="بعدی ▶️", callback_data=f"customer:page:{page+1}"))
    if nav:
        buttons.append(nav)
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="reseller:menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def customer_detail_keyboard(customer_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 تمدید اشتراک", callback_data=f"customer:renew:{customer_id}")],
            [InlineKeyboardButton(text="📋 کپی لینک", callback_data=f"customer:link:{customer_id}")],
            [InlineKeyboardButton(text="🔙 بازگشت به لیست", callback_data="reseller:customers")],
        ]
    )


def cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="❌ انصراف", callback_data="cancel")]]
    )
