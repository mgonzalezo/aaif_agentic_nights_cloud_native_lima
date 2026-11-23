#!/usr/bin/env bash
# Bootstrap the Agentic Bestiary demo on a GPU EC2 instance (Ubuntu 24.04 Deep Learning Base
# OSS Nvidia Driver GPU AMI). Idempotent: safe to run again after a failure or a config change.
# Started by the instance user data as root; logs to /var/log/bestiary-bootstrap.log.
#
# Environment (all optional except where noted):
#   BESTIARY_MODEL            main model tag                       (default qwen3.5:35b)
#   BESTIARY_FAILOVER_MODEL   small model for Agent Router failover (default qwen3.5:4b)
#   BESTIARY_EXTRA_BODY       JSON merged into every /v1/responses request, e.g. {"think": false}
#   GITHUB_TOKEN_PARAM        SSM SecureString holding a GitHub token (default /bestiary/github-token)
#   AWS_REGION                region of that parameter             (default: instance region)
#   BESTIARY_GITHUB_REPO      demo repo for the real PR            (default mgonzalezo/farolito-demo)
#   BESTIARY_GITHUB_ISSUE     issue number of the bug in that repo (default: unset = local forge)
#   BESTIARY_ACCELERATOR      gpu | cpu                            (default: gpu if nvidia-smi sees a GPU, else cpu)
#   REPO_DIR                  checkout of this repo                (default /opt/bestiary)
#   REPO_URL, REPO_REF        used only if REPO_DIR does not exist
#
# No secret is written to disk, to this log or to a manifest. The GitHub token goes
# SSM -> shell variable -> Kubernetes Secret (through a file descriptor, not argv).
set -Eeuo pipefail

LOG=/var/log/bestiary-bootstrap.log
STATE=/var/lib/bestiary-bootstrap
mkdir -p "$STATE"
exec > >(tee -a "$LOG") 2>&1

# ---- pinned versions (verified 2026-11-23, see docs/AWS_DEPLOY.md) -----------------------
K3S_VERSION="${K3S_VERSION:-v1.37.2+k3s1}"
HELM_VERSION="${HELM_VERSION:-v3.22.1}"
NVDP_VERSION="${NVDP_VERSION:-0.20.2}"           # NVIDIA k8s-device-plugin chart
OPENSANDBOX_TAG="${OPENSANDBOX_TAG:-release-1.2.1}"
SANDBOX_IMAGE="${SANDBOX_IMAGE:-bestiary-sandbox:1}"

BESTIARY_MODEL="${BESTIARY_MODEL:-qwen3.5:35b}"
BESTIARY_FAILOVER_MODEL="${BESTIARY_FAILOVER_MODEL:-qwen3.5:4b}"
BESTIARY_EXTRA_BODY="${BESTIARY_EXTRA_BODY:-}"
GITHUB_TOKEN_PARAM="${GITHUB_TOKEN_PARAM:-/bestiary/github-token}"
BESTIARY_GITHUB_REPO="${BESTIARY_GITHUB_REPO:-mgonzalezo/farolito-demo}"
BESTIARY_GITHUB_ISSUE="${BESTIARY_GITHUB_ISSUE:-}"
REPO_DIR="${REPO_DIR:-/opt/bestiary}"
NS=bestiary
if [[ -z "${BESTIARY_ACCELERATOR:-}" ]]; then
  if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi -L >/dev/null 2>&1; then BESTIARY_ACCELERATOR=gpu; else BESTIARY_ACCELERATOR=cpu; fi
fi
OVERLAY=ec2; [[ "$BESTIARY_ACCELERATOR" == "cpu" ]] && OVERLAY=ec2-cpu
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
export DEBIAN_FRONTEND=noninteractive

log()  { printf '\n[%s] == %s\n' "$(date -u +%H:%M:%S)" "$*"; }
die()  { printf '\n[%s] FAILED: %s\n' "$(date -u +%H:%M:%S)" "$*" >&2; exit 1; }
trap 'die "line $LINENO: $BASH_COMMAND (see $LOG)"' ERR

# retry <tries> <sleep> cmd...
retry() { local n=$1 s=$2; shift 2; local i; for ((i = 1; i <= n; i++)); do "$@" && return 0; sleep "$s"; done; return 1; }
kc() { k3s kubectl "$@"; }

[[ $EUID -eq 0 ]] || die "run as root (sudo)"

# ---- 1. GPU ------------------------------------------------------------------------------
log "1/12 accelerator: $BESTIARY_ACCELERATOR (overlay k8s/overlays/$OVERLAY)"
if [[ "$BESTIARY_ACCELERATOR" == "gpu" ]]; then
  nvidia-smi -L || die "nvidia-smi failed: wrong AMI or instance type, or the driver is not loaded"
  nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader
