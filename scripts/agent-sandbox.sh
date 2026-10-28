#!/usr/bin/env bash
# scripts/agent-sandbox.sh — run an agent where this checkout is all there is.
#
# The agent is a process on a shared machine. Its $HOME holds the
# supervisor's working files, its /tmp holds whatever the supervisor's
# shell last left there, and a run that reads either has left the work
# order behind: run 2eb137aa found a replay harness in /tmp, walked it
# into the bench repository and scored against the goldens.
#
# So neither is mounted. What the sandbox contains is the checkout it was
# given, an empty /tmp of its own, a private home, and the docker socket
# it needs to start the stack. Nothing else exists — `ls /home` shows the
# one directory, `ls /tmp` is empty on every run.
#
# The docker socket is a hole this does not close: `docker run -v /:/host`
# reaches the host through the daemon. It closes the channel that was
# actually used, which is the agent finding files that were lying around.
# Removing the daemon as well means the agent cannot restart what it
# edited, so the socket stays and the trace is audited for it.
#
# Supervisor-side tooling. No sample contains this file.
#
#   AGENT_HOME       install directory of the agent, mounted read-only
#                    (e.g. ~/.opencode). Its bin/ joins PATH.
#   AGENT_STATE_DIR  writable directory for this run's agent state only.
#                    Fresh per run, so one run cannot read the last one's
#                    transcripts. Prepare it (credentials and so on)
#                    before the wrapper starts.
#
# Usage: agent-sandbox.sh <agent command...>   (run with cwd = checkout)

set -euo pipefail

: "${AGENT_HOME:?set AGENT_HOME to the agent install directory}"
: "${AGENT_STATE_DIR:?set AGENT_STATE_DIR to the state directory}"

if [ "$#" -lt 1 ]; then
    echo "usage: agent-sandbox.sh <agent command...>" >&2
    exit 2
fi

if [ ! -d "$AGENT_HOME" ]; then
    echo "AGENT_HOME is not a directory: $AGENT_HOME" >&2
    exit 2
fi

if [ ! -d "$AGENT_STATE_DIR" ]; then
    echo "AGENT_STATE_DIR is not a directory: $AGENT_STATE_DIR" >&2
    exit 2
fi

if [ ! -S /run/docker.sock ]; then
    echo "no docker socket at /run/docker.sock" >&2
    exit 2
fi

checkout="$PWD"
state="$AGENT_STATE_DIR"

mkdir -p "$state/home" "$state/data" "$state/config" "$state/cache"

# Order matters: every tmpfs is applied before the binds, because an
# overmount laid down afterwards would hide the bind it covers.
exec bwrap \
    --unshare-all \
    --share-net \
    --die-with-parent \
    --ro-bind /usr /usr \
    --ro-bind /etc /etc \
    --ro-bind-try /run/resolvconf /run/resolvconf \
    --ro-bind-try /run/systemd/resolve /run/systemd/resolve \
    --symlink usr/bin /bin \
    --symlink usr/sbin /sbin \
    --symlink usr/lib /lib \
    --symlink usr/lib64 /lib64 \
    --proc /proc \
    --dev /dev \
    --tmpfs /tmp \
    --tmpfs /var/tmp \
    --tmpfs /home \
    --tmpfs /root \
    --ro-bind "$AGENT_HOME" /opt/agent \
    --bind "$state" /state \
    --bind "$checkout" "$checkout" \
    --bind /run/docker.sock /run/docker.sock \
    --setenv PATH /opt/agent/bin:/usr/local/bin:/usr/bin:/bin \
    --setenv HOME /state/home \
    --setenv XDG_DATA_HOME /state/data \
    --setenv XDG_CONFIG_HOME /state/config \
    --setenv XDG_CACHE_HOME /state/cache \
    --setenv TMPDIR /tmp \
    --chdir "$checkout" \
    -- "$@"
