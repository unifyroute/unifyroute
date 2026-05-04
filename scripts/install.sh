#!/bin/sh
#
# UnifyRoute — One-command install for Linux & macOS
# ===================================================
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/unifyroute/UnifyRoute/main/scripts/install.sh | sh
#
# Or if already cloned:
#   ./scripts/install.sh
#
# Environment variables:
#   UNIFYROUTE_DIR    Install directory (default: $HOME/UnifyRoute)
#   UNIFYROUTE_BRANCH Git branch to clone (default: main)
#   UNIFYROUTE_PORT   App port (default: 6565)
#   UNIFYROUTE_HOST   App host (default: localhost)
#   UNIFYROUTE_PW     Master password (default: auto-generated)
#   UNIFYROUTE_SKIP   Comma-separated: prereqs,clone,setup,build,start
# ===================================================

set -eu

# ── Config ─────────────────────────────────────────────────────────────────────
INSTALL_DIR="${UNIFYROUTE_DIR:-$HOME/UnifyRoute}"
BRANCH="${UNIFYROUTE_BRANCH:-main}"
PORT="${UNIFYROUTE_PORT:-6565}"
HOST="${UNIFYROUTE_HOST:-localhost}"
MASTER_PW="${UNIFYROUTE_PW:-}"
SKIP="${UNIFYROUTE_SKIP:-}"

REPO="https://github.com/unifyroute/UnifyRoute.git"

# ── Helpers ────────────────────────────────────────────────────────────────────
BOLD='\033[1m';  RED='\033[0;31m';  GREEN='\033[0;32m'
YELLOW='\033[0;33m';  CYAN='\033[0;36m';  NC='\033[0m'

info()   { printf "${CYAN}ℹ${NC}  %s\n" "$*"; }
ok()     { printf "${GREEN}✅${NC}  %s\n" "$*"; }
warn()   { printf "${YELLOW}⚠${NC}  %s\n" "$*"; }
err()    { printf "${RED}❌${NC}  %s\n" "$*" >&2; }
banner() { printf "\n${BOLD}━━━ %s ━━━${NC}\n" "$*"; }

has()    { command -v "$1" >/dev/null 2>&1; }

skip_step() {
  name="$1"
  if [ -z "$SKIP" ]; then return 1; fi
  case ",$SKIP," in *",$name,"*) return 0;; esac
  return 1
}

# ── Header ─────────────────────────────────────────────────────────────────────
echo ""
printf "${CYAN}${BOLD}"
echo "  _    _       _  __  _____ _____   ____  _   _ _______ "
echo " | |  | |     | | \ \/ /_   _|  __ \|  _ \| | | |__   __|"
echo " | |  | |_ __ | |  \  /  | | | |__) | |_) | | | |  | |   "
echo " | |  | | '_ \| |  /  \  | | |  _  /|  _ <| | | |  | |   "
echo " | |__| | | | | | / /\ \_| |_| | \ \| |_) | |_| |  | |   "
echo "  \____/|_| |_|_|/_/  \_\___|_|  \_\____/ \___/   |_|   "
printf "${NC}"
echo "                           One-command install"
echo ""

# ── Platform detection ─────────────────────────────────────────────────────────
banner "Platform detection"

OS="$(uname -s)"
ARCH="$(uname -m)"
info "OS:   $OS"
info "Arch: $ARCH"

case "$OS" in
  Linux)
    PKG_INSTALL="sudo apt-get install -y"
    if has dnf; then PKG_INSTALL="sudo dnf install -y"; fi
    if has pacman; then PKG_INSTALL="sudo pacman -S --noconfirm"; fi
    ;;
  Darwin)
    if ! has brew; then
      warn "Homebrew not found -- installing it..."
      /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    fi
    PKG_INSTALL="brew install"
    ;;
  *)
    err "Unsupported OS: $OS"
    exit 1
    ;;
esac
ok "$OS detected"

# ── Prerequisites ──────────────────────────────────────────────────────────────
banner "Prerequisites"

# Python
if has python3 && python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)' 2>/dev/null; then
  PYTHON="python3"
  ok "Python $(python3 --version 2>&1 | awk '{print $2}')"
elif has python && python -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)' 2>/dev/null; then
  PYTHON="python"
  ok "Python $(python --version 2>&1 | awk '{print $2}')"
else
  warn "Python 3.11+ not found. Installing..."
  case "$OS" in
    Linux)
      if echo "$PKG_INSTALL" | grep -q apt-get; then
        sudo apt-get update -qq && $PKG_INSTALL python3 python3-pip python3-venv
      elif echo "$PKG_INSTALL" | grep -q dnf; then
        $PKG_INSTALL python3 python3-pip python3-venv
      else
        $PKG_INSTALL python python-pip
      fi
      PYTHON="python3"
      ;;
    Darwin)
      $PKG_INSTALL python@3.12
      PYTHON="python3"
      ;;
  esac
  ok "Python installed: $($PYTHON --version 2>&1)"
fi

# uv
if has uv; then
  ok "uv $(uv --version 2>&1 | awk '{print $2}')"
else
  info "Installing uv..."
  if has curl; then
    curl -fsSL https://astral.sh/uv/install.sh | sh
  else
    wget -qO- https://astral.sh/uv/install.sh | sh
  fi
  # Add uv to PATH for the rest of this script
  if [ -f "$HOME/.local/bin/uv" ]; then
    PATH="$HOME/.local/bin:$PATH"
    export PATH
  fi
  if has uv; then
    ok "uv installed: $(uv --version 2>&1)"
  else
    err "Failed to install uv. Install manually: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
  fi
