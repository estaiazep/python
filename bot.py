import asyncio
import logging
from datetime import datetime, date, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import json
import os
import numpy as np
from collections import defaultdict

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Токен бота - ЗАМЕНИТЕ НА СВОЙ!
BOT_TOKEN = "7371629878:AAGY3yeMp9fxJq0iUwKpz2XYBzZHTtqctvg"

# Константы
FIXED_EXPENSES = 4  # Фиксированные расходы
MY_SHARE_PERCENT = 50  # Моя доля от чистой прибыли (50%)
CHATTERFY_PERCENT = 0  # Чатерфай от моей доли (3%)
USD_TO_KZT = 515  # Курс доллара к тенге

# Гео и ставки
GEO_RATES = {
    "🇵🇭 Филиппины": 20,
    "🇮🇳 Индия": 40,
    "🇩🇿 Алжир": 45,
    "🇲🇦 Марокко": 50
}

# Инициализация бота
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


# Состояния для FSM
class StatsForm(StatesGroup):
    waiting_for_geo = State()
    waiting_for_deposits = State()
    waiting_for_ad_spend = State()
    waiting_for_additional_expenses = State()


class ReportForm(StatesGroup):
    waiting_for_period_days = State()
    waiting_for_comparison_period = State()


# Функции для работы с данными
def save_stats(user_id: int, stats: dict):
    """Сохранение статистики пользователя"""
    filename = f"stats_{user_id}.json"
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            all_stats = json.load(f)
    except FileNotFoundError:
        all_stats = {}

    today = str(date.today())
    all_stats[today] = stats

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(all_stats, f, indent=2, ensure_ascii=False)


def load_stats(user_id: int):
    """Загрузка статистики пользователя"""
    filename = f"stats_{user_id}.json"
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


# Расширенная функция расчета с учетом доли и чатерфай
def calculate_advanced_profit(deposits: int, ad_spend: float, additional_expenses: float = 0, deposit_rate: int = 20):
    """
    Расчет прибыли с учетом системы долей:
    1. Доход = депозиты * ставка_гео
    2. Расходы = реклама + 3 + доп.расходы
    3. Чистая прибыль = доход - расходы
    4. Моя доля = чистая прибыль * 50%
    5. Чатерфай = моя доля * 3%
    6. Итоговая прибыль = моя доля - чатерфай
    """
    # Базовые расчеты
    revenue = deposits * deposit_rate
    total_expenses = ad_spend + FIXED_EXPENSES + additional_expenses
    gross_profit = revenue - total_expenses

    # Расчет моей доли
    my_share = gross_profit * (MY_SHARE_PERCENT / 100)

    # Расчет чатерфай с моей доли
    chatterfy_fee = my_share * (CHATTERFY_PERCENT / 100)

    # Итоговая прибыль
    net_profit = my_share - chatterfy_fee

    # ROI расчеты
    roi_gross = (gross_profit / ad_spend) * 100 if ad_spend > 0 else 0
    roi_net = (net_profit / ad_spend) * 100 if ad_spend > 0 else 0

    return {
        'revenue': revenue,
        'total_expenses': total_expenses,
        'gross_profit': gross_profit,
        'my_share': my_share,
        'chatterfy_fee': chatterfy_fee,
        'net_profit': net_profit,
        'roi_gross': roi_gross,
        'roi_net': roi_net
    }


# Break-even калькулятор
def calculate_breakeven(ad_spend: float, additional_expenses: float = 0, deposit_rate: int = 20):
    """Расчет точки безубыточности"""
    total_expenses = ad_spend + FIXED_EXPENSES + additional_expenses
    deposits_needed = total_expenses / deposit_rate

    return {
        'deposits_needed': deposits_needed,
        'revenue_needed': total_expenses,
        'total_expenses': total_expenses
    }


# AI ФУНКЦИИ
def analyze_patterns(user_stats):
    """🧠 AI анализ паттернов пользователя"""
    if len(user_stats) < 3:
        return ["📊 Недостаточно данных для анализа паттернов"]

    insights = []

    # Анализ дней недели
    weekday_profits = defaultdict(list)
    for date_str, data in user_stats.items():
        weekday = datetime.strptime(date_str, '%Y-%m-%d').weekday()
        weekday_profits[weekday].append(data['net_profit'])

    if weekday_profits:
        best_day_num = max(weekday_profits.items(), key=lambda x: sum(x[1]) / len(x[1]))[0]
        worst_day_num = min(weekday_profits.items(), key=lambda x: sum(x[1]) / len(x[1]))[0]

        days = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
        insights.append(f"📅 Лучший день недели: {days[best_day_num]}")
        insights.append(f"📉 Худший день недели: {days[worst_day_num]}")

    # Анализ трендов
    recent_profits = [data['net_profit'] for data in list(user_stats.values())[-7:]]
    if len(recent_profits) >= 3:
        trend_direction = "растет" if recent_profits[-1] > recent_profits[0] else "падает"
        insights.append(f"📈 Тренд за неделю: прибыль {trend_direction}")

    # Анализ стабильности
    all_profits = [data['net_profit'] for data in user_stats.values()]
    avg_profit = sum(all_profits) / len(all_profits)
    profitable_days = len([p for p in all_profits if p > 0])
    success_rate = (profitable_days / len(all_profits)) * 100

    insights.append(f"🎯 Процент прибыльных дней: {success_rate:.1f}%")
    insights.append(f"💰 Средняя прибыль в день: ${avg_profit:.2f}")

    return insights