else
  echo "CPU mode: no GPU, no NVIDIA toolkit, no device plugin. $(nproc) vCPU, $(free -g | awk '/Mem:/{print $2}') GiB RAM"
fi

# ---- 2. base packages + Docker + NVIDIA container toolkit ----------------------------------
log "2/12 packages, Docker, NVIDIA container toolkit"
apt-get update -qq
apt-get install -y -qq jq git curl ca-certificates openssl >/dev/null
if ! command -v docker >/dev/null; then
  apt-get install -y -qq docker.io >/dev/null
fi
systemctl enable --now docker
if [[ "$BESTIARY_ACCELERATOR" == "gpu" ]] && ! command -v nvidia-container-runtime >/dev/null; then
  # Not on PATH: k3s only detects the runtime from PATH. Install the toolkit (NVIDIA docs, apt).
  log "installing nvidia-container-toolkit"
  curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | gpg --dearmor --yes -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
  curl -fsSL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
    | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
    > /etc/apt/sources.list.d/nvidia-container-toolkit.list
  apt-get update -qq && apt-get install -y -qq nvidia-container-toolkit >/dev/null
fi
if [[ "$BESTIARY_ACCELERATOR" == "gpu" ]]; then
  command -v nvidia-container-runtime >/dev/null || die "nvidia-container-runtime still not on PATH"
  nvidia-container-runtime --version | head -1
fi

# ---- 3. uv (host copy; the console image has its own) --------------------------------------
log "3/12 uv"
command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | UV_INSTALL_DIR=/usr/local/bin UV_NO_MODIFY_PATH=1 sh >/dev/null
uv --version

# ---- 4. k3s with the NVIDIA runtime ---------------------------------------------------------
log "4/12 k3s ${K3S_VERSION}"
if ! command -v k3s >/dev/null; then
  curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION="$K3S_VERSION" \
    INSTALL_K3S_EXEC="server --write-kubeconfig-mode 644 --disable traefik" sh -
fi
retry 60 5 kc get nodes >/dev/null 2>&1 || die "k3s API did not come up"
# k3s detects the nvidia runtime at start, from PATH. If the toolkit was installed after k3s, restart once.
if [[ "$BESTIARY_ACCELERATOR" == "gpu" ]] && ! grep -q nvidia /var/lib/rancher/k3s/agent/etc/containerd/config.toml 2>/dev/null; then
  log "k3s did not register the nvidia runtime: restarting k3s once"
  systemctl restart k3s
  retry 60 5 kc get nodes >/dev/null 2>&1 || die "k3s API did not come back"
fi
if [[ "$BESTIARY_ACCELERATOR" == "gpu" ]]; then
  grep -q nvidia /var/lib/rancher/k3s/agent/etc/containerd/config.toml || die "k3s containerd config has no nvidia runtime"
  retry 30 5 kc get runtimeclass nvidia >/dev/null 2>&1 || die "RuntimeClass nvidia missing"
fi
node_listed() { [[ -n "$(kc get nodes --no-headers 2>/dev/null)" ]]; }
retry 60 5 node_listed || die "k3s node never registered"   # kubectl wait fails at once if no node exists yet
kc wait --for=condition=Ready node --all --timeout=180s
echo 'export KUBECONFIG=/etc/rancher/k3s/k3s.yaml' > /etc/profile.d/k3s.sh

# ---- 5. Helm ----------------------------------------------------------------------------------
log "5/12 Helm ${HELM_VERSION}"
if ! command -v helm >/dev/null; then
  tmp=$(mktemp -d)
  curl -fsSL "https://get.helm.sh/helm-${HELM_VERSION}-linux-amd64.tar.gz" | tar -xz -C "$tmp"
  install "$tmp/linux-amd64/helm" /usr/local/bin/helm
  rm -rf "$tmp"
fi
helm version --short

# ---- 6. NVIDIA device plugin ---------------------------------------------------------------------
log "6/12 NVIDIA device plugin ${NVDP_VERSION}"
NODE=$(kc get nodes -o jsonpath='{.items[0].metadata.name}')
if [[ "$BESTIARY_ACCELERATOR" == "gpu" ]]; then
# The chart only schedules on nodes labelled by NFD/GFD; without them, label the node by hand.
kc label node "$NODE" nvidia.com/gpu.present=true --overwrite
helm repo add nvdp https://nvidia.github.io/k8s-device-plugin >/dev/null 2>&1 || true
helm repo update >/dev/null
helm upgrade -i nvdp nvdp/nvidia-device-plugin --version "$NVDP_VERSION" \
  --namespace nvidia-device-plugin --create-namespace \
  --set runtimeClassName=nvidia --set gfd.enabled=false --set nfd.enabled=false >/dev/null
