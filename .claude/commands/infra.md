# /infra — Norma Infrastructure Management

Manage the Norma infra stack (Langfuse, LiteLLM, Ollama) using the scripts in `scripts/`.

Usage: `/infra <subcommand> [args]`

## Subcommands

### up
Start all services: Ollama, Langfuse, LiteLLM.
```bash
./.claude/commands/infra/up.sh
```
After running, verify each service is healthy:
- `curl -s http://localhost:11434/api/tags` — Ollama responding + models listed
- `curl -s http://localhost:3000/api/public/health` — Langfuse healthy
- `curl -s http://localhost:4000/health` — LiteLLM healthy

Report which services are up, which failed, and any models missing from Ollama.

### down
Stop all services.
```bash
./.claude/commands/infra/down.sh
```
Confirm containers are stopped and report final state.

### status
Show current state of all services.
```bash
./.claude/commands/infra/status.sh
```
Parse the output and flag any containers that are not in `running` state. Also ping each HTTP endpoint and report latency:
- Ollama: `http://localhost:11434/api/tags`
- Langfuse: `http://localhost:3000/api/public/health`
- LiteLLM: `http://localhost:4000/health`

### restart
Restart all services.
```bash
./.claude/commands/infra/restart.sh
```
After restart, run the same health checks as `up`.

### logs [service]
Tail logs for all services, or a specific one (e.g. `/infra logs langfuse-web`).
```bash
./.claude/commands/infra/logs.sh $ARGS
```
Stream the last 50 lines. If a service name is provided as an argument, pass it through to the script. Highlight ERROR and WARN lines.

## Notes
- All Docker services run on the Linux VM host; Ollama also runs directly on the host.
- All endpoints are on `localhost` — no devcontainer networking needed.
- If a service is unhealthy, check `docker logs <container>` for the root cause before restarting.
