#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   sudo ADMIN_SSH_IP="x.x.x.x" bash deploy/security/ufw-baseline.sh
#
# If ADMIN_SSH_IP is unset, this script allows SSH from everywhere.
# Prefer setting ADMIN_SSH_IP to your fixed office/home IP.

ADMIN_SSH_IP="${ADMIN_SSH_IP:-}"

ufw default deny incoming
ufw default allow outgoing

if [[ -n "${ADMIN_SSH_IP}" ]]; then
  ufw allow from "${ADMIN_SSH_IP}" to any port 22 proto tcp
else
  ufw allow 22/tcp
fi

ufw allow 80/tcp
ufw allow 443/tcp

# Explicit deny for internal ports.
ufw deny 6379/tcp
ufw deny 9000/tcp

ufw --force enable
ufw status verbose

