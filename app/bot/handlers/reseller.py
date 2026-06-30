"""
Reseller Telegram handlers.
All text is in Persian.
"""

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.reseller import (
    cancel_keyboard,
    customer_detail_keyboard,
    customer_list_keyboard,
    duration_keyboard,
    reseller_main_menu,
)
from app.bot.states.reseller import CreateSubscriptionStates, RenewSubscriptionStates
from app.models.server import Server
from app.models.user import User, UserRole
from app.repositories.customer import CustomerRepository
from app.repositories.reseller import ResellerRepository
from app.repositories.subscription import SaleRepository
from app.services.subscription import SubscriptionService
from app.utils.persian import format_gb, format_price

router = Router(name="reseller")


def _require_reseller(db_user: User) -> bool:
    return db_user.role in (UserRole.RESELLER, UserRole.ADMIN)


async def _get_default_server(session: AsyncSession) -> Server | None:
    result = await session.execute(
        select(Server).where(Server.active == True).limit(1)
    )
    return result.scalar_one_or_none()


# ── Credit ───────────────────────────────────────────────────────────────────

@router.message(F.text == "💰 اعتبار من")
async def my_credit(message: Message, db_user: User, db_session: AsyncSession) -> None:
    if not _require_reseller(db_user):
        return await message.answer("⛔ دسترسی ندارید")
    repo = ResellerRepository(db_session)
    reseller = await repo.get_by_user_id(db_user.id)
    if not reseller:
        return await message.answer("❌ پروفایل نماینده یافت نشد.")
    await message.answer(
        f"💰 اعتبار حساب شما\n\n"
        f"💾 اعتبار کل: {format_gb(float(reseller.credit_gb))}\n"
        f"📤 مصرف شده: {format_gb(float(reseller.used_gb))}\n"
        f"📦 باقی‌مانده: {format_gb(float(reseller.remaining_credit_gb))}\n"
        f"💵 قیمت هر گیگ: {format_price(float(reseller.price_per_gb))}\n"
        f"{'✅ فعال' if reseller.active else '❌ غیرفعال'}"
    )


# ── Create Subscription FSM ──────────────────────────────────────────────────

@router.message(F.text == "➕ ساخت اشتراک")
async def create_sub_start(message: Message, db_user: User, state: FSMContext) -> None:
    if not _require_reseller(db_user):
        return await message.answer("⛔ دسترسی ندارید")
    await state.set_state(CreateSubscriptionStates.waiting_customer_name)
    await message.answer(
        "➕ ساخت اشتراک جدید\n\n"
        "نام مشتری را وارد کنید:",
        reply_markup=cancel_keyboard(),
    )


@router.message(CreateSubscriptionStates.waiting_customer_name)
async def create_sub_name(message: Message, state: FSMContext) -> None:
    if not message.text or len(message.text.strip()) < 2:
        return await message.answer("❌ نام خیلی کوتاه است:")
    await state.update_data(customer_name=message.text.strip())
    await state.set_state(CreateSubscriptionStates.waiting_volume_gb)
    await message.answer("حجم اشتراک را به گیگابایت وارد کنید:\nمثال: 50")


@router.message(CreateSubscriptionStates.waiting_volume_gb)
async def create_sub_volume(message: Message, state: FSMContext, db_user: User, db_session: AsyncSession) -> None:
    try:
        gb = float(message.text.strip())
        assert gb > 0
    except (ValueError, AssertionError):
        return await message.answer("❌ مقدار نامعتبر. یک عدد مثبت وارد کنید:")

    # Early credit check
    repo = ResellerRepository(db_session)
    reseller = await repo.get_by_user_id(db_user.id)
    if reseller and float(reseller.remaining_credit_gb) < gb:
        return await message.answer(
            f"❌ موجودی کافی نیست\n\n"
            f"اعتبار باقی‌مانده: {format_gb(float(reseller.remaining_credit_gb))}\n"
            f"درخواست شما: {format_gb(gb)}"
        )

    await state.update_data(volume_gb=gb)
    await state.set_state(CreateSubscriptionStates.waiting_duration)
    await message.answer("مدت اشتراک را انتخاب کنید:", reply_markup=duration_keyboard())