fi

# Node.js (needed for GUI build)
if has node && has npm; then
  ok "Node.js $(node --version 2>&1) / npm $(npm --version 2>&1)"
else
  warn "Node.js not found. Installing via nvm..."
  NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
  if [ ! -d "$NVM_DIR" ]; then
    curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.0/install.sh | sh
  fi
  if [ -f "$NVM_DIR/nvm.sh" ]; then
    . "$NVM_DIR/nvm.sh"
  fi
  nvm install --lts --latest-npm 2>/dev/null || true
  if ! has node; then
    case "$OS" in
      Linux)
        if echo "$PKG_INSTALL" | grep -q apt-get; then
          curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash - && $PKG_INSTALL nodejs
        else
          $PKG_INSTALL nodejs
        fi
        ;;
      Darwin) $PKG_INSTALL node ;;
    esac
  fi
  ok "Node.js $(node --version 2>&1) / npm $(npm --version 2>&1)"
fi

# Git
if has git; then
  ok "Git $(git --version 2>&1 | awk '{print $3}')"
else
  warn "Git not found. Installing..."
  $PKG_INSTALL git
  ok "Git installed"
fi

# Docker (optional)
if has docker && docker info >/dev/null 2>&1; then
  ok "Docker $(docker --version 2>&1 | awk '{print $3}' | tr -d ',')"
else
  warn "Docker not available (optional -- Redis will not auto-start)"
fi

# ── Clone repo ─────────────────────────────────────────────────────────────────
banner "Getting UnifyRoute"

if [ -f "./unifyroute" ] && [ -f "./scripts/setup.py" ]; then
  info "Already inside UnifyRoute repo: $PWD"
  CLONE_DIR="$PWD"
elif [ -d "$INSTALL_DIR" ] && [ -f "$INSTALL_DIR/unifyroute" ]; then
  info "Found existing install at $INSTALL_DIR"
  CLONE_DIR="$INSTALL_DIR"
else
  info "Cloning UnifyRoute ($BRANCH branch) into $INSTALL_DIR..."
  git clone --depth=1 --branch "$BRANCH" "$REPO" "$INSTALL_DIR" 2>/dev/null || {
    warn "Branch '$BRANCH' not found; falling back to default branch"
    git clone --depth=1 "$REPO" "$INSTALL_DIR"
  }
  CLONE_DIR="$INSTALL_DIR"
  ok "Cloned to $CLONE_DIR"
fi

cd "$CLONE_DIR"

# ── Setup ──────────────────────────────────────────────────────────────────────
banner "UnifyRoute Setup"

if ! skip_step "setup"; then

# Generate master password if not set
if [ -z "$MASTER_PW" ]; then
  if has openssl; then
    MASTER_PW="$(openssl rand -base64 12 | tr '+/' '-_')"
  else
    MASTER_PW="unifyroute-$(date +%s)"
  fi
fi

# Run setup non-interactively
info "Running setup (this will take a few minutes)..."
printf '%s\n' "data/unifyroute.db" "$PORT" "$HOST" "http://$HOST:$PORT" "$MASTER_PW" "$MASTER_PW" | \
  "$PYTHON" scripts/setup.py install 2>&1

fi

# ── Show admin token ───────────────────────────────────────────────────────────
banner "Admin Token"

if [ -f ".admin_token" ]; then
  ADMIN_TOKEN="$(cat .admin_token)"
elif [ -f ".api_token" ]; then
  ADMIN_TOKEN="$(cat .api_token)"
else
  ADMIN_TOKEN=""
fi

if [ -n "$ADMIN_TOKEN" ]; then
  printf "\n${YELLOW}${BOLD}  ADMIN API TOKEN:${NC} ${CYAN}%s${NC}\n\n" "$ADMIN_TOKEN"
  printf "  ${BOLD}Save this now${NC} -- it will not be shown again.\n\n"
fi

# ── Start ──────────────────────────────────────────────────────────────────────
if ! skip_step "start"; then
  banner "Starting UnifyRoute"
  info "Starting server on http://$HOST:$PORT ..."
  nohup ./unifyroute start >/dev/null 2>&1 &
  sleep 3

  # Health check
  i=1
  while [ $i -le 20 ]; do
    if curl -sf "http://$HOST:$PORT/api/health" >/dev/null 2>&1; then
      ok "UnifyRoute is running!"
      break
    fi
    i=$((i + 1))
    sleep 1
  done
fi

# ── Done ───────────────────────────────────────────────────────────────────────
banner "Install Complete!"

echo ""
printf "  ${BOLD}Dashboard:${NC}     ${CYAN}http://$HOST:$PORT${NC}\n"
printf "  ${BOLD}API:${NC}           ${CYAN}http://$HOST:$PORT/api${NC}\n"
printf "  ${BOLD}Install dir:${NC}   ${CYAN}$CLONE_DIR${NC}\n"
printf "  ${BOLD}Run again:${NC}     ${CYAN}cd $CLONE_DIR && ./unifyroute start${NC}\n"
echo ""
printf "  ${YELLOW}Login with master password you set during setup.${NC}\n"
echo ""
info "Thank you for installing UnifyRoute! 🚦"
echo ""