def get_ai_recommendations(current_data, user_stats):
    """💡 AI рекомендации на основе данных"""
    recommendations = []

    # Анализ текущего ROI
    roi = current_data.get('roi_net', 0)
    if roi < 20:
        recommendations.append("🚨 ROI критически низкий! Срочно пересмотри источники трафика")
    elif roi < 50:
        recommendations.append("⚠️ ROI можно улучшить. Попробуй оптимизировать креативы")
    elif roi > 100:
        recommendations.append("🔥 Отличный ROI! Можно смело увеличивать бюджет")

    # Анализ расходов
    ad_spend = current_data.get('ad_spend', 0)
    if user_stats:
        avg_spend = sum(data['ad_spend'] for data in user_stats.values()) / len(user_stats)
        if ad_spend > avg_spend * 1.5:
            recommendations.append("💸 Сегодня тратишь больше обычного. Следи за результатами")
        elif ad_spend < avg_spend * 0.5:
            recommendations.append("💰 Бюджет сегодня низкий. Возможно, стоит увеличить")

    # Сравнение с лучшими днями
    if user_stats:
        best_profit = max(data['net_profit'] for data in user_stats.values())
        current_profit = current_data.get('net_profit', 0)
        if current_profit > best_profit * 0.8:
            recommendations.append("🏆 Сегодня один из лучших дней! Запомни настройки")
        elif current_profit < best_profit * 0.3:
            recommendations.append(f"📊 Твой рекорд ${best_profit:.2f}. Попробуй повторить условия того дня")

    return recommendations if recommendations else ["✅ Все показатели в норме, продолжай в том же духе!"]


def detect_anomalies(user_stats):
    """🚨 Детектор аномалий в данных"""
    if len(user_stats) < 5:
        return []

    anomalies = []
    profits = [data['net_profit'] for data in user_stats.values()]
    avg_profit = sum(profits) / len(profits)
    std_dev = np.std(profits) if len(profits) > 1 else 0

    # Ищем аномальные дни (отклонение больше 2 стандартных отклонений)
    for date_str, data in user_stats.items():
        profit = data['net_profit']
        if std_dev > 0 and abs(profit - avg_profit) > 2 * std_dev:
            formatted_date = datetime.strptime(date_str, '%Y-%m-%d').strftime('%d.%m.%Y')
            if profit > avg_profit:
                anomalies.append(f"🚀 {formatted_date}: аномально высокая прибыль ${profit:.2f}")
            else:
                anomalies.append(f"⚠️ {formatted_date}: аномально низкая прибыль ${profit:.2f}")

    return anomalies[-5:]  # Показываем только последние 5 аномалий


def predict_monthly_profit(user_stats):
    """📈 Простой прогноз месячной прибыли"""
    if len(user_stats) < 7:
        return "Недостаточно данных для прогноза"

    # Берем последние 7 дней для прогноза
    recent_profits = [data['net_profit'] for data in list(user_stats.values())[-7:]]
    daily_average = sum(recent_profits) / len(recent_profits)
    monthly_prediction = daily_average * 30

    return f"📊 Прогноз на месяц: ${monthly_prediction:.2f} ({monthly_prediction * USD_TO_KZT:.0f} ₸)"


def get_optimal_budget_suggestion(user_stats):
    """🎯 Предложение оптимального бюджета"""
    if len(user_stats) < 5:
        return "Недостаточно данных для анализа бюджета"

    # Находим дни с лучшим ROI
    best_roi_days = [data for data in user_stats.values() if data['roi_net'] > 50]

    if not best_roi_days:
        return "Пока нет дней с высоким ROI для анализа"

    avg_spend = sum(day['ad_spend'] for day in best_roi_days) / len(best_roi_days)
    avg_roi = sum(day['roi_net'] for day in best_roi_days) / len(best_roi_days)

    return f"💡 Оптимальный бюджет: ${avg_spend:.2f} (средний ROI: {avg_roi:.1f}%)"


# Конвертация в тенге
def format_profit_with_kzt(usd_amount):
    """Форматирование прибыли с конвертацией в тенге"""
    kzt_amount = usd_amount * USD_TO_KZT
    return f"${usd_amount:.2f} ({kzt_amount:.0f} ₸)"


# Главное меню
def get_main_menu():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Добавить статистику"), KeyboardButton(text="📈 Сегодня")],
            [KeyboardButton(text="📋 Отчеты"), KeyboardButton(text="🔥 Топ дни")],
            [KeyboardButton(text="⚖️ Break-Even"), KeyboardButton(text="💰 Калькулятор")],
            [KeyboardButton(text="📊 Сравнить периоды"), KeyboardButton(text="🤖 AI Анализ")],
            [KeyboardButton(text="ℹ️ Инфо")]
        ],
        resize_keyboard=True
    )
    return keyboard


# Меню выбора гео
def get_geo_menu():
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"{geo} (${rate})", callback_data=f"geo_{geo.split()[1]}_{rate}")]
            for geo, rate in GEO_RATES.items()
        ]
    )
    return keyboard


# Меню отчетов
def get_reports_menu():
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📅 За 7 дней", callback_data="report_7")],
            [InlineKeyboardButton(text="📅 За 15 дней", callback_data="report_15")],
            [InlineKeyboardButton(text="📅 За 30 дней", callback_data="report_30")],
            [InlineKeyboardButton(text="📅 Текущий месяц", callback_data="report_month")],
        ]
    )
    return keyboard