gpu_allocatable() { [[ "$(kc get node "$NODE" -o jsonpath='{.status.allocatable.nvidia\.com/gpu}')" == "1" ]]; }
retry 60 5 gpu_allocatable || { kc -n nvidia-device-plugin get pods; die "nvidia.com/gpu is not allocatable"; }
echo "GPU allocatable on $NODE: nvidia.com/gpu=1"
else
  echo "CPU mode: skipped"
fi

# ---- 7. the repo -------------------------------------------------------------------------------------
log "7/12 repository"
if [[ ! -d "$REPO_DIR/.git" ]]; then
  : "${REPO_URL:?REPO_DIR missing: set REPO_URL (and REPO_REF)}"
  TOKEN=$(aws ssm get-parameter --name "$GITHUB_TOKEN_PARAM" --with-decryption --query Parameter.Value --output text ${AWS_REGION:+--region "$AWS_REGION"})
  askpass=$(mktemp); printf '#!/bin/sh\ncase "$1" in Username*) echo x-access-token;; *) echo "$GH_TOKEN_FOR_CLONE";; esac\n' > "$askpass"; chmod 700 "$askpass"
  GH_TOKEN_FOR_CLONE="$TOKEN" GIT_ASKPASS="$askpass" GIT_TERMINAL_PROMPT=0 git clone --branch "${REPO_REF:-main}" "$REPO_URL" "$REPO_DIR"
  rm -f "$askpass"; unset TOKEN
fi
cd "$REPO_DIR"
git rev-parse --short HEAD

# ---- 8. images: build, import into k3s containerd -----------------------------------------------------
log "8/12 build and import images"
# The Ubuntu docker.io package has no buildx; the GPU AMI (docker-ce) does. Use BuildKit only if buildx works.
docker buildx version >/dev/null 2>&1 || apt-get install -y -qq docker-buildx >/dev/null 2>&1 || true
if docker buildx version >/dev/null 2>&1; then export DOCKER_BUILDKIT=1; else export DOCKER_BUILDKIT=0; fi
echo "docker build: BuildKit=$DOCKER_BUILDKIT"
build_import() { # <tag> <docker build args...>
  local tag=$1; shift
  docker build -t "$tag" "$@"
  docker save "$tag" -o "/tmp/img.tar"
  k3s ctr -n k8s.io images import /tmp/img.tar >/dev/null
  rm -f /tmp/img.tar
}
build_import bestiary-console:dev  --target console  -f k8s/Dockerfile .
build_import bestiary-services:dev --target services -f k8s/Dockerfile .
build_import bestiary-openenv:dev  -f envs/farolito_env/Dockerfile .
build_import "$SANDBOX_IMAGE"      -f docker/sandbox.Dockerfile docker
k3s ctr -n k8s.io images ls -q | grep -E 'bestiary-(console|services|openenv|sandbox)'

# ---- 9. namespace, config, secrets -----------------------------------------------------------------------
log "9/12 namespace, ConfigMap, Secrets"
kc create namespace "$NS" --dry-run=client -o yaml | kc apply -f - >/dev/null
FORGE=local
if aws ssm get-parameter --name "$GITHUB_TOKEN_PARAM" --query Parameter.Name --output text ${AWS_REGION:+--region "$AWS_REGION"} >/dev/null 2>&1; then
  TOKEN=$(aws ssm get-parameter --name "$GITHUB_TOKEN_PARAM" --with-decryption --query Parameter.Value --output text ${AWS_REGION:+--region "$AWS_REGION"})
  kc -n "$NS" create secret generic github-token --from-file=token=<(printf %s "$TOKEN") --dry-run=client -o yaml | kc apply -f - >/dev/null
  unset TOKEN
  [[ -n "$BESTIARY_GITHUB_ISSUE" ]] && FORGE=github
else
  echo "no SSM parameter $GITHUB_TOKEN_PARAM: encounter 8 will use the local forge"
