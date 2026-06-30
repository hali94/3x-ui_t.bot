"""
Admin Telegram handlers.

All text visible to users is in Persian.
Permission is checked server-side on every handler.
"""

from aiogram import Router, F
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
from app.models.user import User
from app.repositories.reseller import ResellerRepository
from app.repositories.subscription import SaleRepository
from app.security.rbac import bot_is_admin
from app.services.reseller import ResellerService
from app.utils.persian import format_gb, format_price

router = Router(name="admin")


def _guard(db_user: User) -> bool:
    return bot_is_admin(db_user)


# ── Main text buttons ────────────────────────────────────────────────────────

@router.message(F.text == "👥 مدیریت نمایندگان")
async def reseller_menu(message: Message, db_user: User) -> None:
    if not _guard(db_user):
        return await message.answer("⛔ دسترسی ندارید")
    await message.answer("مدیریت نمایندگان:", reply_markup=reseller_management_menu())


@router.message(F.text == "🖥 مدیریت سرورها")
async def server_menu(message: Message, db_user: User) -> None:
    if not _guard(db_user):
        return await message.answer("⛔ دسترسی ندارید")
    await message.answer("مدیریت سرورها:", reply_markup=server_management_menu())


@router.message(F.text == "📊 گزارش فروش")
async def admin_sales_report(message: Message, db_user: User, db_session: AsyncSession) -> None:
    if not _guard(db_user):
        return await message.answer("⛔ دسترسی ندارید")
    repo = ResellerRepository(db_session)
    resellers = await repo.list_active()
    if not resellers:
        return await message.answer("هیچ نماینده‌ای یافت نشد.")

    sale_repo = SaleRepository(db_session)
    lines = ["📊 گزارش فروش کل سیستم\n"]
    grand_total = grand_gb = grand_profit = 0.0

    for r in resellers:
        name = r.user.full_name if r.user else f"ID:{r.id}"
        level_tag = "سطح ۱" if r.is_level_1 else "سطح ۲"
        total_amount, total_gb, total_profit = await sale_repo.total_sales_by_reseller(r.id)
        grand_total += float(total_amount)
        grand_gb += float(total_gb)
        grand_profit += float(total_profit)
        lines.append(
            f"👤 {name} [{level_tag}]\n"
            f"   💾 فروش: {format_gb(float(total_gb))}\n"
            f"   💰 درآمد: {format_price(float(total_amount))}\n"
            f"   📦 موجودی: {format_gb(float(r.remaining_credit_gb))}\n"
        )

    lines.append(
        f"\n{'─'*20}\n"
        f"📦 جمع کل حجم: {format_gb(grand_gb)}\n"
        f"💰 جمع کل درآمد: {format_price(grand_total)}\n"
        f"📈 جمع سود: {format_price(grand_profit)}"
    )
    await message.answer("\n".join(lines))


# ── Create L1 Reseller FSM ───────────────────────────────────────────────────

@router.callback_query(F.data == "admin:reseller:create")
async def reseller_create_start(callback: CallbackQuery, db_user: User, state: FSMContext) -> None:
    if not _guard(db_user):
        return await callback.answer("⛔ دسترسی ندارید", show_alert=True)
    await state.set_state(CreateResellerStates.waiting_telegram_id)
    await callback.message.edit_text(
        "➕ ساخت نماینده سطح ۱\n\nآیدی عددی تلگرام را وارد کنید:"
    )


