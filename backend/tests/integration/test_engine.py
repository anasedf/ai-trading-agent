"""
Integration tests for BotEngine — full trading loop with mocked dependencies.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest_asyncio

from app.bot.engine import BotEngine, BotState
from app.config import settings
from app.constants import MIN_LOT


class TestBotEngine:
    @pytest_asyncio.fixture
    async def engine(self, mock_connector, db_session, redis_client):
        engine = BotEngine(
            connector=mock_connector,
            db_session=db_session,
            redis_client=redis_client,
            symbol="GOLD",
        )
        engine.paper_trade = True
        return engine

    async def test_initial_state(self, engine):
        assert engine.state == BotState.STOPPED

    async def test_start(self, engine):
        await engine.start()
        assert engine.state == BotState.RUNNING
        assert engine.started_at is not None

    async def test_stop(self, engine):
        await engine.start()
        await engine.stop()
        assert engine.state == BotState.STOPPED

    async def test_start_idempotent(self, engine):
        await engine.start()
        started = engine.started_at
        await engine.start()
        # Should not reset started_at
        assert engine.started_at == started

    async def test_emergency_stop(self, engine):
        await engine.start()
        await engine.emergency_stop()
        assert engine.state == BotState.STOPPED

    async def test_get_status(self, engine):
        status = engine.get_status()
        assert status["state"] == "STOPPED"
        assert status["strategy"] == "ema_crossover"
        assert status["symbol"] == "GOLD"
        assert "max_risk_per_trade" in status

    async def test_process_candle_when_stopped(self, engine):
        """Should return immediately when stopped."""
        await engine.process_candle()
        assert engine.state == BotState.STOPPED

    async def test_update_strategy(self, engine):
        await engine.update_strategy("breakout")
        assert engine.strategy.name == "breakout"

    async def test_update_settings(self, engine):
        await engine.update_settings(paper_trade=True, max_risk_per_trade=0.02)
        assert engine.paper_trade is True
        assert engine.risk_manager.max_risk_per_trade == 0.02

    async def test_update_settings_timeframe(self, engine):
        await engine.update_settings(timeframe="H1")
        assert engine.timeframe == "H1"

    async def test_update_settings_invalid_timeframe(self, engine):
        original = engine.timeframe
        await engine.update_settings(timeframe="INVALID")
        assert engine.timeframe == original

    async def test_paper_trade_mode(self, engine, make_ohlcv_df):
        """Paper trade should create virtual positions without calling real connector."""
        await engine.start()
        # Skip warmup
        engine.started_at = datetime.now(UTC) - timedelta(hours=3)

        # Setup: mock market data to return a df that produces a signal
        df = make_ohlcv_df(rows=200, trend="up", base_price=2000.0)
        # Force a BUY signal on the second-to-last bar
        df.loc[df.index[-2], "signal"] = 1
        df["atr"] = 10.0

        engine.market_data.get_ohlcv = AsyncMock(return_value=df)
        engine.market_data.get_current_tick = AsyncMock(return_value={"ask": 2050.0, "bid": 2049.0})
        engine.strategy.calculate = MagicMock(return_value=df)

        # Disable MTF filter and confirmation gate to avoid data dependencies
        with (
            patch.object(settings, "use_mtf_filter", False),
            patch.dict("sys.modules", {"app.ai.confirmation_gate": None}),
        ):
            await engine.process_candle()

        # Paper position should be created
        assert len(engine._paper_positions) == 1
        assert engine._paper_positions[0]["type"] == "BUY"
        assert engine._paper_positions[0]["symbol"] == "GOLD"

    async def test_shadow_mode_skips_execution(self, engine, make_ohlcv_df):
        """Shadow rollout must NOT place any order on the strategy-engine path."""
        engine.paper_trade = False  # shadow gates the real path; paper toggle off
        await engine.redis.set("guardrails:rollout_mode", "shadow")
        await engine.start()
        engine.started_at = datetime.now(UTC) - timedelta(hours=3)

        df = make_ohlcv_df(rows=200, trend="up", base_price=2000.0)
        df.loc[df.index[-2], "signal"] = 1
        df["atr"] = 10.0
        engine.market_data.get_ohlcv = AsyncMock(return_value=df)
        engine.market_data.get_current_tick = AsyncMock(return_value={"ask": 2050.0, "bid": 2049.0})
        engine.strategy.calculate = MagicMock(return_value=df)
        engine.executor.place_order = AsyncMock()

        with (
            patch.object(settings, "use_mtf_filter", False),
            patch.dict("sys.modules", {"app.ai.confirmation_gate": None}),
        ):
            await engine.process_candle()

        engine.executor.place_order.assert_not_called()
        assert len(engine._paper_positions) == 0

    async def test_micro_mode_caps_lot(self, engine, make_ohlcv_df):
        """Micro rollout must cap the executed lot at 0.01."""
        await engine.redis.set("guardrails:rollout_mode", "micro")
        engine.fixed_lot = 0.5  # force a large lot so the 0.01 cap is observable
        await engine.start()
        engine.started_at = datetime.now(UTC) - timedelta(hours=3)

        df = make_ohlcv_df(rows=200, trend="up", base_price=2000.0)
        df.loc[df.index[-2], "signal"] = 1
        df["atr"] = 10.0
        engine.market_data.get_ohlcv = AsyncMock(return_value=df)
        engine.market_data.get_current_tick = AsyncMock(return_value={"ask": 2050.0, "bid": 2049.0})
        engine.strategy.calculate = MagicMock(return_value=df)

        with (
            patch.object(settings, "use_mtf_filter", False),
            patch.dict("sys.modules", {"app.ai.confirmation_gate": None}),
        ):
            await engine.process_candle()

        assert len(engine._paper_positions) == 1
        assert engine._paper_positions[0]["lot"] == 0.01

    async def test_circuit_breaker_pauses_bot(self, engine, redis_client):
        """When daily loss exceeds limit, bot should pause."""
        await engine.start()

        # Pre-load large loss into circuit breaker
        await redis_client.set("circuit:daily_pnl:GOLD", str(-500.0), ex=86400)

        await engine.process_candle()
        assert engine.state == BotState.PAUSED

    async def test_warmup_reduces_lot(self, engine):
        """Lot should be reduced during warmup period."""
        lot = engine._apply_warmup(1.0)
        # engine.started_at is None → no warmup applied
        assert lot == 1.0

        engine.started_at = datetime.now(UTC)
        lot = engine._apply_warmup(1.0)
        # Just started → should be reduced
        assert lot < 1.0
        assert lot >= MIN_LOT


class TestBotEngineAutoResume:
    @pytest_asyncio.fixture
    async def engine(self, mock_connector, db_session, redis_client):
        engine = BotEngine(
            connector=mock_connector,
            db_session=db_session,
            redis_client=redis_client,
            symbol="GOLD",
        )
        return engine

    async def test_auto_resume_after_cooldown(self, engine, redis_client):
        """Paused bot should auto-resume after cooldown."""
        engine.state = BotState.PAUSED

        # Set trigger time to 2 hours ago (cooldown is 60 min default)
        past = datetime.now(UTC) - timedelta(hours=2)
        await redis_client.set(
            "circuit:triggered_at:GOLD",
            past.isoformat(),
            ex=86400,
        )

        await engine.process_candle()
        assert engine.state == BotState.RUNNING

    async def test_stays_paused_during_cooldown(self, engine, redis_client):
        """Paused bot should stay paused during cooldown."""
        engine.state = BotState.PAUSED

        # Set trigger time to 10 minutes ago
        recent = datetime.now(UTC) - timedelta(minutes=10)
        await redis_client.set(
            "circuit:triggered_at:GOLD",
            recent.isoformat(),
            ex=86400,
        )

        await engine.process_candle()
        assert engine.state == BotState.PAUSED