fi
cfg=(--from-literal=BESTIARY_MODEL="$BESTIARY_MODEL" --from-literal=BESTIARY_FAILOVER_MODEL="$BESTIARY_FAILOVER_MODEL"
     --from-literal=BESTIARY_EXTRA_BODY="$BESTIARY_EXTRA_BODY" --from-literal=BESTIARY_FORGE="$FORGE"
     --from-literal=BESTIARY_ACCELERATOR="$BESTIARY_ACCELERATOR" --from-literal=BESTIARY_GITHUB_REPO="$BESTIARY_GITHUB_REPO" --from-literal=BESTIARY_GITHUB_ISSUE="$BESTIARY_GITHUB_ISSUE")
kc -n "$NS" create configmap bestiary-config "${cfg[@]}" --dry-run=client -o yaml | kc apply -f - >/dev/null
echo "forge backend: $FORGE; main model: $BESTIARY_MODEL; failover model: $BESTIARY_FAILOVER_MODEL"
# OpenSandbox API key: random, created once, copied to the namespaces that need it.
kc create namespace opensandbox-system --dry-run=client -o yaml | kc apply -f - >/dev/null
kc create namespace opensandbox --dry-run=client -o yaml | kc apply -f - >/dev/null
if ! kc -n opensandbox-system get secret opensandbox-api-key >/dev/null 2>&1; then
  KEY=$(openssl rand -hex 24)
  for n in opensandbox-system "$NS"; do
    kc -n "$n" create secret generic opensandbox-api-key --from-file=api-key=<(printf %s "$KEY") >/dev/null
  done
  unset KEY
fi
kc -n "$NS" get secret opensandbox-api-key >/dev/null 2>&1 || {  # key existed in one namespace only
  kc -n opensandbox-system get secret opensandbox-api-key -o json \
    | jq 'del(.metadata.namespace,.metadata.uid,.metadata.resourceVersion,.metadata.creationTimestamp)' | kc -n "$NS" apply -f - >/dev/null; }

# ---- 10. OpenSandbox (Kubernetes runtime) --------------------------------------------------------------------
log "10/12 OpenSandbox ${OPENSANDBOX_TAG}"
OS_DIR=/opt/OpenSandbox
if [[ ! -d "$OS_DIR/.git" ]]; then
  git clone --quiet --depth 1 --branch "$OPENSANDBOX_TAG" https://github.com/opensandbox-group/OpenSandbox.git "$OS_DIR"
fi
helm upgrade -i opensandbox-base "$OS_DIR/manifests/charts/base" >/dev/null
helm upgrade -i opensandbox-controller "$OS_DIR/manifests/charts/controller" -n opensandbox-system \
  --set controller.image.repository=opensandbox/controller --set controller.image.tag="${OPENSANDBOX_TAG}" >/dev/null
helm upgrade -i opensandbox-server "$OS_DIR/manifests/charts/server" -n opensandbox-system \
  -f "$REPO_DIR/infra/aws/opensandbox-values.yaml" >/dev/null

# ---- 11. the Bestiary workloads ---------------------------------------------------------------------------------
log "11/12 kubectl apply -k k8s/overlays/$OVERLAY"
kc -n "$NS" delete job ollama-pull --ignore-not-found >/dev/null   # Job specs are immutable
kc apply -k "k8s/overlays/$OVERLAY"
# the ConfigMaps have fixed names (no hash suffix): restart what reads them so a re-run picks up changes
kc -n "$NS" rollout restart deploy/console deploy/reviewer-a2a deploy/agent-router >/dev/null

# ---- 12. wait until it is really ready ------------------------------------------------------------------------------
log "12/12 waiting: pods, GPU, models"
for d in ollama agent-router openenv-farolito reviewer-a2a console; do
  kc -n "$NS" rollout status "deploy/$d" --timeout=900s
done
kc -n opensandbox-system rollout status deploy/opensandbox-server --timeout=600s
echo "waiting for the model pull job (22 GB for the main model; up to 45 min)"
kc -n "$NS" wait --for=condition=complete job/ollama-pull --timeout=2700s || { kc -n "$NS" logs job/ollama-pull --tail=30; die "model pull did not finish"; }
echo "--- ollama list"
kc -n "$NS" exec deploy/ollama -- ollama list
echo "--- GPU allocation ($BESTIARY_ACCELERATOR mode)"
kc -n "$NS" get pods -o custom-columns='POD:.metadata.name,NODE:.spec.nodeName,GPU:.spec.containers[*].resources.limits.nvidia\.com/gpu'
echo "--- nodes and pods"
kc get nodes -o wide
kc get pods -A
echo "--- bestiary doctor (from the console pod)"
kc -n "$NS" exec deploy/console -c console -- bestiary doctor || true

date -u +%FT%TZ > "$STATE/READY"
log "READY. Present with: powershell infra\\aws\\present.ps1 -InstanceId <id>"
