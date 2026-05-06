#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"
DISPLAY_VALUE="${RECORDER_DISPLAY:-:99}"
SCREEN_VALUE="${RECORDER_SCREEN:-1280x900x24}"
NOVNC_PORT="${RECORDER_NOVNC_PORT:-6080}"
VNC_PORT="${RECORDER_VNC_PORT:-5900}"
DESKTOP_ENABLED="${RECORDER_DESKTOP_ENABLED:-true}"

start_recorder_desktop() {
  export DISPLAY="${DISPLAY_VALUE}"
  mkdir -p /tmp/.X11-unix /tmp/recorder-desktop

  if pgrep -f "Xvfb ${DISPLAY_VALUE}" >/dev/null 2>&1; then
    echo "[desktop] Xvfb already running on ${DISPLAY_VALUE}."
  else
    Xvfb "${DISPLAY_VALUE}" -screen 0 "${SCREEN_VALUE}" -ac +extension RANDR >/tmp/recorder-desktop/xvfb.log 2>&1 &
    echo "[desktop] Xvfb started on ${DISPLAY_VALUE} (${SCREEN_VALUE})."
  fi

  if command -v fluxbox >/dev/null 2>&1; then
    fluxbox >/tmp/recorder-desktop/fluxbox.log 2>&1 &
    echo "[desktop] fluxbox started."
  fi

  local vnc_args=(-display "${DISPLAY_VALUE}" -forever -shared -rfbport "${VNC_PORT}" -localhost)
  if [[ -n "${RECORDER_VNC_PASSWORD:-}" ]]; then
    x11vnc -storepasswd "${RECORDER_VNC_PASSWORD}" /tmp/recorder-desktop/x11vnc.pass >/tmp/recorder-desktop/x11vnc-pass.log 2>&1
    vnc_args+=(-rfbauth /tmp/recorder-desktop/x11vnc.pass)
    echo "[desktop] x11vnc password enabled."
  else
    vnc_args+=(-nopw)
    echo "[desktop] WARNING: x11vnc password is disabled. Set RECORDER_VNC_PASSWORD in production."
  fi
  x11vnc "${vnc_args[@]}" >/tmp/recorder-desktop/x11vnc.log 2>&1 &
  echo "[desktop] x11vnc started on localhost:${VNC_PORT}."

  if command -v websockify >/dev/null 2>&1 && [[ -d /usr/share/novnc ]]; then
    websockify --web=/usr/share/novnc "0.0.0.0:${NOVNC_PORT}" "127.0.0.1:${VNC_PORT}" \
      >/tmp/recorder-desktop/novnc.log 2>&1 &
    echo "[desktop] noVNC started on 0.0.0.0:${NOVNC_PORT}."
  else
    echo "[desktop] noVNC unavailable; install novnc and websockify to enable browser access."
  fi
}

if [[ "${DESKTOP_ENABLED}" == "true" || "${DESKTOP_ENABLED}" == "1" || "${DESKTOP_ENABLED}" == "yes" ]]; then
  start_recorder_desktop
else
  echo "[desktop] recorder desktop disabled by RECORDER_DESKTOP_ENABLED=${DESKTOP_ENABLED}."
fi

cd "${APP_DIR}"
python apps/web-ui-service/scripts/bootstrap_database.py
python scripts/tools/seed_page_objects.py --project "${PAGE_OBJECT_SEED_PROJECT:-mall}" --client web --force
exec python -m uvicorn app.main:app --app-dir apps/web-ui-service --host 0.0.0.0 --port 8013