# Стартовая команда
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    welcome_text = f"""
🤖 <b>AI-Powered бот для арбитража трафика!</b>

🌍 <b>Доступные ГЕО:</b>
{chr(10).join([f"├ {geo}: ${rate}" for geo, rate in GEO_RATES.items()])}

💰 <b>Система расчета прибыли:</b>
├ Моя доля: {MY_SHARE_PERCENT}% от чистой прибыли
├ Чатерфай: {CHATTERFY_PERCENT}% с моей доли
└ Фиксированные расходы: ${FIXED_EXPENSES}

🤖 <b>AI возможности:</b>
• Анализ паттернов и трендов
• Умные рекомендации
• Детектор аномалий
• Прогнозы прибыли
• Оптимизация бюджета

💱 <b>Валюты:</b> USD и Тенге (₸)

Выберите действие из меню ниже:
    """
    await message.answer(welcome_text, reply_markup=get_main_menu(), parse_mode="HTML")


# Добавление статистики
@dp.message(F.text == "📊 Добавить статистику")
async def add_stats(message: types.Message, state: FSMContext):
    await message.answer(
        "🌍 <b>Выберите ГЕО для сегодняшней статистики:</b>",
        reply_markup=get_geo_menu(),
        parse_mode="HTML"
    )
    await state.set_state(StatsForm.waiting_for_geo)


# Обработка выбора гео
@dp.callback_query(F.data.startswith("geo_"))
async def process_geo_selection(callback: types.CallbackQuery, state: FSMContext):
    geo_data = callback.data.split("_")
    geo_name = geo_data[1]
    deposit_rate = int(geo_data[2])

    # Находим полное название гео
    full_geo_name = next(geo for geo in GEO_RATES.keys() if geo_name in geo)

    await state.update_data(geo=full_geo_name, deposit_rate=deposit_rate)

    await callback.message.answer(
        f"✅ <b>Выбрано ГЕО:</b> {full_geo_name}\n"
        f"💵 <b>Ставка:</b> ${deposit_rate} за депозит\n\n"
        "Введите количество депозитов за сегодня:",
        parse_mode="HTML"
    )
    await state.set_state(StatsForm.waiting_for_deposits)
    await callback.answer()


@dp.message(StatsForm.waiting_for_deposits)
async def process_deposits(message: types.Message, state: FSMContext):
    try:
        deposits = int(message.text)
        if deposits < 0:
            raise ValueError

        data = await state.get_data()
        deposit_rate = data['deposit_rate']
        geo = data['geo']

        await state.update_data(deposits=deposits)
        revenue = deposits * deposit_rate
        await message.answer(
            f"✅ Депозиты: {deposits} шт.\n"
            f"🌍 ГЕО: {geo}\n"
            f"💰 Потенциальный доход: ${revenue}\n\n"
            "Введите расход на рекламу (в USD):"
        )
        await state.set_state(StatsForm.waiting_for_ad_spend)
    except ValueError:
        await message.answer("❌ Пожалуйста, введите корректное число депозитов (целое число ≥ 0)")


@dp.message(StatsForm.waiting_for_ad_spend)
async def process_ad_spend(message: types.Message, state: FSMContext):
    try:
        ad_spend = float(message.text.replace(',', '.'))
        if ad_spend < 0:
            raise ValueError

        data = await state.get_data()
        deposit_rate = data['deposit_rate']

        await state.update_data(ad_spend=ad_spend)

        # Показываем предварительный расчет break-even
        breakeven = calculate_breakeven(ad_spend, 0, deposit_rate)

        await message.answer(
            f"✅ Расход на рекламу: ${ad_spend}\n\n"
            f"📊 <b>Break-even анализ:</b>\n"
            f"⚖️ Нужно депозитов для окупаемости: {breakeven['deposits_needed']:.1f}\n\n"
            "Введите дополнительные расходы (или 0, если их нет):"
        )
        await state.set_state(StatsForm.waiting_for_additional_expenses)
    except ValueError:
        await message.answer("❌ Пожалуйста, введите корректную сумму расхода на рекламу")


