from aiogram.fsm.state import State, StatesGroup


class CreateSubscriptionStates(StatesGroup):
    waiting_customer_name = State()
    waiting_volume_gb = State()
    waiting_duration = State()
    confirm = State()


class RenewSubscriptionStates(StatesGroup):
    waiting_customer_id = State()
    waiting_volume_gb = State()
    waiting_duration = State()
    confirm = State()


class CreateL2ResellerStates(StatesGroup):
    waiting_telegram_id = State()
    waiting_full_name = State()
    waiting_credit_gb = State()
    waiting_sell_price = State()
    confirm = State()


class AllocateCreditStates(StatesGroup):
    waiting_child_id = State()
    waiting_amount_gb = State()
    confirm = State()
