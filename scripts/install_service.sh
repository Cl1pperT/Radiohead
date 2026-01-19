#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="meshtastic-llm-bridge.service"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_SRC="${REPO_ROOT}/systemd/${SERVICE_NAME}"
SERVICE_DST="/etc/systemd/system/${SERVICE_NAME}"

if [[ ! -f "${SERVICE_SRC}" ]]; then
  echo "Service file not found at ${SERVICE_SRC}"
  exit 1
fi

if [[ $EUID -ne 0 ]]; then
  echo "This script needs root privileges to install the systemd service."
  echo "You may be prompted for your sudo password."
  exec sudo "$0" "$@"
fi

if [[ -f "${SERVICE_DST}" ]]; then
  if cmp -s "${SERVICE_SRC}" "${SERVICE_DST}"; then
    echo "Service file already up to date."
  else
    echo "Updating service file at ${SERVICE_DST}."
    cp "${SERVICE_SRC}" "${SERVICE_DST}"
  fi
else
  echo "Installing service file to ${SERVICE_DST}."
  cp "${SERVICE_SRC}" "${SERVICE_DST}"
fi

systemctl daemon-reload
systemctl enable "${SERVICE_NAME}"

if systemctl is-active --quiet "${SERVICE_NAME}"; then
  systemctl restart "${SERVICE_NAME}"
else
  systemctl start "${SERVICE_NAME}"
fi

echo "Installed ${SERVICE_NAME}."
echo "Remember to configure /etc/meshtastic-llm-bridge.env and edit the service file path/user if needed."
