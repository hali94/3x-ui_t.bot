"""
Admin Telegram handlers.

All text visible to users is in Persian.
"""

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.admin import (
    admin_main_menu,
    confirm_keyboard,
    reseller_list_keyboard,
    reseller_management_menu,
    server_management_menu,
)
from app.bot.states.admin import AddCreditStates, AddServerStates, CreateResellerStates
from app.models.server import Server
from app.models.user import User, UserRole
from app.repositories.reseller import ResellerRepository
from app.repositories.user import UserRepository
from app.security.encryption import encrypt_value
from app.services.reseller import ResellerService

router = Router(name="admin")


def _require_admin(db_user: User) -> bool:
    return db_user.role == UserRole.ADMIN


# ── Main menu text handlers ──────────────────────────────────────────────────

@router.message(F.text == "👥 مدیریت نمایندگان")
async def reseller_menu(message: Message, db_user: User) -> None:
    if not _require_admin(db_user):
        return await message.answer("⛔ دسترسی ندارید")
    await message.answer("مدیریت نمایندگان:", reply_markup=reseller_management_menu())


@router.message(F.text == "🖥 مدیریت سرورها")
async def server_menu(message: Message, db_user: User) -> None:
    if not _require_admin(db_user):
        return await message.answer("⛔ دسترسی ندارید")
    await message.answer("مدیریت سرورها:", reply_markup=server_management_menu())


@router.message(F.text == "📊 گزارش فروش")
async def sales_report(message: Message, db_user: User, db_session: AsyncSession) -> None:
    if not _require_admin(db_user):
        return await message.answer("⛔ دسترسی ندارید")
    repo = ResellerRepository(db_session)
    resellers = await repo.list_active()
    if not resellers:
        return await message.answer("هیچ نماینده‌ای یافت نشد.")
    lines = ["📊 گزارش فروش نمایندگان\n"]
    for r in resellers:
        name = r.user.full_name if r.user else f"ID:{r.id}"
        lines.append(
            f"👤 {name}\n"
            f"   💾 اعتبار کل: {r.credit_gb:.2f} GB\n"
            f"   📤 فروخته شده: {r.used_gb:.2f} GB\n"
            f"   📦 باقی‌مانده: {r.remaining_credit_gb:.2f} GB\n"
        )
    await message.answer("\n".join(lines))


# ── Create Reseller FSM ──────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:reseller:create")
async def reseller_create_start(callback: CallbackQuery, db_user: User, state: FSMContext) -> None:
    if not _require_admin(db_user):
        return await callback.answer("⛔ دسترسی ندارید", show_alert=True)
    await state.set_state(CreateResellerStates.waiting_telegram_id)
    await callback.message.edit_text(
        "➕ ساخت نماینده جدید\n\n"
        "آیدی تلگرام نماینده را وارد کنید (عدد):\n"
        "مثال: 123456789"
    )


@router.message(CreateResellerStates.waiting_telegram_id)
async def reseller_create_telegram_id(message: Message, state: FSMContext, db_user: User) -> None:
    if not message.text or not message.text.strip().isdigit():
        return await message.answer("❌ آیدی تلگرام باید یک عدد باشد. لطفاً دوباره وارد کنید:")
    await state.update_data(telegram_id=int(message.text.strip()))
    await state.set_state(CreateResellerStates.waiting_full_name)
    await message.answer("نام کامل نماینده را وارد کنید:")


@router.message(CreateResellerStates.waiting_full_name)
async def reseller_create_name(message: Message, state: FSMContext) -> None:
    if not message.text or len(message.text.strip()) < 2:
        return await message.answer("❌ نام خیلی کوتاه است. دوباره وارد کنید:")
    await state.update_data(full_name=message.text.strip())
    await state.set_state(CreateResellerStates.waiting_credit_gb)
    await message.answer("اعتبار اولیه (گیگابایت) را وارد کنید:\nمثال: 500")


@router.message(CreateResellerStates.waiting_credit_gb)
async def reseller_create_credit(message: Message, state: FSMContext) -> None:
    try:
        gb = float(message.text.strip())
        assert gb > 0
    except (ValueError, AssertionError):
        return await message.answer("❌ مقدار نامعتبر. یک عدد مثبت وارد کنید:")
    await state.update_data(credit_gb=gb)
    await state.set_state(CreateResellerStates.waiting_price_per_gb)
    await message.answer("قیمت هر گیگابایت (تومان) را وارد کنید:\nمثال: 20000")


