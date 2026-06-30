"""
Reseller Telegram handlers — covers both Level 1 and Level 2.

All user-facing text is in Persian.
Permission is checked server-side on every handler, not just on menu display.
"""

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.reseller import (
    cancel_keyboard,
    child_reseller_detail_keyboard,
    child_reseller_list_keyboard,
    confirm_keyboard,
    customer_detail_keyboard,
    customer_list_keyboard,
    duration_keyboard,
    reseller_l1_menu,
    reseller_l2_menu,
)
from app.bot.states.reseller import (
    AllocateCreditStates,
    CreateL2ResellerStates,
    CreateSubscriptionStates,
    RenewSubscriptionStates,
)
from app.models.server import Server
from app.models.user import User
from app.repositories.customer import CustomerRepository
from app.repositories.reseller import ResellerRepository
from app.repositories.subscription import SaleRepository, SubscriptionRepository
from app.security.rbac import (
    bot_is_admin_or_l1,
    bot_is_l1,
    bot_is_reseller,
    check_reseller_owns_customer,
)
from app.services.notification import NotificationService
from app.services.reseller import ResellerService
from app.services.subscription import SubscriptionService
from app.utils.persian import format_gb, format_price

router = Router(name="reseller")

# ── Helpers ──────────────────────────────────────────────────────────────────


async def _get_default_server(session: AsyncSession) -> Server | None:
    result = await session.execute(
        select(Server).where(Server.active == True).limit(1)
    )
    return result.scalar_one_or_none()


async def _get_reseller(db_user: User, session: AsyncSession):
    repo = ResellerRepository(session)
    return await repo.get_by_user_id(db_user.id)


def _safe_int(s: str) -> int | None:
    try:
        return int(s)
    except (ValueError, TypeError):
        return None


# ── /start & menu routing ────────────────────────────────────────────────────


@router.message(F.text.in_(["👤 پنل نماینده سطح ۱", "👤 پنل نماینده سطح ۲"]))
async def reseller_panel(message: Message, db_user: User) -> None:
    if not bot_is_reseller(db_user):
        return await message.answer("⛔ دسترسی ندارید")
    if bot_is_l1(db_user):
        await message.answer("👤 پنل نماینده سطح ۱", reply_markup=reseller_l1_menu())
    else:
        await message.answer("👤 پنل نماینده سطح ۲", reply_markup=reseller_l2_menu())


# ── Credit info ──────────────────────────────────────────────────────────────


@router.message(F.text == "💳 اعتبار")
async def my_credit(message: Message, db_user: User, db_session: AsyncSession) -> None:
    if not bot_is_reseller(db_user):
        return await message.answer("⛔ دسترسی ندارید")
    reseller = await _get_reseller(db_user, db_session)
    if not reseller:
        return await message.answer("❌ پروفایل نماینده یافت نشد.")
    lines = [
        f"💳 اعتبار حساب شما\n",
        f"💾 اعتبار کل: {format_gb(float(reseller.credit_gb))}",
        f"📤 فروخته شده: {format_gb(float(reseller.used_gb))}",
    ]
    if reseller.is_level_1:
        lines.append(f"📦 تخصیص به زیرمجموعه‌ها: {format_gb(float(reseller.allocated_to_children_gb))}")
    lines += [
        f"✅ باقی‌مانده: {format_gb(float(reseller.remaining_credit_gb))}",
        f"💵 قیمت خرید هر گیگ: {format_price(float(reseller.buy_price_per_gb))}",
        f"💰 قیمت فروش هر گیگ: {format_price(float(reseller.sell_price_per_gb))}",
        f"\n{'✅ فعال' if reseller.active else '❌ غیرفعال'}",
    ]
    await message.answer("\n".join(lines))


# ── Create subscription FSM ──────────────────────────────────────────────────


@router.message(F.text == "➕ فروش اشتراک")
async def create_sub_start(message: Message, db_user: User, state: FSMContext) -> None:
    if not bot_is_reseller(db_user):
        return await message.answer("⛔ دسترسی ندارید")
    await state.set_state(CreateSubscriptionStates.waiting_customer_name)
    await message.answer(
        "➕ ساخت اشتراک جدید\n\nنام مشتری را وارد کنید:",
        reply_markup=cancel_keyboard(),
    )


