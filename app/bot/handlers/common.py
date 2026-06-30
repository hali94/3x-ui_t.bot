from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from app.bot.keyboards.admin import admin_main_menu
from app.bot.keyboards.reseller import reseller_l1_menu, reseller_l2_menu
from app.models.user import User
from app.security.rbac import bot_is_admin, bot_is_l1, bot_is_reseller

router = Router(name="common")


@router.message(CommandStart())
async def cmd_start(message: Message, db_user: User, state: FSMContext) -> None:
    await state.clear()

    if bot_is_admin(db_user):
        await message.answer(
            f"🔧 خوش آمدید، {db_user.full_name}\n\nشما به عنوان مدیر اصلی وارد شدید.",
            reply_markup=admin_main_menu(),
        )
    elif bot_is_l1(db_user):
        await message.answer(
            f"👤 خوش آمدید، {db_user.full_name}\n\nپنل نماینده سطح ۱",
            reply_markup=reseller_l1_menu(),
        )
    elif bot_is_reseller(db_user):
        await message.answer(
            f"👤 خوش آمدید، {db_user.full_name}\n\nپنل نماینده سطح ۲",
            reply_markup=reseller_l2_menu(),
        )
    else:
        await message.answer(
            "👋 به سیستم مدیریت VPN خوش آمدید.\n\n"
            "برای دریافت اشتراک با نماینده خود تماس بگیرید."
        )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    current = await state.get_state()
    if current:
        await state.clear()
        await message.answer("❌ عملیات لغو شد.")
    else:
        await message.answer("عملیات فعالی وجود ندارد.")


@router.message(Command("menu"))
async def cmd_menu(message: Message, db_user: User) -> None:
    if bot_is_admin(db_user):
        await message.answer("منوی مدیر:", reply_markup=admin_main_menu())
    elif bot_is_l1(db_user):
        await message.answer("منوی نماینده سطح ۱:", reply_markup=reseller_l1_menu())
    elif bot_is_reseller(db_user):
        await message.answer("منوی نماینده سطح ۲:", reply_markup=reseller_l2_menu())