@router.message(CreateResellerStates.waiting_price_per_gb)
async def reseller_create_price(message: Message, state: FSMContext) -> None:
    try:
        price = float(message.text.strip())
        assert price >= 0
    except (ValueError, AssertionError):
        return await message.answer("❌ مقدار نامعتبر. یک عدد مثبت وارد کنید:")
    await state.update_data(price_per_gb=price)
    await state.set_state(CreateResellerStates.waiting_max_sale_gb)
    await message.answer("حداکثر سقف فروش (گیگابایت) را وارد کنید:\nمثال: 200")


@router.message(CreateResellerStates.waiting_max_sale_gb)
async def reseller_create_max_sale(message: Message, state: FSMContext) -> None:
    try:
        max_gb = float(message.text.strip())
        assert max_gb > 0
    except (ValueError, AssertionError):
        return await message.answer("❌ مقدار نامعتبر:")
    await state.update_data(max_sale_limit_gb=max_gb)
    await state.set_state(CreateResellerStates.confirm)
    data = await state.get_data()
    text = (
        f"📋 تأیید ساخت نماینده\n\n"
        f"🆔 آیدی تلگرام: {data['telegram_id']}\n"
        f"👤 نام: {data['full_name']}\n"
        f"💾 اعتبار: {data['credit_gb']} GB\n"
        f"💰 قیمت هر GB: {data['price_per_gb']:,.0f} تومان\n"
        f"📊 سقف فروش: {data['max_sale_limit_gb']} GB\n\n"
        f"آیا تأیید می‌کنید؟"
    )
    await message.answer(text, reply_markup=confirm_keyboard("admin:reseller:create:confirm", "admin:reseller:create:cancel"))


@router.callback_query(F.data == "admin:reseller:create:confirm", CreateResellerStates.confirm)
async def reseller_create_confirm(callback: CallbackQuery, state: FSMContext, db_user: User, db_session: AsyncSession) -> None:
    data = await state.get_data()
    await state.clear()
    try:
        service = ResellerService(db_session)
        user, reseller = await service.create_reseller(
            telegram_id=data["telegram_id"],
            full_name=data["full_name"],
            credit_gb=data["credit_gb"],
            price_per_gb=data["price_per_gb"],
            max_sale_limit_gb=data["max_sale_limit_gb"],
            admin_user_id=db_user.id,
        )
        await db_session.commit()
        await callback.message.edit_text(
            f"✅ نماینده با موفقیت ساخته شد\n\n"
            f"👤 نام: {user.full_name}\n"
            f"💾 اعتبار: {reseller.credit_gb} GB"
        )
    except ValueError as e:
        await callback.message.edit_text(f"❌ خطا: {e}")
    except Exception:
        await callback.message.edit_text("❌ خطایی رخ داد. لطفاً دوباره تلاش کنید.")


@router.callback_query(F.data == "admin:reseller:create:cancel")
async def reseller_create_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("❌ عملیات لغو شد.")


# ── List Resellers ───────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:reseller:list")
async def reseller_list(callback: CallbackQuery, db_user: User, db_session: AsyncSession) -> None:
    if not _require_admin(db_user):
        return await callback.answer("⛔ دسترسی ندارید", show_alert=True)
    repo = ResellerRepository(db_session)
    resellers = await repo.list_active()
    if not resellers:
        return await callback.message.edit_text("هیچ نماینده‌ای یافت نشد.", reply_markup=reseller_management_menu())
    await callback.message.edit_text("📋 لیست نمایندگان:", reply_markup=reseller_list_keyboard(resellers))


# ── Add Credit FSM ───────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:reseller:add_credit")
async def add_credit_start(callback: CallbackQuery, db_user: User, state: FSMContext) -> None:
    if not _require_admin(db_user):
        return await callback.answer("⛔ دسترسی ندارید", show_alert=True)
    await state.set_state(AddCreditStates.waiting_reseller_id)
    await callback.message.edit_text("آیدی نماینده را وارد کنید (عدد):")


@router.message(AddCreditStates.waiting_reseller_id)
async def add_credit_reseller_id(message: Message, state: FSMContext) -> None:
    if not message.text or not message.text.strip().isdigit():
        return await message.answer("❌ آیدی نامعتبر:")
    await state.update_data(reseller_id=int(message.text.strip()))
    await state.set_state(AddCreditStates.waiting_amount_gb)
    await message.answer("مقدار اعتبار (گیگابایت) را وارد کنید:")


@router.message(AddCreditStates.waiting_amount_gb)
async def add_credit_amount(message: Message, state: FSMContext) -> None:
    try:
        gb = float(message.text.strip())
        assert gb > 0
    except (ValueError, AssertionError):
        return await message.answer("❌ مقدار نامعتبر:")
    await state.update_data(gb=gb)
    await state.set_state(AddCreditStates.confirm)
    data = await state.get_data()
    await message.answer(
        f"📋 تأیید افزایش اعتبار\n\nنماینده #{data['reseller_id']}: {gb} گیگابایت\n\nآیا تأیید می‌کنید؟",
        reply_markup=confirm_keyboard("admin:credit:confirm", "admin:credit:cancel"),
    )