@dp.message(StatsForm.waiting_for_additional_expenses)
async def process_additional_expenses(message: types.Message, state: FSMContext):
    try:
        additional_expenses = float(message.text.replace(',', '.'))
        if additional_expenses < 0:
            raise ValueError

        data = await state.get_data()
        deposits = data['deposits']
        ad_spend = data['ad_spend']
        deposit_rate = data['deposit_rate']
        geo = data['geo']

        # Расширенный расчет профита
        results = calculate_advanced_profit(deposits, ad_spend, additional_expenses, deposit_rate)

        # Сохранение статистики
        stats = {
            'geo': geo,
            'deposit_rate': deposit_rate,
            'deposits': deposits,
            'ad_spend': ad_spend,
            'additional_expenses': additional_expenses,
            'revenue': results['revenue'],
            'total_expenses': results['total_expenses'],
            'gross_profit': results['gross_profit'],
            'my_share': results['my_share'],
            'chatterfy_fee': results['chatterfy_fee'],
            'net_profit': results['net_profit'],
            'roi_gross': results['roi_gross'],
            'roi_net': results['roi_net'],
            'timestamp': datetime.now().isoformat()
        }

        save_stats(message.from_user.id, stats)

        # Загружаем всю статистику для AI анализа
        user_stats = load_stats(message.from_user.id)

        # AI рекомендации
        ai_recommendations = get_ai_recommendations(stats, user_stats)

        # Детальный отчет
        profit_emoji = "🟢" if results['net_profit'] > 0 else "🔴" if results['net_profit'] < 0 else "🟡"
        roi_emoji = "📈" if results['roi_net'] > 0 else "📉"

        report = f"""
📊 <b>Детальная статистика за {date.today().strftime('%d.%m.%Y')}</b>

🌍 <b>ГЕО:</b> {geo}
🏦 <b>Депозиты:</b> {deposits} шт.
💰 <b>Доход:</b> ${results['revenue']:.2f}

💸 <b>Расходы:</b>
├ Реклама: ${ad_spend:.2f}
├ Фиксированные: ${FIXED_EXPENSES:.2f}
├ Дополнительные: ${additional_expenses:.2f}
└ <b>Всего:</b> ${results['total_expenses']:.2f}

💵 <b>Чистая прибыль:</b> ${results['gross_profit']:.2f}

🎯 <b>Моя доля ({MY_SHARE_PERCENT}%):</b> ${results['my_share']:.2f}
🔧 <b>Чатерфай ({CHATTERFY_PERCENT}%):</b> ${results['chatterfy_fee']:.2f}

{profit_emoji} <b>ИТОГОВАЯ ПРИБЫЛЬ:</b> {format_profit_with_kzt(results['net_profit'])}

📊 <b>ROI:</b>
├ Валовый: {results['roi_gross']:.1f}%
└ {roi_emoji} <b>Чистый: {results['roi_net']:.1f}%</b>

🤖 <b>AI Рекомендации:</b>
{chr(10).join([f"• {rec}" for rec in ai_recommendations[:2]])}
        """

        await message.answer(report, parse_mode="HTML")
        await state.clear()

    except ValueError:
        await message.answer("❌ Пожалуйста, введите корректную сумму дополнительных расходов")


# Сегодняшняя статистика
@dp.message(F.text == "📈 Сегодня")
async def today_stats(message: types.Message):
    stats = load_stats(message.from_user.id)
    today = str(date.today())

    if today not in stats:
        await message.answer("📭 На сегодня статистика еще не добавлена.")
        return

    data = stats[today]
    profit_emoji = "🟢" if data['net_profit'] > 0 else "🔴" if data['net_profit'] < 0 else "🟡"
    roi_emoji = "📈" if data['roi_net'] > 0 else "📉"

    report = f"""
📊 <b>Сегодня ({date.today().strftime('%d.%m.%Y')})</b>

🌍 <b>ГЕО:</b> {data.get('geo', 'Не указано')}
🏦 <b>Депозиты:</b> {data['deposits']} шт.
💰 <b>Доход:</b> ${data['revenue']:.2f}
💸 <b>Расходы:</b> ${data['total_expenses']:.2f}

💵 <b>Чистая прибыль:</b> ${data['gross_profit']:.2f}
🎯 <b>Моя доля:</b> ${data['my_share']:.2f}
🔧 <b>Чатерфай:</b> ${data['chatterfy_fee']:.2f}

{profit_emoji} <b>ИТОГО:</b> {format_profit_with_kzt(data['net_profit'])}
{roi_emoji} <b>ROI:</b> {data['roi_net']:.1f}%
    """

    await message.answer(report, parse_mode="HTML")


# AI Анализ
@dp.message(F.text == "🤖 AI Анализ")
async def ai_analysis(message: types.Message):
    user_stats = load_stats(message.from_user.id)

    if len(user_stats) < 3:
        await message.answer(
            "🤖 <b>AI Анализ недоступен</b>\n\n"
            "Для работы AI нужно минимум 3 дня статистики.\n"
            f"У вас: {len(user_stats)} дней\n\n"
            "Добавьте больше данных для получения умных рекомендаций!",
            parse_mode="HTML"
        )
        return

    # Получаем все AI анализы
    patterns = analyze_patterns(user_stats)
    anomalies = detect_anomalies(user_stats)
    monthly_prediction = predict_monthly_profit(user_stats)
    budget_suggestion = get_optimal_budget_suggestion(user_stats)

    # Формируем отчет
    ai_report = f"""
🤖 <b>AI АНАЛИЗ ВАШЕЙ СТАТИСТИКИ</b>

📊 <b>АНАЛИЗ ПАТТЕРНОВ:</b>
{chr(10).join([f"• {pattern}" for pattern in patterns])}

🚨 <b>ДЕТЕКТОР АНОМАЛИЙ:</b>
{chr(10).join([f"• {anomaly}" for anomaly in anomalies]) if anomalies else "• Аномалий не обнаружено"}

📈 <b>ПРОГНОЗЫ:</b>
• {monthly_prediction}
• {budget_suggestion}

💡 <b>ОБЩИЕ РЕКОМЕНДАЦИИ:</b>
• Анализируйте лучшие дни и повторяйте успешные стратегии
• Следите за трендами и корректируйте бюджеты
• Обращайте внимание на аномальные дни для выявления причин
    """

    await message.answer(ai_report, parse_mode="HTML")


