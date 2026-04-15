#!/usr/bin/env bash
set -euo pipefail

# Pull code from Git remote and restart backend service.
#
# Example (systemd runtime):
#   bash scripts/deploy-from-git.sh \
#     --repo-dir /opt/S-image \
#     --remote origin \
#     --branch main \
#     --backend-runtime systemd \
#     --backend-service s-image-backend \
#     --reload-nginx
#
# Example (docker runtime):
#   bash scripts/deploy-from-git.sh \
#     --repo-dir /opt/S-image \
#     --remote origin \
#     --branch main \
#     --backend-runtime docker \
#     --docker-compose-file deploy/docker/docker-compose.gateway.yml \
#     --docker-services "backend" \
#     --reload-nginx

REPO_DIR="/opt/S-image"
REMOTE_NAME="origin"
BRANCH_NAME="main"
BACKEND_RUNTIME="systemd"
BACKEND_SERVICE="s-image-backend"
DOCKER_COMPOSE_FILE="deploy/docker/docker-compose.gateway.yml"
DOCKER_PROJECT_NAME="s-image"
DOCKER_SERVICES="backend"
RELOAD_NGINX="false"
INSTALL_BACKEND_DEPS="false"
PIP_INDEX_URL=""

usage() {
  cat <<'EOF'
Usage:
  deploy-from-git.sh [options]

Options:
  --repo-dir <path>            Git repo path on server (default: /opt/S-image)
  --remote <name>              Git remote name (default: origin)
  --branch <name>              Branch name (default: main)
  --backend-runtime <mode>     Backend runtime: systemd|docker (default: systemd)

Systemd options:
  --backend-service <name>     systemd backend service name (default: s-image-backend)
  --install-backend-deps       Run pip install -r backend/requirements.txt after pull
  --pip-index-url <url>        Optional pip index URL used with --install-backend-deps

Docker options:
  --docker-compose-file <path> Docker compose file path (default: deploy/docker/docker-compose.gateway.yml)
  --docker-project-name <name> Docker compose project name (default: s-image)
  --docker-services <list>     Space-separated services passed to compose up (default: "backend")

Common:
  --reload-nginx               Run nginx -t && systemctl reload nginx
  -h, --help                   Show help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo-dir)
      REPO_DIR="${2:-}"
      shift 2
      ;;
    --remote)
      REMOTE_NAME="${2:-}"
      shift 2
      ;;
    --branch)
      BRANCH_NAME="${2:-}"
      shift 2
      ;;
    --backend-runtime)
      BACKEND_RUNTIME="${2:-}"
      shift 2
      ;;
    --backend-service)
      BACKEND_SERVICE="${2:-}"
      shift 2
      ;;
    --docker-compose-file)
      DOCKER_COMPOSE_FILE="${2:-}"
      shift 2
      ;;
    --docker-project-name)
      DOCKER_PROJECT_NAME="${2:-}"
      shift 2
      ;;
    --docker-services)
      DOCKER_SERVICES="${2:-}"
      shift 2
      ;;
    --reload-nginx)
      RELOAD_NGINX="true"
      shift
      ;;
    --install-backend-deps)
      INSTALL_BACKEND_DEPS="true"
      shift
      ;;
    --pip-index-url)
      PIP_INDEX_URL="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ ! -d "${REPO_DIR}" ]]; then
  echo "ERROR: repo dir not found: ${REPO_DIR}" >&2
  exit 1
fi

if [[ ! -d "${REPO_DIR}/.git" ]]; then
  echo "ERROR: not a git repository: ${REPO_DIR}" >&2
  exit 1
fi

if [[ "${BACKEND_RUNTIME}" != "systemd" && "${BACKEND_RUNTIME}" != "docker" ]]; then
  echo "ERROR: unsupported --backend-runtime: ${BACKEND_RUNTIME}" >&2
  exit 1
fi

if [[ -n "$(git -C "${REPO_DIR}" status --porcelain)" ]]; then
  echo "ERROR: working tree is not clean at ${REPO_DIR}. Commit/stash local changes first." >&2
  exit 1
fi

