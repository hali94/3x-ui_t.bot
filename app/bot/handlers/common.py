from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from app.models.user import User, UserRole
from app.bot.keyboards.admin import admin_main_menu
from app.bot.keyboards.reseller import reseller_main_menu

router = Router(name="common")


@router.message(CommandStart())
async def cmd_start(message: Message, db_user: User, state: FSMContext) -> None:
    await state.clear()
    if db_user.role == UserRole.ADMIN:
        await message.answer(
            f"🔧 خوش آمدید، {db_user.full_name}\n\nشما به عنوان مدیر اصلی وارد شدید.",
            reply_markup=admin_main_menu(),
        )
    elif db_user.role == UserRole.RESELLER:
        await message.answer(
            f"👤 خوش آمدید، {db_user.full_name}\n\nشما به عنوان نماینده وارد شدید.",
            reply_markup=reseller_main_menu(),
        )
    else:
        await message.answer(
            "👋 به سیستم مدیریت VPN خوش آمدید.\n\n"
            "برای دریافت اشتراک با نماینده خود تماس بگیرید."
        )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext, db_user: User) -> None:
    current = await state.get_state()
    if current is not None:
        await state.clear()
        await message.answer("❌ عملیات لغو شد.")
    else:
        await message.answer("عملیات فعالی وجود ندارد.")