# Отчеты
@dp.message(F.text == "📋 Отчеты")
async def reports_menu(message: types.Message):
    await message.answer(
        "📋 <b>Выберите период для отчета:</b>",
        reply_markup=get_reports_menu(),
        parse_mode="HTML"
    )


# Обработка кнопок отчетов
@dp.callback_query(F.data.startswith("report_"))
async def process_report(callback: types.CallbackQuery):
    report_type = callback.data.split("_")[1]
    user_id = callback.from_user.id
    stats = load_stats(user_id)

    if not stats:
        await callback.answer("📭 Нет данных для отчета")
        return

    today = date.today()

    if report_type == "7":
        start_date = today - timedelta(days=6)
        period_name = "7 дней"
    elif report_type == "15":
        start_date = today - timedelta(days=14)
        period_name = "15 дней"
    elif report_type == "30":
        start_date = today - timedelta(days=29)
        period_name = "30 дней"
    elif report_type == "month":
        start_date = today.replace(day=1)
        period_name = "текущий месяц"

    # Фильтрация данных по периоду
    period_stats = {}
    for date_str, data in stats.items():
        stat_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        if start_date <= stat_date <= today:
            period_stats[date_str] = data

    if not period_stats:
        await callback.answer(f"📭 Нет данных за {period_name}")
        return

    # Расчет итогов
    total_deposits = sum(data['deposits'] for data in period_stats.values())
    total_revenue = sum(data['revenue'] for data in period_stats.values())
    total_expenses = sum(data['total_expenses'] for data in period_stats.values())
    total_gross_profit = sum(data['gross_profit'] for data in period_stats.values())
    total_net_profit = sum(data['net_profit'] for data in period_stats.values())
    total_ad_spend = sum(data['ad_spend'] for data in period_stats.values())

    avg_roi = (total_net_profit / total_ad_spend) * 100 if total_ad_spend > 0 else 0
    days_count = len(period_stats)
    avg_deposits_per_day = total_deposits / days_count if days_count > 0 else 0
    avg_profit_per_day = total_net_profit / days_count if days_count > 0 else 0

    profit_emoji = "🟢" if total_net_profit > 0 else "🔴" if total_net_profit < 0 else "🟡"

    # Лучший и худший день
    best_day = max(period_stats.items(), key=lambda x: x[1]['net_profit'])
    worst_day = min(period_stats.items(), key=lambda x: x[1]['net_profit'])

    # Анализ по ГЕО
    geo_stats = defaultdict(lambda: {'deposits': 0, 'profit': 0})
    for data in period_stats.values():
        geo = data.get('geo', 'Неизвестно')
        geo_stats[geo]['deposits'] += data['deposits']
        geo_stats[geo]['profit'] += data['net_profit']

    geo_breakdown = "\n".join([
        f"├ {geo}: {stats['deposits']} депов, ${stats['profit']:.2f}"
        for geo, stats in geo_stats.items()
    ])

    report = f"""
📊 <b>Отчет за {period_name}</b>
📅 {start_date.strftime('%d.%m.%Y')} - {today.strftime('%d.%m.%Y')}

📈 <b>ИТОГИ:</b>
🏦 Всего депозитов: {total_deposits}
💰 Общий доход: ${total_revenue:.2f}
💸 Общие расходы: ${total_expenses:.2f}
💵 Чистая прибыль: ${total_gross_profit:.2f}

{profit_emoji} <b>ИТОГОВАЯ ПРИБЫЛЬ: {format_profit_with_kzt(total_net_profit)}</b>
📊 <b>Средний ROI: {avg_roi:.1f}%</b>

📊 <b>СРЕДНИЕ ПОКАЗАТЕЛИ:</b>
├ Депозитов в день: {avg_deposits_per_day:.1f}
├ Прибыль в день: ${avg_profit_per_day:.2f}
└ Рабочих дней: {days_count}

🌍 <b>СТАТИСТИКА ПО ГЕО:</b>
{geo_breakdown}

🎯 <b>Лучший день:</b> {datetime.strptime(best_day[0], '%Y-%m-%d').strftime('%d.%m.%Y')} ({format_profit_with_kzt(best_day[1]['net_profit'])})
📉 <b>Худший день:</b> {datetime.strptime(worst_day[0], '%Y-%m-%d').strftime('%d.%m.%Y')} ({format_profit_with_kzt(worst_day[1]['net_profit'])})
    """

    await callback.message.answer(report, parse_mode="HTML")
    await callback.answer()


# Топ дни по профиту
@dp.message(F.text == "🔥 Топ дни")
async def top_days(message: types.Message):
    stats = load_stats(message.from_user.id)

    if not stats:
        await message.answer("📭 Нет данных для анализа.")
        return

    # Сортировка по чистой прибыли
    sorted_days = sorted(stats.items(), key=lambda x: x[1]['net_profit'], reverse=True)

    top_text = "🔥 <b>ТОП-10 дней по прибыли:</b>\n\n"

    for i, (date_str, data) in enumerate(sorted_days[:10], 1):
        profit_emoji = "🟢" if data['net_profit'] > 0 else "🔴" if data['net_profit'] < 0 else "🟡"
        formatted_date = datetime.strptime(date_str, '%Y-%m-%d').strftime('%d.%m.%Y')
        geo = data.get('geo', '🌍')

        top_text += f"{i}. {profit_emoji} <b>{formatted_date}</b> ({geo})\n"
        top_text += f"   💰 {format_profit_with_kzt(data['net_profit'])} | 🏦 {data['deposits']} депов | 📊 {data['roi_net']:.1f}% ROI\n\n"

    # Добавляем худшие дни
    if len(sorted_days) > 10:
        top_text += "\n📉 <b>Худшие дни:</b>\n\n"
        for i, (date_str, data) in enumerate(sorted_days[-3:], 1):
            profit_emoji = "🔴" if data['net_profit'] < 0 else "🟡"
            formatted_date = datetime.strptime(date_str, '%Y-%m-%d').strftime('%d.%m.%Y')
            geo = data.get('geo', '🌍')

            top_text += f"{i}. {profit_emoji} <b>{formatted_date}</b> ({geo})\n"
            top_text += f"   💸 {format_profit_with_kzt(data['net_profit'])} | 🏦 {data['deposits']} депов | 📊 {data['roi_net']:.1f}% ROI\n\n"

    await message.answer(top_text, parse_mode="HTML")


