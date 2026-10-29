import math
from statistics import median


HORIZON = 7
TRAINING_WINDOW = 30
MIN_TRAINING_POINTS = 30
MIN_BACKTESTS = 30
TREND_IMPROVEMENT_REQUIRED = 0.95
TREND_DAMPING = 0.8


def forecast_next_week(records: list[dict]) -> dict:
    """Compare a damped log trend with a hold-last-price baseline by walk-forward."""
    prices = [
        float(record["close"])
        for record in records
        if isinstance(record.get("close"), (int, float)) and record["close"] > 0
    ]
    if len(prices) < MIN_TRAINING_POINTS + HORIZON:
        raise ValueError("Not enough daily history for a seven-day forecast")

    naive_errors = []
    trend_errors = []
    trend_origins = []
    for origin in range(MIN_TRAINING_POINTS, len(prices) - HORIZON + 1):
        training = prices[max(0, origin - TRAINING_WINDOW) : origin]
        actual = prices[origin + HORIZON - 1]
        naive_prediction = training[-1]
        trend_prediction = _damped_log_trend(training, HORIZON)
        naive_errors.append(abs(naive_prediction - actual) / actual)
        trend_errors.append(abs(trend_prediction - actual) / actual)
        trend_origins.append(origin)

    if len(trend_origins) >= MIN_BACKTESTS:
        selection_size = min(
            len(naive_errors) - 10,
            max(20, int(len(naive_errors) * 2 / 3)),
        )
        selection_naive_error = median(naive_errors[:selection_size])
        selection_trend_error = median(trend_errors[:selection_size])
        use_trend = (
            selection_trend_error
            < selection_naive_error * TREND_IMPROVEMENT_REQUIRED
        )
    else:
        selection_size = 0
        use_trend = False

    latest_price = prices[-1]
    if use_trend:
        prediction = _damped_log_trend(prices[-TRAINING_WINDOW:], HORIZON)
        selected_errors = trend_errors[selection_size:]
        model_name = "damped log-linear trend"
        selected_error = median(selected_errors)
    else:
        prediction = latest_price
        selected_errors = naive_errors[selection_size:]
        model_name = "latest price baseline"
        selected_error = median(selected_errors)

    error_band = _quantile(selected_errors, 0.8)
    records_with_dates = [record for record in records if record.get("date")]
    last_date = records_with_dates[-1]["date"] if records_with_dates else None

    return {
        "latest_price": latest_price,
        "forecast_price": prediction,
        "range_low": max(0, prediction * (1 - error_band)),
        "range_high": prediction * (1 + error_band),
        "model": model_name,
        "backtest_error_pct": selected_error * 100,
        "naive_error_pct": median(naive_errors[selection_size:]) * 100,
        "trend_error_pct": median(trend_errors[selection_size:]) * 100,
        "backtest_count": len(selected_errors),
        "horizon": HORIZON,
        "last_date": last_date,
    }


def _damped_log_trend(prices: list[float], horizon: int) -> float:
    window = prices[-TRAINING_WINDOW:]
    log_prices = [math.log(price) for price in window]
    count = len(log_prices)
    mean_x = (count - 1) / 2
    mean_y = sum(log_prices) / count
    denominator = sum((index - mean_x) ** 2 for index in range(count))
    slope = sum(
        (index - mean_x) * (value - mean_y)
        for index, value in enumerate(log_prices)
    ) / denominator

    damped_steps = sum(TREND_DAMPING**step for step in range(horizon))
    return math.exp(math.log(window[-1]) + slope * damped_steps)


def _quantile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, math.ceil(probability * len(ordered)) - 1)
    return ordered[index]