@router.callback_query(F.data.startswith("duration:"), CreateSubscriptionStates.waiting_duration)
async def create_sub_duration(callback: CallbackQuery, state: FSMContext) -> None:
    days = int(callback.data.split(":")[1])
    await state.update_data(duration_days=days)
    data = await state.get_data()
    await state.set_state(CreateSubscriptionStates.confirm)
    await callback.message.edit_text(
        f"📋 تأیید ساخت اشتراک\n\n"
        f"👤 مشتری: {data['customer_name']}\n"
        f"💾 حجم: {format_gb(data['volume_gb'])}\n"
        f"⏳ مدت: {days} روز\n\n"
        f"آیا تأیید می‌کنید؟",
        reply_markup=_confirm_inline(),
    )


def _confirm_inline():
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ تأیید", callback_data="sub:confirm"),
        InlineKeyboardButton(text="❌ انصراف", callback_data="cancel"),
    ]])


@router.callback_query(F.data == "sub:confirm", CreateSubscriptionStates.confirm)
async def create_sub_confirm(callback: CallbackQuery, state: FSMContext, db_user: User, db_session: AsyncSession) -> None:
    data = await state.get_data()
    await state.clear()

    server = await _get_default_server(db_session)
    if not server:
        return await callback.message.edit_text("❌ هیچ سروری پیکربندی نشده است. با ادمین تماس بگیرید.")

    await callback.message.edit_text("⏳ در حال ساخت اشتراک...")
    try:
        service = SubscriptionService(db_session)
        customer, sub, link = await service.create_subscription(
            reseller_user_id=db_user.id,
            customer_name=data["customer_name"],
            volume_gb=data["volume_gb"],
            duration_days=data["duration_days"],
            server=server,
        )
        await db_session.commit()
        await callback.message.edit_text(
            f"✅ اشتراک با موفقیت ساخته شد\n\n"
            f"👤 مشتری: {customer.name}\n"
            f"💾 حجم: {format_gb(float(customer.volume_gb))}\n"
            f"⏳ مدت: {data['duration_days']} روز\n"
            f"📅 تاریخ انقضا: {customer.expire_date.strftime('%Y-%m-%d')}\n\n"
            f"🔗 لینک اتصال:\n<code>{link}</code>",
            parse_mode="HTML",
        )
    except ValueError as e:
        await callback.message.edit_text(f"❌ {e}")
    except Exception as exc:
        await callback.message.edit_text("❌ خطایی رخ داد. لطفاً دوباره تلاش کنید.")


# ── Customer List ────────────────────────────────────────────────────────────

@router.message(F.text == "👥 مشتری‌های من")
async def my_customers(message: Message, db_user: User, db_session: AsyncSession) -> None:
    if not _require_reseller(db_user):
        return await message.answer("⛔ دسترسی ندارید")
    repo = ResellerRepository(db_session)
    reseller = await repo.get_by_user_id(db_user.id)
    if not reseller:
        return await message.answer("❌ پروفایل نماینده یافت نشد.")
    customer_repo = CustomerRepository(db_session)
    customers = await customer_repo.list_by_reseller(reseller.id)
    if not customers:
        return await message.answer("هیچ مشتری‌ای ثبت نشده است.")
    await message.answer(
        f"👥 مشتری‌های شما ({len(customers)} نفر):",
        reply_markup=customer_list_keyboard(customers),
    )


@router.callback_query(F.data.startswith("customer:page:"))
async def customer_page(callback: CallbackQuery, db_user: User, db_session: AsyncSession) -> None:
    page = int(callback.data.split(":")[2])
    repo = ResellerRepository(db_session)
    reseller = await repo.get_by_user_id(db_user.id)
    customer_repo = CustomerRepository(db_session)
    customers = await customer_repo.list_by_reseller(reseller.id)
    await callback.message.edit_reply_markup(reply_markup=customer_list_keyboard(customers, page))