# Break-even калькулятор
@dp.message(F.text == "⚖️ Break-Even")
async def breakeven_calculator(message: types.Message):
    calculator_text = """
⚖️ <b>Break-Even Калькулятор</b>

Для расчета точки безубыточности отправьте:
<code>be гео расход_на_рекламу [доп_расходы]</code>

<b>Примеры:</b>
• <code>be филиппины 100</code> - Филиппины, $100 на рекламу
• <code>be индия 150 20</code> - Индия, $150 на рекламу + $20 доп. расходы
• <code>be алжир 200</code> - Алжир, $200 на рекламу
• <code>be марокко 180 15</code> - Марокко, $180 на рекламу + $15 доп. расходы

🌍 <b>Доступные ГЕО:</b>
{chr(10).join([f"• {geo.split()[1].lower()}: ${rate}" for geo, rate in GEO_RATES.items()])}

📊 <b>Формула:</b>
• Общие расходы = Реклама + $3 (фикс.) + Доп. расходы
• Депозитов нужно = Общие расходы ÷ Ставка ГЕО
    """
    await message.answer(calculator_text, parse_mode="HTML")


# Обработка break-even команд
@dp.message(F.text.regexp(r'^be\s+\w+\s+\d+(?:\.\d+)?(?:\s+\d+(?:\.\d+)?)?$'))
async def calculate_breakeven_command(message: types.Message):
    try:
        parts = message.text.lower().split()
        geo_input = parts[1]
        ad_spend = float(parts[2])
        additional_expenses = float(parts[3]) if len(parts) > 3 else 0

        # Находим ГЕО
        deposit_rate = None
        geo_name = None
        for geo, rate in GEO_RATES.items():
            if geo_input in geo.lower():
                deposit_rate = rate
                geo_name = geo
                break

        if not deposit_rate:
            await message.answer("❌ ГЕО не найдено. Доступные: филиппины, индия, алжир, марокко")
            return

        breakeven = calculate_breakeven(ad_spend, additional_expenses, deposit_rate)

        result = f"""
⚖️ <b>Break-Even Анализ</b>

🌍 <b>ГЕО:</b> {geo_name}
💵 <b>Ставка:</b> ${deposit_rate}

💸 <b>Расходы:</b>
├ Реклама: ${ad_spend:.2f}
├ Фиксированные: ${FIXED_EXPENSES:.2f}
├ Дополнительные: ${additional_expenses:.2f}
└ <b>Всего:</b> ${breakeven['total_expenses']:.2f}

🎯 <b>Для безубыточности нужно:</b>
🏦 <b>Депозитов:</b> {breakeven['deposits_needed']:.1f} шт.
💰 <b>Дохода:</b> ${breakeven['revenue_needed']:.2f}

📊 <b>При достижении break-even:</b>
• Чистая прибыль: $0.00
• Моя доля: $0.00
• ROI: 0%
        """

        await message.answer(result, parse_mode="HTML")

    except (ValueError, IndexError):
        await message.answer("❌ Неверный формат. Используйте: be гео расход_на_рекламу [доп_расходы]")


# Быстрый калькулятор
@dp.message(F.text == "💰 Калькулятор")
async def profit_calculator(message: types.Message):
    calculator_text = """
🧮 <b>Быстрый калькулятор прибыли</b>

Для расчета отправьте:
<code>гео депозиты расход_на_рекламу [доп_расходы]</code>

<b>Примеры:</b>
• <code>филиппины 5 100</code> - Филиппины, 5 депозитов, $100 на рекламу
• <code>индия 3 80 10</code> - Индия, 3 депозита, $80 на рекламу, $10 доп. расходы
• <code>алжир 4 120</code> - Алжир, 4 депозита, $120 на рекламу
• <code>марокко 2 90 5</code> - Марокко, 2 депозита, $90 на рекламу, $5 доп. расходы

🌍 <b>Доступные ГЕО:</b>
{chr(10).join([f"• {geo.split()[1].lower()}: ${rate}" for geo, rate in GEO_RATES.items()])}

💰 <b>Система расчета:</b>
• Доход = Депозиты × Ставка ГЕО
• Чистая прибыль = Доход - Все расходы
• Моя доля = Чистая прибыль × 50%
• Чатерфай = Моя доля × 3%
• <b>Итого = Моя доля - Чатерфай</b>
    """
    await message.answer(calculator_text, parse_mode="HTML")


