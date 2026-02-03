# Meshtastic LLM Bridge

A production-lean Raspberry Pi service that listens to Meshtastic text messages over USB serial and replies using a local Ollama LLM. Designed for offline use and resilience on low-power hardware.

## Features
- USB serial autodetection for Heltec V3 (or any Meshtastic node)
- Configurable channel/DM filtering and trigger prefix
- Local Ollama calls (no cloud) with retries and timeouts
- Conversation memory per sender (SQLite)
- JSON logs to stdout plus rotating file logs
- Systemd service support

## Hardware + Wiring
- Raspberry Pi with USB access
- Heltec V3 running Meshtastic firmware
- USB cable from Heltec to Pi

No additional wiring needed beyond USB for data and power.

## Flash Meshtastic (Heltec V3, brief)
1. Install Meshtastic flasher on another machine (see meshtastic.org for exact steps).
2. Flash the latest stable firmware for Heltec V3.
3. Configure the node name and channels in the Meshtastic app.

## Install
```bash
uv sync
```

For dev tools (tests/formatting):
```bash
uv sync --extra dev
```

## Configure
Copy the example env file and edit as needed:
```bash
cp .env.example .env
```

Key settings:
- `SERIAL_PORT`: optional. Leave empty for autodetect.
- `OLLAMA_MODEL`: model name installed in Ollama (e.g. `mistral`).
- `TRIGGER_PREFIX`: prefix to activate the LLM (default `!ai `).
- `RESPOND_TO_DMS_ONLY`: if `true`, only reply to DMs.
- `ALLOWED_CHANNELS`: comma list like `0,1` to allow only those channels.
- `ALLOWED_SENDERS`: comma list of node IDs (e.g. `!abcd1234`).
- `DUPLICATE_PROMPT_WINDOW_S`: suppress identical prompts from the same sender for N seconds (set `0` to disable).
- `MESHTASTIC_CONNECTION`: `serial` (default) or `tcp`.
- `MESHTASTIC_HOST`: hostname/IP for TCP connections.
- `MESHTASTIC_PORT`: TCP port (default `4403`).

Make sure the model is available locally:
```bash
ollama pull mistral
```

## Find Serial Port
Plug in the Heltec and run:
```bash
ls /dev/ttyACM* /dev/ttyUSB*
```
If you see something like `/dev/ttyACM0`, you can set `SERIAL_PORT` to it. Otherwise, leave it empty for autodetect.

## Network (TCP) Connection
If you want to run the bridge on a different machine than the radio, connect over TCP:
```bash
MESHTASTIC_CONNECTION=tcp
MESHTASTIC_HOST=192.168.1.50
MESHTASTIC_PORT=4403
```
The Meshtastic node must be reachable over the network and have its TCP interface enabled.

## Run (foreground)
```bash
uv run meshtastic-llm-bridge
```

or
```bash
uv run python -m meshtastic_llm_bridge
```

or
```bash
python -m meshtastic_llm_bridge
```

or
```bash
meshtastic-llm-bridge
```

## Run as a systemd service
Edit `systemd/meshtastic-llm-bridge.service` to match your install path and user, then:
```bash
scripts/install_service.sh
```

Place your environment file at `/etc/meshtastic-llm-bridge.env`.

## Logs + Data
- SQLite database: `./data/meshtastic_llm_bridge.sqlite3`
- Rotating logs: `./data/logs/bridge.log`

## Troubleshooting
- **No serial device found**: make sure the node is connected and powered, and check `/dev/ttyACM*` or `/dev/ttyUSB*`.
- **No replies**: confirm your trigger prefix, channel restrictions, and that Ollama is running locally.
- **Permission errors**: add your user to the `dialout` group or run the service as a user with serial access.
- **Ollama connection failure**: verify `OLLAMA_HOST` and check `ollama serve` is running.

## Safety and Legal Notes
- Ensure you comply with local radio regulations.
- Keep replies short to avoid channel congestion.
- Never transmit sensitive or personal data over public mesh networks.

## Development
```bash
uv sync --extra dev
uv run pytest
uv run ruff check .
uv run black .
```
