from aiogram.fsm.state import State, StatesGroup


class CreateResellerStates(StatesGroup):
    waiting_telegram_id = State()
    waiting_full_name = State()
    waiting_credit_gb = State()
    waiting_price_per_gb = State()    # buy price
    waiting_max_sale_gb = State()     # sell price (reused field name for backward compat)
    confirm = State()


class AddCreditStates(StatesGroup):
    waiting_reseller_id = State()
    waiting_amount_gb = State()
    confirm = State()


class AddServerStates(StatesGroup):
    waiting_name = State()
    waiting_url = State()
    waiting_username = State()
    waiting_password = State()
    waiting_inbound_id = State()
    confirm = State()