# Обработка быстрого калькулятора
@dp.message(F.text.regexp(r'^\w+\s+\d+\s+\d+(?:\.\d+)?(?:\s+\d+(?:\.\d+)?)?$'))
async def calculate_quick_profit(message: types.Message):
    try:
        parts = message.text.lower().split()
        geo_input = parts[0]
        deposits = int(parts[1])
        ad_spend = float(parts[2])
        additional_expenses = float(parts[3]) if len(parts) > 3 else 0

        # Находим ГЕО
        deposit_rate = None
        geo_name = None
        for geo, rate in GEO_RATES.items():
            if geo_input in geo.lower():
                deposit_rate = rate
                geo_name = geo
                break

        if not deposit_rate:
            await message.answer("❌ ГЕО не найдено. Доступные: филиппины, индия, алжир, марокко")
            return

        results = calculate_advanced_profit(deposits, ad_spend, additional_expenses, deposit_rate)
        breakeven = calculate_breakeven(ad_spend, additional_expenses, deposit_rate)

        profit_emoji = "🟢" if results['net_profit'] > 0 else "🔴" if results['net_profit'] < 0 else "🟡"
        roi_emoji = "📈" if results['roi_net'] > 0 else "📉"

        # Определяем статус относительно break-even
        if deposits >= breakeven['deposits_needed']:
            be_status = f"✅ Выше break-even на {deposits - breakeven['deposits_needed']:.1f} депозитов"
        else:
            be_status = f"⚠️ Ниже break-even на {breakeven['deposits_needed'] - deposits:.1f} депозитов"

        calc_result = f"""
🧮 <b>Результат расчета</b>

🌍 <b>ГЕО:</b> {geo_name}
🏦 <b>Депозиты:</b> {deposits} шт.
💰 <b>Доход:</b> ${results['revenue']:.2f}

💸 <b>Расходы:</b>
├ Реклама: ${ad_spend:.2f}
├ Фиксированные: ${FIXED_EXPENSES:.2f}
├ Дополнительные: ${additional_expenses:.2f}
└ <b>Всего:</b> ${results['total_expenses']:.2f}

💵 <b>Чистая прибыль:</b> ${results['gross_profit']:.2f}

🎯 <b>Моя доля ({MY_SHARE_PERCENT}%):</b> ${results['my_share']:.2f}
🔧 <b>Чатерфай ({CHATTERFY_PERCENT}%):</b> ${results['chatterfy_fee']:.2f}

{profit_emoji} <b>ИТОГОВАЯ ПРИБЫЛЬ:</b> {format_profit_with_kzt(results['net_profit'])}

📊 <b>ROI:</b>
├ Валовый: {results['roi_gross']:.1f}%
└ {roi_emoji} <b>Чистый: {results['roi_net']:.1f}%</b>

⚖️ <b>Break-Even:</b> {breakeven['deposits_needed']:.1f} депозитов
{be_status}
        """

        await message.answer(calc_result, parse_mode="HTML")

    except (ValueError, IndexError):
        await message.answer("❌ Неверный формат. Используйте: гео депозиты расход_на_рекламу [доп_расходы]")


# Сравнение периодов
@dp.message(F.text == "📊 Сравнить периоды")
async def compare_periods(message: types.Message):
    stats = load_stats(message.from_user.id)

    if not stats:
        await message.answer("📭 Нет данных для сравнения.")
        return

    today = date.today()

    # Последние 15 дней
    period1_start = today - timedelta(days=14)
    period1_end = today

    # Предыдущие 15 дней
    period2_start = today - timedelta(days=29)
    period2_end = today - timedelta(days=15)

    # Фильтрация данных
    period1_stats = {}
    period2_stats = {}

    for date_str, data in stats.items():
        stat_date = datetime.strptime(date_str, '%Y-%m-%d').date()

        if period1_start <= stat_date <= period1_end:
            period1_stats[date_str] = data
        elif period2_start <= stat_date <= period2_end:
            period2_stats[date_str] = data

    if not period1_stats and not period2_stats:
        await message.answer("📭 Недостаточно данных для сравнения периодов.")
        return

    # Расчет показателей для периода 1
    p1_deposits = sum(data['deposits'] for data in period1_stats.values()) if period1_stats else 0
    p1_revenue = sum(data['revenue'] for data in period1_stats.values()) if period1_stats else 0
    p1_expenses = sum(data['total_expenses'] for data in period1_stats.values()) if period1_stats else 0
    p1_profit = sum(data['net_profit'] for data in period1_stats.values()) if period1_stats else 0
    p1_days = len(period1_stats)

    # Расчет показателей для периода 2
    p2_deposits = sum(data['deposits'] for data in period2_stats.values()) if period2_stats else 0
    p2_revenue = sum(data['revenue'] for data in period2_stats.values()) if period2_stats else 0
    p2_expenses = sum(data['total_expenses'] for data in period2_stats.values()) if period2_stats else 0
    p2_profit = sum(data['net_profit'] for data in period2_stats.values()) if period2_stats else 0
    p2_days = len(period2_stats)

    # Расчет изменений
    def calculate_change(new_val, old_val):
        if old_val == 0:
            return "∞" if new_val > 0 else "0"
        return f"{((new_val - old_val) / old_val) * 100:+.1f}%"

    def get_trend_emoji(new_val, old_val):
        if new_val > old_val:
            return "📈"
        elif new_val < old_val:
            return "📉"
        else:
            return "➡️"

    deposits_change = calculate_change(p1_deposits, p2_deposits)
    profit_change = calculate_change(p1_profit, p2_profit)
    revenue_change = calculate_change(p1_revenue, p2_revenue)

    comparison = f"""
📊 <b>Сравнение периодов (15 дней)</b>

📅 <b>Период 1:</b> {period1_start.strftime('%d.%m')} - {period1_end.strftime('%d.%m')} ({p1_days} дней)
📅 <b>Период 2:</b> {period2_start.strftime('%d.%m')} - {period2_end.strftime('%d.%m')} ({p2_days} дней)

🏦 <b>ДЕПОЗИТЫ:</b>
├ Сейчас: {p1_deposits} шт.
├ Было: {p2_deposits} шт.
└ {get_trend_emoji(p1_deposits, p2_deposits)} Изменение: {deposits_change}

💰 <b>ДОХОД:</b>
├ Сейчас: ${p1_revenue:.2f}
├ Было: ${p2_revenue:.2f}
└ {get_trend_emoji(p1_revenue, p2_revenue)} Изменение: {revenue_change}

💸 <b>РАСХОДЫ:</b>
├ Сейчас: ${p1_expenses:.2f}
├ Было: ${p2_expenses:.2f}
└ {get_trend_emoji(p2_expenses, p1_expenses)} Изменение: {calculate_change(p1_expenses, p2_expenses)}

💵 <b>ПРИБЫЛЬ:</b>
├ Сейчас: {format_profit_with_kzt(p1_profit)}
├ Было: {format_profit_with_kzt(p2_profit)}
└ {get_trend_emoji(p1_profit, p2_profit)} Изменение: {profit_change}

📊 <b>СРЕДНИЕ ПОКАЗАТЕЛИ В ДЕНЬ:</b>
├ Депозиты: {p1_deposits / p1_days if p1_days > 0 else 0:.1f} vs {p2_deposits / p2_days if p2_days > 0 else 0:.1f}
└ Прибыль: ${p1_profit / p1_days if p1_days > 0 else 0:.2f} vs ${p2_profit / p2_days if p2_days > 0 else 0:.2f}
    """

    await message.answer(comparison, parse_mode="HTML")


