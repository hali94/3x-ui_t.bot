from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton


def admin_main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👥 مدیریت نمایندگان"), KeyboardButton(text="📊 گزارش فروش")],
            [KeyboardButton(text="🖥 مدیریت سرورها"), KeyboardButton(text="⚙ تنظیمات")],
        ],
        resize_keyboard=True,
    )


def reseller_management_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ ساخت نماینده", callback_data="admin:reseller:create")],
            [InlineKeyboardButton(text="📋 لیست نمایندگان", callback_data="admin:reseller:list")],
            [InlineKeyboardButton(text="💳 افزایش اعتبار", callback_data="admin:reseller:add_credit")],
            [InlineKeyboardButton(text="🚫 غیرفعال کردن", callback_data="admin:reseller:deactivate")],
            [InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin:back")],
        ]
    )


def server_management_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ افزودن سرور", callback_data="admin:server:add")],
            [InlineKeyboardButton(text="📋 لیست سرورها", callback_data="admin:server:list")],
            [InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin:back")],
        ]
    )


def reseller_list_keyboard(resellers: list) -> InlineKeyboardMarkup:
    buttons = []
    for r in resellers:
        name = r.user.full_name if r.user else f"ID:{r.id}"
        buttons.append([
            InlineKeyboardButton(
                text=f"{'✅' if r.active else '❌'} {name}",
                callback_data=f"admin:reseller:detail:{r.id}",
            )
        ])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin:reseller:menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_keyboard(yes_data: str, no_data: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ تأیید", callback_data=yes_data),
                InlineKeyboardButton(text="❌ انصراف", callback_data=no_data),
            ]
        ]
    )
