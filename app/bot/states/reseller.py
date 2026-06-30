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