# Информация
@dp.message(F.text == "ℹ️ Инфо")
async def info(message: types.Message):
    info_text = f"""
ℹ️ <b>Информация о AI-боте</b>

🎯 <b>Назначение:</b> AI-powered учет арбитража трафика

🌍 <b>Поддерживаемые ГЕО:</b>
{chr(10).join([f"• {geo}: ${rate}" for geo, rate in GEO_RATES.items()])}

📊 <b>Настройки:</b>
• Моя доля: {MY_SHARE_PERCENT}% от чистой прибыли
• Чатерфай: {CHATTERFY_PERCENT}% с моей доли
• Фиксированные расходы: ${FIXED_EXPENSES}
• Валюты: USD и Тенге (₸)

🤖 <b>AI возможности:</b>
• Анализ паттернов и трендов
• Умные рекомендации
• Детектор аномалий
• Прогнозы прибыли
• Оптимизация бюджета

🔧 <b>Функции:</b>
• Мульти-ГЕО статистика
• Детальные отчеты за любой период
• Сравнение периодов (15 дней)
• Топ дни по профиту
• Break-even калькулятор
• Быстрый калькулятор прибыли

💡 <b>Формула расчета прибыли:</b>
1. Доход = Депозиты × Ставка ГЕО
2. Общие расходы = Реклама + ${FIXED_EXPENSES} + Доп. расходы
3. Чистая прибыль = Доход - Общие расходы
4. Моя доля = Чистая прибыль × {MY_SHARE_PERCENT}%
5. Чатерфай = Моя доля × {CHATTERFY_PERCENT}%
6. <b>ИТОГОВАЯ ПРИБЫЛЬ = Моя доля - Чатерфай</b>

🚀 <b>Быстрые команды:</b>
• <code>филиппины 5 100</code> - расчет для Филиппин
• <code>индия 3 80 10</code> - расчет для Индии с доп. расходами
• <code>be алжир 150</code> - break-even для Алжира
• <code>марокко 2 90</code> - расчет для Марокко

💱 <b>Курс:</b> 1 USD = {USD_TO_KZT} ₸
    """
    await message.answer(info_text, parse_mode="HTML")


# Обработка неизвестных команд
@dp.message()
async def unknown_command(message: types.Message):
    await message.answer(
        "❓ Неизвестная команда.\n\n"
        "Используйте меню ниже или команды:\n"
        "• <code>филиппины 5 100</code> - быстрый расчет\n"
        "• <code>be индия 150</code> - break-even\n"
        "• /start - главное меню",
        parse_mode="HTML"
    )


# Запуск бота
async def main():
    print("🤖 AI-Powered бот для арбитража запущен!")
    print("🌍 Поддерживаемые ГЕО:")
    for geo, rate in GEO_RATES.items():
        print(f"   ├ {geo}: ${rate}")
    print(f"💱 Курс: 1 USD = {USD_TO_KZT} ₸")
    print(f"🎯 Моя доля: {MY_SHARE_PERCENT}%")
    print(f"🔧 Чатерфай: {CHATTERFY_PERCENT}%")
    print("🤖 AI функции активированы!")
    print("=" * 50)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