@router.message(CreateSubscriptionStates.waiting_customer_name)
async def create_sub_name(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if len(text) < 2:
        return await message.answer("❌ نام خیلی کوتاه است. دوباره وارد کنید:")
    await state.update_data(customer_name=text)
    await state.set_state(CreateSubscriptionStates.waiting_volume_gb)
    await message.answer("حجم اشتراک را به گیگابایت وارد کنید:\nمثال: 50")


@router.message(CreateSubscriptionStates.waiting_volume_gb)
async def create_sub_volume(
    message: Message, state: FSMContext, db_user: User, db_session: AsyncSession
) -> None:
    try:
        gb = float((message.text or "").strip())
        if gb <= 0 or gb > 10_000:
            raise ValueError
    except ValueError:
        return await message.answer("❌ مقدار نامعتبر. یک عدد بین ۱ تا ۱۰۰۰۰ وارد کنید:")

    reseller = await _get_reseller(db_user, db_session)
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
    days_str = callback.data.split(":")[-1]
    days = _safe_int(days_str)
    if not days:
        return await callback.answer("❌ مقدار نامعتبر", show_alert=True)
    await state.update_data(duration_days=days)
    data = await state.get_data()
    await state.set_state(CreateSubscriptionStates.confirm)
    await callback.message.edit_text(
        f"📋 تأیید ساخت اشتراک\n\n"
        f"👤 مشتری: {data['customer_name']}\n"
        f"💾 حجم: {format_gb(data['volume_gb'])}\n"
        f"⏳ مدت: {days} روز\n\n"
        f"آیا تأیید می‌کنید؟",
        reply_markup=confirm_keyboard("sub:confirm"),
    )


@router.callback_query(F.data == "sub:confirm", CreateSubscriptionStates.confirm)
async def create_sub_confirm(
    callback: CallbackQuery, state: FSMContext, db_user: User, db_session: AsyncSession
) -> None:
    if not bot_is_reseller(db_user):
        await state.clear()
        return await callback.answer("⛔ دسترسی ندارید", show_alert=True)

    data = await state.get_data()
    await state.clear()

    server = await _get_default_server(db_session)
    if not server:
        return await callback.message.edit_text(
            "❌ هیچ سروری پیکربندی نشده است. با مدیر تماس بگیرید."
        )

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

        # Notify L1 parent if this is an L2 reseller
        reseller = await _get_reseller(db_user, db_session)
        if reseller and reseller.parent_reseller_id:
            parent = await ResellerRepository(db_session).get(reseller.parent_reseller_id)
            if parent:
                notif_svc = NotificationService(db_session)
                await notif_svc.notify_l1_of_l2_sale(
                    parent_reseller_user_id=parent.user_id,
                    l2_reseller_name=db_user.full_name,
                    customer_name=customer.name,
                    volume_gb=float(customer.volume_gb),
                    amount=float(sub.price),
                    sale_id=sub.id,
                )

        await db_session.commit()
        expire_str = customer.expire_date.strftime("%Y-%m-%d") if customer.expire_date else "نامشخص"
        await callback.message.edit_text(
            f"✅ اشتراک با موفقیت ساخته شد\n\n"
            f"👤 مشتری: {customer.name}\n"
            f"💾 حجم: {format_gb(float(customer.volume_gb))}\n"
            f"⏳ مدت: {data['duration_days']} روز\n"
            f"📅 انقضا: {expire_str}\n\n"
            f"🔗 لینک اتصال:\n<code>{link}</code>",
            parse_mode="HTML",
        )
    except ValueError as exc:
        await db_session.rollback()
        await callback.message.edit_text(f"❌ {exc}")
    except Exception:
        await db_session.rollback()
        await callback.message.edit_text("❌ خطایی رخ داد. لطفاً دوباره تلاش کنید.")


# ── Renew subscription FSM ───────────────────────────────────────────────────


@router.message(F.text == "🔄 تمدید اشتراک")
async def renew_sub_start(message: Message, db_user: User, state: FSMContext) -> None:
    if not bot_is_reseller(db_user):
        return await message.answer("⛔ دسترسی ندارید")
    await state.set_state(RenewSubscriptionStates.waiting_customer_id)
    await message.answer(
        "🔄 تمدید اشتراک\n\nآیدی مشتری را وارد کنید (عدد):",
        reply_markup=cancel_keyboard(),
    )


@router.message(RenewSubscriptionStates.waiting_customer_id)
async def renew_sub_customer_id(
    message: Message, state: FSMContext, db_user: User, db_session: AsyncSession
) -> None:
    cid = _safe_int((message.text or "").strip())
    if not cid:
        return await message.answer("❌ آیدی نامعتبر. یک عدد وارد کنید:")

    reseller = await _get_reseller(db_user, db_session)
    if not reseller:
        return await message.answer("❌ پروفایل نماینده یافت نشد.")
    customer = await CustomerRepository(db_session).get(cid)
    if not check_reseller_owns_customer(reseller, customer):
        return await message.answer("⛔ مشتری یافت نشد یا دسترسی ندارید.")

    await state.update_data(customer_id=cid)
    await state.set_state(RenewSubscriptionStates.waiting_volume_gb)
    await message.answer(
        f"مشتری: {customer.name}\n\nحجم جدید اشتراک را وارد کنید (GB):"
    )


@router.message(RenewSubscriptionStates.waiting_volume_gb)
async def renew_sub_volume(message: Message, state: FSMContext) -> None:
    try:
        gb = float((message.text or "").strip())
        if gb <= 0:
            raise ValueError
    except ValueError:
        return await message.answer("❌ مقدار نامعتبر:")
    await state.update_data(volume_gb=gb)
    await state.set_state(RenewSubscriptionStates.waiting_duration)
    await message.answer("مدت اشتراک را انتخاب کنید:", reply_markup=duration_keyboard())


@router.callback_query(F.data.startswith("duration:"), RenewSubscriptionStates.waiting_duration)
async def renew_sub_duration(callback: CallbackQuery, state: FSMContext) -> None:
    days = _safe_int(callback.data.split(":")[-1])
    if not days:
        return await callback.answer("❌ نامعتبر", show_alert=True)
    await state.update_data(duration_days=days)
    data = await state.get_data()
    await state.set_state(RenewSubscriptionStates.confirm)
    await callback.message.edit_text(
        f"📋 تأیید تمدید اشتراک\n\n"
        f"🆔 آیدی مشتری: {data['customer_id']}\n"
        f"💾 حجم جدید: {format_gb(data['volume_gb'])}\n"
        f"⏳ مدت: {days} روز\n\n"
        f"آیا تأیید می‌کنید؟",
        reply_markup=confirm_keyboard("renew:confirm"),
    )


@router.callback_query(F.data == "renew:confirm", RenewSubscriptionStates.confirm)
async def renew_sub_confirm(
    callback: CallbackQuery, state: FSMContext, db_user: User, db_session: AsyncSession
) -> None:
    if not bot_is_reseller(db_user):
        await state.clear()
        return await callback.answer("⛔ دسترسی ندارید", show_alert=True)

    data = await state.get_data()
    await state.clear()

    server = await _get_default_server(db_session)
    if not server:
        return await callback.message.edit_text("❌ سروری پیکربندی نشده است.")

    await callback.message.edit_text("⏳ در حال تمدید اشتراک...")
    try:
        service = SubscriptionService(db_session)
        customer, sub = await service.renew_subscription(
            reseller_user_id=db_user.id,
            customer_id=data["customer_id"],
            volume_gb=data["volume_gb"],
            duration_days=data["duration_days"],
            server=server,
        )
        await db_session.commit()
        expire_str = customer.expire_date.strftime("%Y-%m-%d") if customer.expire_date else "نامشخص"
        await callback.message.edit_text(
            f"✅ اشتراک با موفقیت تمدید شد\n\n"
            f"👤 مشتری: {customer.name}\n"
            f"💾 حجم: {format_gb(float(customer.volume_gb))}\n"
            f"📅 انقضا جدید: {expire_str}"
        )
    except ValueError as exc:
        await db_session.rollback()
        await callback.message.edit_text(f"❌ {exc}")
    except Exception:
        await db_session.rollback()
        await callback.message.edit_text("❌ خطایی رخ داد.")


# ── Customer list ────────────────────────────────────────────────────────────


@router.message(F.text == "👥 مشتری‌های من")
async def my_customers(message: Message, db_user: User, db_session: AsyncSession) -> None:
    if not bot_is_reseller(db_user):
        return await message.answer("⛔ دسترسی ندارید")
    reseller = await _get_reseller(db_user, db_session)
    if not reseller:
        return await message.answer("❌ پروفایل نماینده یافت نشد.")
    customers = await CustomerRepository(db_session).list_by_reseller(reseller.id)
    if not customers:
        return await message.answer("هیچ مشتری‌ای ثبت نشده است.")
    await message.answer(
        f"👥 مشتری‌های شما ({len(customers)} نفر):",
        reply_markup=customer_list_keyboard(customers),
    )


@router.callback_query(F.data == "reseller:customers")
async def reseller_customers_cb(callback: CallbackQuery, db_user: User, db_session: AsyncSession) -> None:
    reseller = await _get_reseller(db_user, db_session)
    customers = await CustomerRepository(db_session).list_by_reseller(reseller.id)
    await callback.message.edit_text(
        f"👥 مشتری‌های شما ({len(customers)} نفر):",
        reply_markup=customer_list_keyboard(customers),
    )


@router.callback_query(F.data.startswith("customer:page:"))
async def customer_page(callback: CallbackQuery, db_user: User, db_session: AsyncSession) -> None:
    page = _safe_int(callback.data.split(":")[-1]) or 0
    reseller = await _get_reseller(db_user, db_session)
    customers = await CustomerRepository(db_session).list_by_reseller(reseller.id)
    await callback.message.edit_reply_markup(reply_markup=customer_list_keyboard(customers, page))


@router.callback_query(F.data.startswith("customer:detail:"))
async def customer_detail(callback: CallbackQuery, db_user: User, db_session: AsyncSession) -> None:
    cid = _safe_int(callback.data.split(":")[-1])
    if not cid:
        return await callback.answer("❌ آیدی نامعتبر", show_alert=True)

    reseller = await _get_reseller(db_user, db_session)
    if not reseller:
        return await callback.answer("⛔ دسترسی ندارید", show_alert=True)

    customer = await CustomerRepository(db_session).get(cid)
    if not check_reseller_owns_customer(reseller, customer):
        return await callback.answer("⛔ دسترسی ندارید", show_alert=True)

    status_map = {
        "ACTIVE": "✅ فعال", "EXPIRED": "⏰ منقضی",
        "DISABLED": "🚫 غیرفعال", "TRAFFIC_EXHAUSTED": "📵 ترافیک تمام شده",
    }
    expire_str = customer.expire_date.strftime("%Y-%m-%d") if customer.expire_date else "نامشخص"
    await callback.message.edit_text(
        f"👤 مشخصات مشتری\n\n"
        f"🔤 نام: {customer.name}\n"
        f"📧 ایمیل: {customer.email}\n"
        f"💾 حجم: {format_gb(float(customer.volume_gb))}\n"
        f"📊 مصرف: {format_gb(float(customer.used_gb))} ({customer.traffic_percent:.1f}٪)\n"
        f"📅 انقضا: {expire_str}\n"
        f"🔵 وضعیت: {status_map.get(customer.status, customer.status)}",
        reply_markup=customer_detail_keyboard(cid),
    )


@router.callback_query(F.data.startswith("customer:link:"))
async def customer_link(callback: CallbackQuery, db_user: User, db_session: AsyncSession) -> None:
    cid = _safe_int(callback.data.split(":")[-1])
    if not cid:
        return await callback.answer("❌ آیدی نامعتبر", show_alert=True)

    reseller = await _get_reseller(db_user, db_session)
    if not reseller:
        return await callback.answer("⛔ دسترسی ندارید", show_alert=True)

    customer = await CustomerRepository(db_session).get(cid)
    if not check_reseller_owns_customer(reseller, customer):
        return await callback.answer("⛔ دسترسی ندارید", show_alert=True)

    sub = await SubscriptionRepository(db_session).get_active_by_customer(cid)
    if not sub or not sub.link:
        return await callback.answer("لینک فعالی یافت نشد", show_alert=True)

    await callback.message.answer(
        f"🔗 لینک اتصال مشتری «{customer.name}»:\n\n<code>{sub.link}</code>",
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("customer:renew:"))
async def customer_renew_start(callback: CallbackQuery, state: FSMContext, db_user: User, db_session: AsyncSession) -> None:
    cid = _safe_int(callback.data.split(":")[-1])
    if not cid:
        return await callback.answer("❌ نامعتبر", show_alert=True)

    reseller = await _get_reseller(db_user, db_session)
    customer = await CustomerRepository(db_session).get(cid)
    if not check_reseller_owns_customer(reseller, customer):
        return await callback.answer("⛔ دسترسی ندارید", show_alert=True)

    await state.set_state(RenewSubscriptionStates.waiting_volume_gb)
    await state.update_data(customer_id=cid)
    await callback.message.edit_text(
        f"🔄 تمدید اشتراک مشتری «{customer.name}»\n\nحجم جدید (GB) را وارد کنید:"
    )


# ── Sales report ─────────────────────────────────────────────────────────────


@router.message(F.text == "📊 گزارش فروش")
async def sales_report(message: Message, db_user: User, db_session: AsyncSession) -> None:
    if not bot_is_reseller(db_user):
        return await message.answer("⛔ دسترسی ندارید")
    reseller = await _get_reseller(db_user, db_session)
    if not reseller:
        return await message.answer("❌ پروفایل نماینده یافت نشد.")

    sale_repo = SaleRepository(db_session)
    total_amount, total_gb, total_profit = await sale_repo.total_sales_by_reseller(reseller.id)
    recent = await sale_repo.list_by_reseller(reseller.id, limit=10)

    lines = [
        "📊 گزارش فروش شما\n",
        f"💰 کل درآمد: {format_price(float(total_amount))}",
        f"📦 کل فروش: {format_gb(float(total_gb))}",
        f"📈 سود خالص: {format_price(float(total_profit))}\n",
        "🕐 آخرین فروش‌ها:",
    ]
    for s in recent:
        name = s.customer.name if s.customer else "?"
        lines.append(
            f"  • {name} — {format_gb(float(s.gb))} — {format_price(float(s.amount))}"
        )

    # If L1, also show children summary
    if reseller.is_level_1:
        children_summary = await sale_repo.children_sales_summary(reseller.id)
        if children_summary:
            lines.append("\n👥 فروش نمایندگان زیرمجموعه:")
            for row in children_summary:
                lines.append(
                    f"  • {row.full_name}: {format_gb(float(row.total_gb or 0))} — "
                    f"{format_price(float(row.total_amount or 0))}"
                )

    await message.answer("\n".join(lines))


# ── Notifications ────────────────────────────────────────────────────────────


@router.message(F.text == "🔔 اعلان‌ها")
async def my_notifications(message: Message, db_user: User, db_session: AsyncSession) -> None:
    if not bot_is_reseller(db_user):
        return await message.answer("⛔ دسترسی ندارید")
    from app.models.notification import Notification, NotificationStatus
    from sqlalchemy import select as sa_select
    result = await db_session.execute(
        sa_select(Notification)
        .where(
            Notification.user_id == db_user.id,
            Notification.status == NotificationStatus.SENT,
        )
        .order_by(Notification.created_at.desc())
        .limit(10)
    )
    notifs = list(result.scalars().all())
    if not notifs:
        return await message.answer("هیچ اعلانی وجود ندارد.")
    lines = ["🔔 آخرین اعلان‌های شما:\n"]
    for n in notifs:
        date_str = n.created_at.strftime("%m/%d %H:%M") if n.created_at else ""
        lines.append(f"[{date_str}]\n{n.message}\n{'─'*20}")
    await message.answer("\n".join(lines))


# ── L1-only: child reseller management ──────────────────────────────────────


@router.message(F.text == "👥 نمایندگان زیرمجموعه")
async def my_children(message: Message, db_user: User, db_session: AsyncSession) -> None:
    if not bot_is_admin_or_l1(db_user):
        return await message.answer("⛔ دسترسی ندارید — فقط نمایندگان سطح ۱")
    reseller = await _get_reseller(db_user, db_session)
    if not reseller:
        return await message.answer("❌ پروفایل نماینده یافت نشد.")
    children = await ResellerRepository(db_session).list_children(reseller.id)
    if not children:
        return await message.answer("هیچ نماینده زیرمجموعه‌ای ندارید.")
    await message.answer(
        f"👥 نمایندگان زیرمجموعه شما ({len(children)} نفر):",
        reply_markup=child_reseller_list_keyboard(children),
    )


@router.callback_query(F.data == "reseller:children")
async def reseller_children_cb(callback: CallbackQuery, db_user: User, db_session: AsyncSession) -> None:
    reseller = await _get_reseller(db_user, db_session)
    children = await ResellerRepository(db_session).list_children(reseller.id)
    await callback.message.edit_text(
        f"👥 نمایندگان زیرمجموعه ({len(children)} نفر):",
        reply_markup=child_reseller_list_keyboard(children),
    )


@router.callback_query(F.data.startswith("child:detail:"))
async def child_detail(callback: CallbackQuery, db_user: User, db_session: AsyncSession) -> None:
    child_id = _safe_int(callback.data.split(":")[-1])
    if not child_id:
        return await callback.answer("❌ نامعتبر", show_alert=True)

    if not bot_is_admin_or_l1(db_user):
        return await callback.answer("⛔ دسترسی ندارید", show_alert=True)

    repo = ResellerRepository(db_session)
    parent_reseller = await repo.get_by_user_id(db_user.id)
    child = await repo.get(child_id)

    if not child or child.parent_reseller_id != parent_reseller.id:
        return await callback.answer("⛔ این نماینده زیرمجموعه شما نیست", show_alert=True)

    child_user = child.user
    name = child_user.full_name if child_user else f"ID:{child.id}"
    await callback.message.edit_text(
        f"👤 مشخصات نماینده زیرمجموعه\n\n"
        f"🔤 نام: {name}\n"
        f"💾 اعتبار کل: {format_gb(float(child.credit_gb))}\n"
        f"📤 فروخته شده: {format_gb(float(child.used_gb))}\n"
        f"✅ باقی‌مانده: {format_gb(float(child.remaining_credit_gb))}\n"
        f"💰 قیمت فروش: {format_price(float(child.sell_price_per_gb))}\n"
        f"🔵 وضعیت: {'✅ فعال' if child.active else '❌ غیرفعال'}",
        reply_markup=child_reseller_detail_keyboard(child_id),
    )


@router.callback_query(F.data.startswith("child:sales:"))
async def child_sales(callback: CallbackQuery, db_user: User, db_session: AsyncSession) -> None:
    child_id = _safe_int(callback.data.split(":")[-1])
    if not child_id:
        return await callback.answer("❌ نامعتبر", show_alert=True)

    repo = ResellerRepository(db_session)
    parent = await repo.get_by_user_id(db_user.id)
    child = await repo.get(child_id)
    if not child or child.parent_reseller_id != parent.id:
        return await callback.answer("⛔ دسترسی ندارید", show_alert=True)

    sale_repo = SaleRepository(db_session)
    total_amount, total_gb, total_profit = await sale_repo.total_sales_by_reseller(child_id)
    child_name = child.user.full_name if child.user else f"ID:{child_id}"
    await callback.message.edit_text(
        f"📊 گزارش فروش {child_name}\n\n"
        f"💰 کل فروش: {format_price(float(total_amount))}\n"
        f"📦 حجم فروخته: {format_gb(float(total_gb))}\n"
        f"📈 سود نماینده: {format_price(float(total_profit))}",
        reply_markup=child_reseller_detail_keyboard(child_id),
    )


# ── L1-only: create L2 reseller FSM ─────────────────────────────────────────


@router.message(F.text == "➕ ساخت نماینده سطح ۲")
async def create_l2_start(message: Message, db_user: User, state: FSMContext) -> None:
    if not bot_is_admin_or_l1(db_user):
        return await message.answer("⛔ دسترسی ندارید — فقط نمایندگان سطح ۱")
    await state.set_state(CreateL2ResellerStates.waiting_telegram_id)
    await message.answer(
        "➕ ساخت نماینده سطح ۲\n\nآیدی عددی تلگرام نماینده را وارد کنید:",
        reply_markup=cancel_keyboard(),
    )


@router.message(CreateL2ResellerStates.waiting_telegram_id)
async def create_l2_telegram_id(message: Message, state: FSMContext) -> None:
    tid = _safe_int((message.text or "").strip())
    if not tid:
        return await message.answer("❌ آیدی تلگرام باید یک عدد باشد:")
    await state.update_data(telegram_id=tid)
    await state.set_state(CreateL2ResellerStates.waiting_full_name)
    await message.answer("نام کامل نماینده را وارد کنید:")


@router.message(CreateL2ResellerStates.waiting_full_name)
async def create_l2_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if len(name) < 2:
        return await message.answer("❌ نام خیلی کوتاه است:")
    await state.update_data(full_name=name)
    await state.set_state(CreateL2ResellerStates.waiting_credit_gb)
    await message.answer("اعتبار اولیه (گیگابایت) را وارد کنید:\nمثال: 500")


@router.message(CreateL2ResellerStates.waiting_credit_gb)
async def create_l2_credit(
    message: Message, state: FSMContext, db_user: User, db_session: AsyncSession
) -> None:
    try:
        gb = float((message.text or "").strip())
        if gb <= 0:
            raise ValueError
    except ValueError:
        return await message.answer("❌ مقدار نامعتبر:")

    reseller = await _get_reseller(db_user, db_session)
    if reseller and float(reseller.remaining_credit_gb) < gb:
        return await message.answer(
            f"❌ موجودی کافی نیست\n"
            f"اعتبار باقی‌مانده: {format_gb(float(reseller.remaining_credit_gb))}"
        )
    await state.update_data(credit_gb=gb)
    await state.set_state(CreateL2ResellerStates.waiting_sell_price)
    await message.answer(
        "قیمت فروش هر گیگابایت برای این نماینده (تومان) را وارد کنید:\nمثال: 15000"
    )


@router.message(CreateL2ResellerStates.waiting_sell_price)
async def create_l2_price(message: Message, state: FSMContext) -> None:
    try:
        price = float((message.text or "").strip())
        if price < 0:
            raise ValueError
    except ValueError:
        return await message.answer("❌ قیمت نامعتبر:")
    await state.update_data(sell_price_per_gb=price)
    data = await state.get_data()
    await state.set_state(CreateL2ResellerStates.confirm)
    await message.answer(
        f"📋 تأیید ساخت نماینده سطح ۲\n\n"
        f"🆔 آیدی تلگرام: {data['telegram_id']}\n"
        f"👤 نام: {data['full_name']}\n"
        f"💾 اعتبار: {format_gb(data['credit_gb'])}\n"
        f"💰 قیمت فروش: {format_price(data['sell_price_per_gb'])} / گیگ\n\n"
        f"نماینده جدید ایجاد شود؟",
        reply_markup=confirm_keyboard("l2:confirm"),
    )


@router.callback_query(F.data == "l2:confirm", CreateL2ResellerStates.confirm)
async def create_l2_confirm(
    callback: CallbackQuery, state: FSMContext, db_user: User, db_session: AsyncSession
) -> None:
    if not bot_is_admin_or_l1(db_user):
        await state.clear()
        return await callback.answer("⛔ دسترسی ندارید", show_alert=True)

    data = await state.get_data()
    await state.clear()

    reseller = await _get_reseller(db_user, db_session)
    if not reseller:
        return await callback.message.edit_text("❌ پروفایل نماینده یافت نشد.")

    try:
        service = ResellerService(db_session)
        user, child = await service.create_level2_reseller(
            parent_reseller_id=reseller.id,
            telegram_id=data["telegram_id"],
            full_name=data["full_name"],
            credit_gb=data["credit_gb"],
            sell_price_per_gb=data["sell_price_per_gb"],
            parent_user_id=db_user.id,
        )
        await db_session.commit()
        await callback.message.edit_text(
            f"✅ نماینده سطح ۲ با موفقیت ساخته شد\n\n"
            f"👤 نام: {user.full_name}\n"
            f"💾 اعتبار: {format_gb(float(child.credit_gb))}\n"
            f"💰 قیمت فروش: {format_price(float(child.sell_price_per_gb))} / گیگ"
        )
    except ValueError as exc:
        await db_session.rollback()
        await callback.message.edit_text(f"❌ {exc}")
    except Exception:
        await db_session.rollback()
        await callback.message.edit_text("❌ خطایی رخ داد.")


# ── L1-only: allocate more credit to existing child ──────────────────────────


@router.callback_query(F.data.startswith("child:credit:"))
async def child_credit_start(callback: CallbackQuery, state: FSMContext, db_user: User) -> None:
    child_id = _safe_int(callback.data.split(":")[-1])
    if not child_id or not bot_is_admin_or_l1(db_user):
        return await callback.answer("⛔ دسترسی ندارید", show_alert=True)
    await state.set_state(AllocateCreditStates.waiting_amount_gb)
    await state.update_data(child_id=child_id)
    await callback.message.edit_text("مقدار اعتبار (گیگابایت) برای انتقال را وارد کنید:")


@router.message(AllocateCreditStates.waiting_amount_gb)
async def allocate_credit_amount(message: Message, state: FSMContext) -> None:
    try:
        gb = float((message.text or "").strip())
        if gb <= 0:
            raise ValueError
    except ValueError:
        return await message.answer("❌ مقدار نامعتبر:")
    await state.update_data(amount_gb=gb)
    data = await state.get_data()
    await state.set_state(AllocateCreditStates.confirm)
    await message.answer(
        f"📋 تأیید انتقال اعتبار\n\n"
        f"مقدار: {format_gb(gb)} به نماینده #{data['child_id']}\n\n"
        f"آیا تأیید می‌کنید؟",
        reply_markup=confirm_keyboard("allocate:confirm"),
    )


@router.callback_query(F.data == "allocate:confirm", AllocateCreditStates.confirm)
async def allocate_credit_confirm(
    callback: CallbackQuery, state: FSMContext, db_user: User, db_session: AsyncSession
) -> None:
    if not bot_is_admin_or_l1(db_user):
        await state.clear()
        return await callback.answer("⛔ دسترسی ندارید", show_alert=True)

    data = await state.get_data()
    await state.clear()

    parent = await _get_reseller(db_user, db_session)
    if not parent:
        return await callback.message.edit_text("❌ پروفایل نماینده یافت نشد.")

    try:
        service = ResellerService(db_session)
        _, child = await service.allocate_credit_to_child(
            parent_reseller_id=parent.id,
            child_reseller_id=data["child_id"],
            gb=data["amount_gb"],
            actor_user_id=db_user.id,
        )
        await db_session.commit()
        await callback.message.edit_text(
            f"✅ اعتبار با موفقیت منتقل شد\n\n"
            f"💾 اعتبار کل نماینده: {format_gb(float(child.credit_gb))}\n"
            f"✅ باقی‌مانده نماینده: {format_gb(float(child.remaining_credit_gb))}"
        )
    except ValueError as exc:
        await db_session.rollback()
        await callback.message.edit_text(f"❌ {exc}")
    except Exception:
        await db_session.rollback()
        await callback.message.edit_text("❌ خطایی رخ داد.")


# ── Cancel ────────────────────────────────────────────────────────────────────


@router.callback_query(F.data == "cancel")
async def cancel_handler(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("❌ عملیات لغو شد.")


@router.callback_query(F.data == "reseller:back")
async def reseller_back(callback: CallbackQuery) -> None:
    await callback.message.delete()
    await callback.answer()
