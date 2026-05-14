"""
SoAI 2026 AI Algorithmic Trading Competition - participant entrypoint.

The official execution environment imports the class defined here, so:

* Keep the class name ``Strategy``.
* Keep this file at ``strategies/strategy.py``.
* Keep the import path ``from strategies.strategy import Strategy``.

Build your strategy by editing ``initialize`` and ``on_trading_iteration``
below. The default bodies are intentionally minimal so a fresh clone runs
end-to-end - replace them with your own logic.

Useful Lumibot documentation
----------------------------
* Lifecycle methods:    https://lumibot.lumiwealth.com/lifecycle_methods.html
* Strategy methods:     https://lumibot.lumiwealth.com/strategy_methods.html
* Strategy properties:  https://lumibot.lumiwealth.com/strategy_properties.html
* Entities (Asset,
  Order, Position):     https://lumibot.lumiwealth.com/entities.html
* Backtesting overview: https://lumibot.lumiwealth.com/backtesting.html
"""

from lumibot.strategies import Strategy as _LumibotStrategy


class Strategy(_LumibotStrategy):
    """
    Your strategy implementation.

    The two methods you almost always need are :meth:`initialize` and
    :meth:`on_trading_iteration`. Lumibot supports many other lifecycle
    hooks (``before_market_opens``, ``after_market_closes``,
    ``on_filled_order``, ...) - see the lifecycle docs linked above when
    you need them.

    Common attributes you can read at any time (full list in the
    properties docs):

    * ``self.cash`` / ``self.get_cash()`` - available cash.
    * ``self.portfolio_value`` / ``self.get_portfolio_value()`` -
      total mark-to-market portfolio value.
    * ``self.first_iteration`` - ``True`` on the very first call to
      ``on_trading_iteration``, useful for one-shot setup or buy & hold.
    * ``self.is_backtesting`` - ``True`` when running under a backtest
      engine, ``False`` when running live.
    """

    # ------------------------------------------------------------------
    # Lifecycle: setup
    # ------------------------------------------------------------------
    def initialize(self):
        """
        Called once before trading begins.

        Typical responsibilities:

        1. Choose how often the strategy wakes up via ``self.sleeptime``
           (``"1D"`` once per trading day, ``"60M"`` hourly,
           ``"5M"`` every five minutes, ``"1M"`` every minute).
        2. Declare the universe you want to trade.
        3. Set risk limits (max position weight, cash buffer, leverage cap).
        4. Load any models or precomputed parameters and stash them on
           ``self`` so :meth:`on_trading_iteration` can reuse them.
        """
        # How often this strategy is woken up. Examples:
        #   "1D"  -> once per trading day (good default for DL signals)
        #   "60M" -> every hour
        #   "5M"  -> every five minutes (intraday)
        self.sleeptime = "1D"

        # TODO: declare your universe, risk limits and any state/models
        # you want to reuse later. For example:
        #
        #     self.target_assets = ["SPY", "QQQ"]
        #     self.max_weight_per_asset = 0.6     # cap any single name at 60%
        #     self.min_cash_buffer = 0.05         # keep >=5% in cash
        #     self.lookback_days = 20             # for a moving-average signal
        #     self.model = joblib.load("models/my_model.pkl")

        self.log_message("Strategy initialized")

    # ------------------------------------------------------------------
    # Lifecycle: per-step decision making
    # ------------------------------------------------------------------
    def on_trading_iteration(self):
        """
        Called every ``self.sleeptime`` step while the market is open.

        The classic pattern is:

        1. Read current portfolio state (cash, positions, P&L).
        2. Pull market data (latest price + historical bars).
        3. Compute your signal / model prediction and translate it into
           target positions or weights.
        4. Diff target vs current positions and submit orders.
        5. Log enough information to debug later and write your report.

        Replace the no-op below with your trading logic. The default log
        line is a safe-to-keep instrumentation example - keep some form
        of logging even after you add real logic, because the official
        execution environment surfaces these messages back to you.
        """
        # ------------------------------------------------------------------
        # Step 1: observe current state.
        # ------------------------------------------------------------------
        # portfolio_value = self.get_portfolio_value()
        # cash = self.get_cash()
        # positions = self.get_positions()

        # ------------------------------------------------------------------
        # Step 2: get market data.
        # ------------------------------------------------------------------
        # Latest tradable price:
        #     price = self.get_last_price("SPY")
        # Historical bars (returns a Bars entity; access .df for a DataFrame):
        #     bars = self.get_historical_prices("SPY", length=20, timestep="day")
        #     close = bars.df["close"]

        # ------------------------------------------------------------------
        # Step 3: compute your signal / model prediction.
        # ------------------------------------------------------------------
        # Translate it into a target weight in [-1, 1] (or [0, 1] long-only)
        # and from there into a target quantity.

        # ------------------------------------------------------------------
        # Step 4: diff target vs current and submit orders.
        # ------------------------------------------------------------------
        # order = self.create_order("SPY", quantity, "buy")
        # self.submit_order(order)
        # # Or batch:
        # self.submit_orders([order_a, order_b])

        # TODO: implement your trading logic above.

        # ------------------------------------------------------------------
        # Step 5: log what happened so debugging stays painless.
        # ------------------------------------------------------------------
        self.log_message(
            f"[Strategy] portfolio=${self.get_portfolio_value():,.2f}, "
            f"cash=${self.get_cash():,.2f}, "
            f"positions={self.get_positions()}"
        )