echo "Deploy from git:"
echo "  repo:    ${REPO_DIR}"
echo "  remote:  ${REMOTE_NAME}"
echo "  branch:  ${BRANCH_NAME}"
echo "  runtime: ${BACKEND_RUNTIME}"

git -C "${REPO_DIR}" fetch "${REMOTE_NAME}"
git -C "${REPO_DIR}" checkout "${BRANCH_NAME}"
git -C "${REPO_DIR}" pull --ff-only "${REMOTE_NAME}" "${BRANCH_NAME}"

if [[ "${BACKEND_RUNTIME}" == "systemd" ]]; then
  echo "  service: ${BACKEND_SERVICE}"

  if [[ "${INSTALL_BACKEND_DEPS}" == "true" ]]; then
    if [[ ! -f "${REPO_DIR}/backend/requirements.txt" ]]; then
      echo "ERROR: backend/requirements.txt not found." >&2
      exit 1
    fi
    if ! command -v python3 >/dev/null 2>&1; then
      echo "ERROR: python3 not found." >&2
      exit 1
    fi

    if [[ ! -d "${REPO_DIR}/backend/.venv" ]]; then
      python3 -m venv "${REPO_DIR}/backend/.venv"
    fi

    PIP_BIN="${REPO_DIR}/backend/.venv/bin/pip"
    if [[ ! -x "${PIP_BIN}" ]]; then
      echo "ERROR: pip not found in venv: ${PIP_BIN}" >&2
      exit 1
    fi

    if [[ -n "${PIP_INDEX_URL}" ]]; then
      "${PIP_BIN}" install -r "${REPO_DIR}/backend/requirements.txt" -i "${PIP_INDEX_URL}"
    else
      "${PIP_BIN}" install -r "${REPO_DIR}/backend/requirements.txt"
    fi
  fi

  systemctl restart "${BACKEND_SERVICE}"
  systemctl --no-pager --full status "${BACKEND_SERVICE}" | head -n 20
else
  if [[ "${INSTALL_BACKEND_DEPS}" == "true" ]]; then
    echo "WARNING: --install-backend-deps is ignored when --backend-runtime docker." >&2
  fi

  if ! command -v docker >/dev/null 2>&1; then
    echo "ERROR: docker command not found." >&2
    exit 1
  fi

  if [[ "${DOCKER_COMPOSE_FILE}" = /* ]]; then
    COMPOSE_FILE_PATH="${DOCKER_COMPOSE_FILE}"
  else
    COMPOSE_FILE_PATH="${REPO_DIR}/${DOCKER_COMPOSE_FILE}"
  fi

  if [[ ! -f "${COMPOSE_FILE_PATH}" ]]; then
    echo "ERROR: docker compose file not found: ${COMPOSE_FILE_PATH}" >&2
    exit 1
  fi

  if [[ ! -f "${REPO_DIR}/backend/.env" && -f "${REPO_DIR}/backend/.env.example" ]]; then
    cp "${REPO_DIR}/backend/.env.example" "${REPO_DIR}/backend/.env"
    echo "WARNING: backend/.env not found; created from .env.example. Update secrets before production." >&2
  fi

  mkdir -p "${REPO_DIR}/backend/storage"

  read -r -a DOCKER_SERVICES_ARR <<< "${DOCKER_SERVICES}"
  if [[ "${#DOCKER_SERVICES_ARR[@]}" -eq 0 ]]; then
    DOCKER_SERVICES_ARR=("backend")
  fi

  echo "  compose: ${COMPOSE_FILE_PATH}"
  echo "  project: ${DOCKER_PROJECT_NAME}"
  echo "  targets: ${DOCKER_SERVICES}"

  docker compose \
    -p "${DOCKER_PROJECT_NAME}" \
    -f "${COMPOSE_FILE_PATH}" \
    up -d --build "${DOCKER_SERVICES_ARR[@]}"

  docker compose \
    -p "${DOCKER_PROJECT_NAME}" \
    -f "${COMPOSE_FILE_PATH}" \
    ps
fi

if [[ "${RELOAD_NGINX}" == "true" ]]; then
  if ! command -v nginx >/dev/null 2>&1; then
    echo "ERROR: nginx command not found." >&2
    exit 1
  fi
  nginx -t
  systemctl reload nginx
fi

echo "Deploy completed."
