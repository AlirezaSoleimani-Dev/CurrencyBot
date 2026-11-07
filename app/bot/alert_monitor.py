import asyncio
import logging

logger = logging.getLogger(__name__)


async def monitor_price_alerts(
    client,
    alert_store,
    currency_service,
    poll_seconds: int = 5 * 60,
):
    """Send each alert once after a fresh price crosses its target."""
    while True:
        try:
            alerts = alert_store.get_active()
            if alerts:
                result = await currency_service.get_latest_prices()
                if result.get("stale"):
                    logger.warning("Skipping alert checks because the latest prices are stale")
                else:
                    prices = result.get("prices", {})
                    for alert in alerts:
                        quote = prices.get(alert["price_label"])
                        if not quote or not isinstance(quote.get("value"), (int, float)):
                            logger.warning("No current price available for alert %s", alert["id"])
                            continue

                        current = float(quote["value"])
                        crossed = (
                            current >= alert["target"]
                            if alert["direction"] == "above"
                            else current <= alert["target"]
                        )
                        if not crossed:
                            continue

                        direction = "above" if alert["direction"] == "above" else "below"
                        message = (
                            f"🔔 Price alert: {alert['title']} is now {direction} your target.\n"
                            f"Target: {alert['target']:,.0f} toman\n"
                            f"Current price: {current:,.0f} toman"
                        )
                        try:
                            await client.send_message(alert["chat_id"], message)
                            alert_store.mark_triggered(alert["id"])
                            logger.info("Triggered price alert %s", alert["id"])
                        except Exception:
                            logger.exception("Could not deliver price alert %s", alert["id"])
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Price-alert check failed")

        await asyncio.sleep(poll_seconds)