@router.callback_query(F.data.startswith("customer:detail:"))
async def customer_detail(callback: CallbackQuery, db_user: User, db_session: AsyncSession) -> None:
    customer_id = int(callback.data.split(":")[2])
    repo = ResellerRepository(db_session)
    reseller = await repo.get_by_user_id(db_user.id)
    customer_repo = CustomerRepository(db_session)
    customer = await customer_repo.get(customer_id)

    if not customer or customer.reseller_id != reseller.id:
        return await callback.answer("⛔ دسترسی ندارید", show_alert=True)

    status_map = {"ACTIVE": "✅ فعال", "EXPIRED": "⏰ منقضی", "DISABLED": "🚫 غیرفعال", "TRAFFIC_EXHAUSTED": "📵 تمام شده"}
    expire_str = customer.expire_date.strftime("%Y-%m-%d") if customer.expire_date else "نامشخص"
    await callback.message.edit_text(
        f"👤 مشخصات مشتری\n\n"
        f"🔤 نام: {customer.name}\n"
        f"📧 ایمیل: {customer.email}\n"
        f"💾 حجم: {format_gb(float(customer.volume_gb))}\n"
        f"📊 مصرف: {format_gb(float(customer.used_gb))} ({customer.traffic_percent:.1f}٪)\n"
        f"📅 انقضا: {expire_str}\n"
        f"🔵 وضعیت: {status_map.get(customer.status, customer.status)}",
        reply_markup=customer_detail_keyboard(customer_id),
    )


@router.callback_query(F.data.startswith("customer:link:"))
async def customer_link(callback: CallbackQuery, db_user: User, db_session: AsyncSession) -> None:
    customer_id = int(callback.data.split(":")[2])
    repo = ResellerRepository(db_session)
    reseller = await repo.get_by_user_id(db_user.id)
    from app.repositories.subscription import SubscriptionRepository
    sub_repo = SubscriptionRepository(db_session)
    sub = await sub_repo.get_active_by_customer(customer_id)
    if not sub:
        return await callback.answer("لینک یافت نشد", show_alert=True)
    customer_repo = CustomerRepository(db_session)
    customer = await customer_repo.get(customer_id)
    if not customer or customer.reseller_id != reseller.id:
        return await callback.answer("⛔ دسترسی ندارید", show_alert=True)
    await callback.message.answer(
        f"🔗 لینک اتصال:\n<code>{sub.link}</code>",
        parse_mode="HTML",
    )
    await callback.answer()


# ── Sales Report ─────────────────────────────────────────────────────────────

@router.message(F.text == "📊 گزارش فروش")
async def sales_report(message: Message, db_user: User, db_session: AsyncSession) -> None:
    if not _require_reseller(db_user):
        return await message.answer("⛔ دسترسی ندارید")
    repo = ResellerRepository(db_session)
    reseller = await repo.get_by_user_id(db_user.id)
    if not reseller:
        return await message.answer("❌ پروفایل نماینده یافت نشد.")
    sale_repo = SaleRepository(db_session)
    total_amount, total_gb = await sale_repo.total_sales_by_reseller(reseller.id)
    recent_sales = await sale_repo.list_by_reseller(reseller.id, limit=10)

    lines = [
        "📊 گزارش فروش شما\n",
        f"💰 کل درآمد: {format_price(float(total_amount or 0))}",
        f"📦 کل فروش: {format_gb(float(total_gb or 0))}\n",
        "🕐 آخرین فروش‌ها:",
    ]
    for s in recent_sales:
        name = s.customer.name if s.customer else "?"
        lines.append(f"  • {name} — {format_gb(float(s.gb))} — {format_price(float(s.amount))}")

    await message.answer("\n".join(lines))


# ── Cancel ───────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "cancel")
async def cancel_handler(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("❌ عملیات لغو شد.")