@router.callback_query(F.data == "admin:credit:confirm", AddCreditStates.confirm)
async def add_credit_confirm(callback: CallbackQuery, state: FSMContext, db_user: User, db_session: AsyncSession) -> None:
    data = await state.get_data()
    await state.clear()
    service = ResellerService(db_session)
    try:
        reseller = await service.add_credit(data["reseller_id"], data["gb"], admin_user_id=db_user.id)
        await db_session.commit()
        await callback.message.edit_text(
            f"✅ اعتبار با موفقیت افزوده شد\n\n"
            f"💾 اعتبار کل: {reseller.credit_gb} GB\n"
            f"📦 باقی‌مانده: {reseller.remaining_credit_gb} GB"
        )
    except ValueError as e:
        await callback.message.edit_text(f"❌ {e}")


@router.callback_query(F.data == "admin:credit:cancel")
async def add_credit_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("❌ عملیات لغو شد.")


# ── Add Server FSM ───────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:server:add")
async def server_add_start(callback: CallbackQuery, db_user: User, state: FSMContext) -> None:
    if not _require_admin(db_user):
        return await callback.answer("⛔ دسترسی ندارید", show_alert=True)
    await state.set_state(AddServerStates.waiting_name)
    await callback.message.edit_text("نام سرور را وارد کنید:\nمثال: سرور ایران ۱")


@router.message(AddServerStates.waiting_name)
async def server_name(message: Message, state: FSMContext) -> None:
    await state.update_data(name=message.text.strip())
    await state.set_state(AddServerStates.waiting_url)
    await message.answer("آدرس پنل 3x-ui را وارد کنید:\nمثال: http://1.2.3.4:54321")


@router.message(AddServerStates.waiting_url)
async def server_url(message: Message, state: FSMContext) -> None:
    url = message.text.strip()
    if not url.startswith("http"):
        return await message.answer("❌ آدرس باید با http یا https شروع شود:")
    await state.update_data(xui_url=url)
    await state.set_state(AddServerStates.waiting_username)
    await message.answer("نام کاربری پنل 3x-ui را وارد کنید:")


@router.message(AddServerStates.waiting_username)
async def server_username(message: Message, state: FSMContext) -> None:
    await state.update_data(xui_username=message.text.strip())
    await state.set_state(AddServerStates.waiting_password)
    await message.answer("رمز عبور پنل 3x-ui را وارد کنید:")


@router.message(AddServerStates.waiting_password)
async def server_password(message: Message, state: FSMContext) -> None:
    await state.update_data(xui_password=message.text.strip())
    await state.set_state(AddServerStates.waiting_inbound_id)
    await message.answer("آیدی Inbound پیش‌فرض را وارد کنید (عدد):\nمثال: 1")


@router.message(AddServerStates.waiting_inbound_id)
async def server_inbound(message: Message, state: FSMContext) -> None:
    if not message.text or not message.text.strip().isdigit():
        return await message.answer("❌ آیدی نامعتبر:")
    await state.update_data(inbound_id=int(message.text.strip()))
    data = await state.get_data()
    await state.set_state(AddServerStates.confirm)
    await message.answer(
        f"📋 تأیید افزودن سرور\n\n"
        f"🖥 نام: {data['name']}\n"
        f"🌐 آدرس: {data['xui_url']}\n"
        f"👤 کاربر: {data['xui_username']}\n"
        f"🔌 Inbound: {data['inbound_id']}\n\n"
        f"آیا تأیید می‌کنید؟",
        reply_markup=confirm_keyboard("admin:server:confirm", "admin:server:cancel"),
    )


@router.callback_query(F.data == "admin:server:confirm", AddServerStates.confirm)
async def server_confirm(callback: CallbackQuery, state: FSMContext, db_user: User, db_session: AsyncSession) -> None:
    data = await state.get_data()
    await state.clear()
    server = Server(
        name=data["name"],
        xui_url=data["xui_url"],
        xui_username=data["xui_username"],
        default_inbound_id=data["inbound_id"],
        active=True,
    )
    server.xui_password = data["xui_password"]
    db_session.add(server)
    await db_session.commit()
    await callback.message.edit_text(f"✅ سرور «{server.name}» با موفقیت اضافه شد.")


@router.callback_query(F.data == "admin:server:cancel")
async def server_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("❌ عملیات لغو شد.")
