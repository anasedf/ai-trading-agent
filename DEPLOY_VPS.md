# Deploy on Windows VPS — Full GOLD run (systems test)

Run the whole stack on one Windows VPS, 24/7, trading GOLD on the Exness
demo for ~1 week. Goal: prove the system runs **unattended without crashing**
— NOT to make money (GOLD ema loses in backtest; demo P&L will likely be red,
that's expected and fine for a reliability test).

> All code fixes are on GitHub `main`. Clone fresh and you get them.

---

## Phase 1 — Install prerequisites (once)

- [ ] Python 3.11 (`python --version`)
- [ ] Node.js 22 (`node --version`)
- [ ] Git
- [ ] Docker Desktop — and set it to **start on login** (Settings → General → Start Docker Desktop when you log in)
- [ ] MetaTrader 5 EXNESS terminal — installed, demo `415351894` logged in
- [ ] In MT5: right-click Market Watch → **Show All** so `XAUUSDm` is subscribed

## Phase 2 — Get the code

```powershell
git clone https://github.com/anasedf/ai-trading-agent.git D:\ai-trading-agent
cd D:\ai-trading-agent
docker compose up -d                              # PostgreSQL :5434 + Redis :6380

cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt

cd ..\mt5_bridge
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\pip install "numpy<2"               # MetaTrader5 needs numpy 1.x

cd ..\frontend
npm install
```

## Phase 3 — Configure

- [ ] Create `backend\.env` (copy from your local machine)
- [ ] Create `mt5_bridge\.env` — **update `MT5_PATH`** to the VPS terminal path
      (e.g. `C:\Program Files\MetaTrader 5 EXNESS\terminal64.exe`)
- [ ] Create `frontend\.env.local` (API/WS URLs = `http://localhost:8000`)
- [ ] Run DB migrations:
  ```powershell
  cd backend
  $env:DATABASE_URL_SYNC="postgresql://goldbot:changeme@localhost:5434/goldbot"
  .venv\Scripts\python -m alembic upgrade head
  ```
- [ ] **Claude credentials:** copy `C:\Users\<you>\.claude\.credentials.json`
      from your local machine to the same path on the VPS (or log into Claude
      Code on the VPS). The SDK auto-refreshes from this file — keep it valid.

> ⚠️ **broker_alias** — a fresh DB seeds it as NULL (broker-agnostic). After first
> start, open the **Symbols** page and set GOLD's broker_alias to **`XAUUSDm`**,
> or the engine can't fetch prices ("no tick data for GOLD").

## Phase 4 — Start & verify

- [ ] Double-click **`start.bat`** (runs backend WITHOUT `--reload` — required on
      Windows, else the Claude agent fails with "Failed to start Claude Code")
- [ ] Run **`check_health.ps1`** — everything should be green
- [ ] Open `http://localhost:3000`:
  - Integration page: all services connected
  - Dashboard: GOLD price ticking, rollout badge shows your mode
  - Settings → set **Rollout = live**, set risk, then **Start** the bot
- [ ] Wait for an M15 candle close → Activity page shows AI analysis (no errors)

---

## Phase 5 — Survive 1 week unattended (the important part)

| Concern | Do this |
|---------|---------|
| **Sleep** | Control Panel → Power → Sleep = Never, Turn off disk = Never |
| **RDP** | **Disconnect** (close the window) — do NOT **Log off** (log off kills the apps) |
| **MT5** | Enable auto-login so it reconnects; keep the terminal open |
| **Docker** | Set "start on login" (Phase 1) so DB/Redis come back after reboot |
| **Crash/reboot** | Auto-restart via Task Scheduler (below) |
| **Claude token** | Do NOT log out of Claude Code on the VPS |

### Auto-restart with Task Scheduler

1. Open **Task Scheduler** → Create Task
2. General: "Run whether user is logged on or not" = **off** (needs the desktop
   session for MT5); "Run with highest privileges" = on
3. Triggers → New → **At log on** (of your user)
4. Actions → New → Start a program → `D:\ai-trading-agent\start.bat`
5. Settings → "If the task fails, restart every 5 minutes" (optional)

> This relaunches the whole stack when the VPS reboots or you log back in.
> `start.bat` is idempotent-ish: Docker `compose up -d` no-ops if already up;
> the service windows will open fresh.

---

## Phase 6 — Security (do NOT skip)

The VPS is on the internet and **auth is currently disabled**. If ports 8000/3000
are open to the world, anyone can control the bot.

Pick one:
- **Simplest:** keep ports closed to the internet (Windows Firewall blocks
  inbound 8000/3000/5434/6380). Access the UI only via **RDP + `localhost`** on
  the VPS itself.
- **Or:** set `AUTH_USERNAME` + `AUTH_PASSWORD_HASH` in `backend\.env` to enable
  login, before exposing any port.

---

## Phase 7 — What to monitor during the week

RDP in periodically and check:
- **Dashboard** — bot still RUNNING? price still ticking?
- **Activity** — AI analysis every 15 min, no repeating errors
- **History** — trades open/close are recorded correctly
- **Integration** — all services green
- **MT5 terminal** — open positions match the History page

---

## Expectations / reality check

1. **GOLD ema_crossover loses in backtest** → demo P&L will probably be negative.
   That's OK — this week tests *reliability*, not profitability.
2. Watch for: service crashes, MT5 disconnects, DB errors, AI agent failures,
   memory growth — anything that breaks an unattended run.
3. If the week is clean → next step is forward-testing the one candidate that
   showed an edge: **BTC breakout (lookback=30, atr_threshold=0.8)** with tight
   risk (~0.25%/trade, because its drawdown is large).

---

## Quick command reference

```powershell
# Start everything
D:\ai-trading-agent\start.bat

# Health check
D:\ai-trading-agent\check_health.ps1

# Tail backend log (the Backend window shows it live)
# Restart just the backend: close its window, re-run start.bat

# Stop the bot (not the services): Dashboard → Stop, or Emergency Stop
```