@router.message(CreateResellerStates.waiting_telegram_id)
async def reseller_create_tgid(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text.isdigit():
        return await message.answer("❌ آیدی باید یک عدد باشد:")
    await state.update_data(telegram_id=int(text))
    await state.set_state(CreateResellerStates.waiting_full_name)
    await message.answer("نام کامل نماینده را وارد کنید:")


@router.message(CreateResellerStates.waiting_full_name)
async def reseller_create_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if len(name) < 2:
        return await message.answer("❌ نام خیلی کوتاه است:")
    await state.update_data(full_name=name)
    await state.set_state(CreateResellerStates.waiting_credit_gb)
    await message.answer("اعتبار اولیه (گیگابایت) را وارد کنید:\nمثال: 1000")


@router.message(CreateResellerStates.waiting_credit_gb)
async def reseller_create_credit(message: Message, state: FSMContext) -> None:
    try:
        gb = float((message.text or "").strip())
        assert gb > 0
    except (ValueError, AssertionError):
        return await message.answer("❌ مقدار نامعتبر:")
    await state.update_data(credit_gb=gb)
    await state.set_state(CreateResellerStates.waiting_price_per_gb)
    await message.answer("قیمت خرید هر گیگ از سیستم (تومان):\nمثال: 10000")


@router.message(CreateResellerStates.waiting_price_per_gb)
async def reseller_create_buy_price(message: Message, state: FSMContext) -> None:
    try:
        price = float((message.text or "").strip())
        assert price >= 0
    except (ValueError, AssertionError):
        return await message.answer("❌ قیمت نامعتبر:")
    await state.update_data(buy_price_per_gb=price)
    await state.set_state(CreateResellerStates.waiting_max_sale_gb)
    await message.answer("قیمت فروش هر گیگ توسط نماینده (تومان):\nمثال: 15000")


@router.message(CreateResellerStates.waiting_max_sale_gb)
async def reseller_create_sell_price(message: Message, state: FSMContext) -> None:
    try:
        price = float((message.text or "").strip())
        assert price >= 0
    except (ValueError, AssertionError):
        return await message.answer("❌ قیمت نامعتبر:")
    await state.update_data(sell_price_per_gb=price)
    await state.set_state(CreateResellerStates.confirm)
    data = await state.get_data()
    await message.answer(
        f"📋 تأیید ساخت نماینده سطح ۱\n\n"
        f"🆔 آیدی: {data['telegram_id']}\n"
        f"👤 نام: {data['full_name']}\n"
        f"💾 اعتبار: {format_gb(data['credit_gb'])}\n"
        f"💵 قیمت خرید: {format_price(data['buy_price_per_gb'])} / گیگ\n"
        f"💰 قیمت فروش: {format_price(data['sell_price_per_gb'])} / گیگ\n\n"
        f"آیا تأیید می‌کنید؟",
        reply_markup=confirm_keyboard("admin:reseller:create:confirm", "admin:reseller:create:cancel"),
    )


@router.callback_query(F.data == "admin:reseller:create:confirm", CreateResellerStates.confirm)
async def reseller_create_confirm(
    callback: CallbackQuery, state: FSMContext, db_user: User, db_session: AsyncSession
) -> None:
    data = await state.get_data()
    await state.clear()
    try:
        service = ResellerService(db_session)
        user, reseller = await service.create_level1_reseller(
            telegram_id=data["telegram_id"],
            full_name=data["full_name"],
            credit_gb=data["credit_gb"],
            buy_price_per_gb=data.get("buy_price_per_gb", 0),
            sell_price_per_gb=data.get("sell_price_per_gb", 0),
            admin_user_id=db_user.id,
        )
        await db_session.commit()
        await callback.message.edit_text(
            f"✅ نماینده سطح ۱ با موفقیت ساخته شد\n\n"
            f"👤 نام: {user.full_name}\n"
            f"💾 اعتبار: {format_gb(float(reseller.credit_gb))}"
        )
    except ValueError as exc:
        await db_session.rollback()
        await callback.message.edit_text(f"❌ {exc}")
    except Exception:
        await db_session.rollback()
        await callback.message.edit_text("❌ خطایی رخ داد.")


@router.callback_query(F.data == "admin:reseller:create:cancel")
async def reseller_create_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("❌ عملیات لغو شد.")


# ── List Resellers ───────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:reseller:list")
async def reseller_list(callback: CallbackQuery, db_user: User, db_session: AsyncSession) -> None:
    if not _guard(db_user):
        return await callback.answer("⛔ دسترسی ندارید", show_alert=True)
    repo = ResellerRepository(db_session)
    resellers = await repo.list_active()
    if not resellers:
        return await callback.message.edit_text(
            "هیچ نماینده‌ای یافت نشد.", reply_markup=reseller_management_menu()
        )
    await callback.message.edit_text("📋 لیست نمایندگان:", reply_markup=reseller_list_keyboard(resellers))


# ── Add Credit FSM ───────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:reseller:add_credit")
async def add_credit_start(callback: CallbackQuery, db_user: User, state: FSMContext) -> None:
    if not _guard(db_user):
        return await callback.answer("⛔ دسترسی ندارید", show_alert=True)
    await state.set_state(AddCreditStates.waiting_reseller_id)
    await callback.message.edit_text("آیدی نماینده سطح ۱ را وارد کنید (عدد):")


@router.message(AddCreditStates.waiting_reseller_id)
async def add_credit_reseller_id(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text.isdigit():
        return await message.answer("❌ آیدی نامعتبر:")
    await state.update_data(reseller_id=int(text))
    await state.set_state(AddCreditStates.waiting_amount_gb)
    await message.answer("مقدار اعتبار (گیگابایت) را وارد کنید:")


@router.message(AddCreditStates.waiting_amount_gb)
async def add_credit_amount(message: Message, state: FSMContext) -> None:
    try:
        gb = float((message.text or "").strip())
        assert gb > 0
    except (ValueError, AssertionError):
        return await message.answer("❌ مقدار نامعتبر:")
    await state.update_data(gb=gb)
    await state.set_state(AddCreditStates.confirm)
    data = await state.get_data()
    await message.answer(
        f"📋 تأیید افزایش اعتبار\n\nنماینده #{data['reseller_id']}: {format_gb(gb)}\n\nتأیید می‌کنید؟",
        reply_markup=confirm_keyboard("admin:credit:confirm", "admin:credit:cancel"),
    )


@router.callback_query(F.data == "admin:credit:confirm", AddCreditStates.confirm)
async def add_credit_confirm(
    callback: CallbackQuery, state: FSMContext, db_user: User, db_session: AsyncSession
) -> None:
    data = await state.get_data()
    await state.clear()
    try:
        service = ResellerService(db_session)
        reseller = await service.add_credit_to_reseller(
            data["reseller_id"], data["gb"], actor_user_id=db_user.id
        )
        await db_session.commit()
        await callback.message.edit_text(
            f"✅ اعتبار افزوده شد\n\n"
            f"💾 اعتبار کل: {format_gb(float(reseller.credit_gb))}\n"
            f"✅ باقی‌مانده: {format_gb(float(reseller.remaining_credit_gb))}"
        )
    except ValueError as exc:
        await db_session.rollback()
        await callback.message.edit_text(f"❌ {exc}")


@router.callback_query(F.data == "admin:credit:cancel")
async def add_credit_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("❌ عملیات لغو شد.")


# ── Deactivate Reseller ───────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:reseller:deactivate")
async def reseller_deactivate_start(callback: CallbackQuery, db_user: User, state: FSMContext) -> None:
    if not _guard(db_user):
        return await callback.answer("⛔ دسترسی ندارید", show_alert=True)
    await state.set_state(AddCreditStates.waiting_reseller_id)
    await state.update_data(action="deactivate")
    await callback.message.edit_text("آیدی نماینده برای غیرفعال کردن را وارد کنید:")


# ── Add Server FSM ───────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:server:add")
async def server_add_start(callback: CallbackQuery, db_user: User, state: FSMContext) -> None:
    if not _guard(db_user):
        return await callback.answer("⛔ دسترسی ندارید", show_alert=True)
    await state.set_state(AddServerStates.waiting_name)
    await callback.message.edit_text("نام سرور را وارد کنید:\nمثال: سرور ایران ۱")


@router.message(AddServerStates.waiting_name)
async def server_name(message: Message, state: FSMContext) -> None:
    await state.update_data(name=(message.text or "").strip())
    await state.set_state(AddServerStates.waiting_url)
    await message.answer("آدرس پنل 3x-ui:\nمثال: http://1.2.3.4:54321")


@router.message(AddServerStates.waiting_url)
async def server_url(message: Message, state: FSMContext) -> None:
    url = (message.text or "").strip()
    if not url.startswith("http"):
        return await message.answer("❌ آدرس باید با http شروع شود:")
    await state.update_data(xui_url=url)
    await state.set_state(AddServerStates.waiting_username)
    await message.answer("نام کاربری پنل 3x-ui:")


@router.message(AddServerStates.waiting_username)
async def server_username(message: Message, state: FSMContext) -> None:
    await state.update_data(xui_username=(message.text or "").strip())
    await state.set_state(AddServerStates.waiting_password)
    await message.answer("رمز عبور پنل 3x-ui:")


@router.message(AddServerStates.waiting_password)
async def server_password(message: Message, state: FSMContext) -> None:
    await state.update_data(xui_password=(message.text or "").strip())
    await state.set_state(AddServerStates.waiting_inbound_id)
    await message.answer("آیدی Inbound پیش‌فرض (عدد):\nمثال: 1")


@router.message(AddServerStates.waiting_inbound_id)
async def server_inbound(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text.isdigit():
        return await message.answer("❌ آیدی نامعتبر:")
    await state.update_data(inbound_id=int(text))
    data = await state.get_data()
    await state.set_state(AddServerStates.confirm)
    await message.answer(
        f"📋 تأیید افزودن سرور\n\n"
        f"🖥 نام: {data['name']}\n"
        f"🌐 آدرس: {data['xui_url']}\n"
        f"👤 کاربر: {data['xui_username']}\n"
        f"🔌 Inbound ID: {data['inbound_id']}\n\nتأیید می‌کنید؟",
        reply_markup=confirm_keyboard("admin:server:confirm", "admin:server:cancel"),
    )


@router.callback_query(F.data == "admin:server:confirm", AddServerStates.confirm)
async def server_confirm(
    callback: CallbackQuery, state: FSMContext, db_user: User, db_session: AsyncSession
) -> None:
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
    await callback.message.edit_text(f"✅ سرور «{server.name}» اضافه شد.")


@router.callback_query(F.data == "admin:server:cancel")
async def server_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("❌ عملیات لغو شد.")


@router.callback_query(F.data == "admin:server:list")
async def server_list(callback: CallbackQuery, db_user: User, db_session: AsyncSession) -> None:
    if not _guard(db_user):
        return await callback.answer("⛔ دسترسی ندارید", show_alert=True)
    from sqlalchemy import select
    result = await db_session.execute(select(Server).order_by(Server.created_at.desc()))
    servers = list(result.scalars().all())
    if not servers:
        return await callback.message.edit_text("هیچ سروری ثبت نشده.", reply_markup=server_management_menu())
    lines = ["🖥 لیست سرورها:\n"]
    for s in servers:
        lines.append(
            f"{'✅' if s.active else '❌'} {s.name}\n"
            f"   🌐 {s.xui_url}\n"
            f"   🔌 Inbound: {s.default_inbound_id}\n"
        )
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin:back")]]
        ),
    )


@router.callback_query(F.data == "admin:back")
async def admin_back(callback: CallbackQuery) -> None:
    await callback.message.delete()
    await callback.answer()
