# Vastai-helper

Helper scripts for running [opencode](https://opencode.ai) against an LLM served on a
[Vast.ai](https://vast.ai) GPU instance (OpenAI-compatible endpoint, e.g. llama.cpp / vLLM),
and managing that instance's lifecycle from the same machine.

## Scripts

| Script | Purpose |
| --- | --- |
| `stop_instance.py` | List running Vast.ai instances and stop one (or all that serve opencode sessions). |
| `update_vastai_ip.py` | After (re)starting an instance, point the `Vastai` provider in `opencode.json` at the instance's new public IP. |

## Prerequisites

- Python 3 with the Vast.ai SDK: `pip install vastai`
- `VASTAI_API_KEY` environment variable set to your Vast.ai API key
- opencode configured with a custom OpenAI-compatible provider pointing at your instance

## One-time opencode setup

Paths below use `~/.config/opencode/` (Windows: `C:\Users\<you>\.config\opencode\`).

1. **Provider** — in `opencode.json`, add the active model and a `Vastai` provider:

   ```json
   "model": "Vastai/Qwen3.8-27B",
   "provider": {
     "Vastai": {
       "npm": "@ai-sdk/openai-compatible",
       "options": {
         "baseURL": "https://<INSTANCE_PUBLIC_IP>:<PORT>/v1",
         "apiKey": "sk-any-placeholder"
       },
       "models": { "Qwen3.8-27B": { "name": "Qwen3.8-27B" } }
     }
   }
   ```

   - `<INSTANCE_PUBLIC_IP>` — the instance's public IP. It changes when the instance
     (re)starts; `update_vastai_ip.py` keeps it current.
   - `<PORT>` — your model server's port. Keep it the same across restarts.
   - If the instance serves self-signed TLS, add `"network": { "ca_cert": "<path-to-ca-bundle>" }`.

2. **Scripts** — copy both scripts to `~/.config/opencode/scripts/` so the
   `/endsession` command and your shell can call them from anywhere.

3. **`/endsession` command** — create `~/.config/opencode/command/endsession.md`:

   ```markdown
   ---
   description: Complete the given task, then stop the Vast.ai instances serving opencode sessions.
   agent: build
   ---

   Task: $ARGUMENTS

   If no task is given above, do no work — immediately run the stop command as your last action.

   Otherwise: complete the task above as usual, or as far as possible if it cannot be finished.

   As your very last action, run:

       python "<path-to-scripts>/stop_instance.py" --stop_opencode_session

   This stops every Vast.ai instance that any opencode session on this PC is currently
   talking to. The model serving this session dies immediately after that tool call, so do
   not plan any further tool calls or summaries after it.
   ```

4. **Unattended permission** — so the stop command never blocks on a prompt while you
   sleep, allow it in `opencode.json`:

   ```json
   "permission": {
     "bash": { "python *stop_instance.py*": "allow" }
   }
   ```

5. **Restart opencode** — config is loaded once at startup; none of the above is
   hot-reloaded.

## stop_instance.py

```
python stop_instance.py                            # interactive: numbered table, pick to stop
python stop_instance.py 47991049                   # stop a specific instance ID
python stop_instance.py 47991049 --yes             # skip the y/N confirmation
python stop_instance.py 47991049 --force           # allow stopping an instance that serves an opencode session
python stop_instance.py --stop_opencode_session    # stop the instance(s) serving opencode sessions, no confirmation
python stop_instance.py --help
```

- Only running instances are listed. The row serving the current opencode session is
  marked `<- you` (detected from live opencode TCP connections, with a fallback to the
  opencode session DB + config).
- Stopping is not destroying: instance data is preserved and it can be started again.
- Direct mode refuses to stop a `<- you` instance without `--force`.

## update_vastai_ip.py

```
python update_vastai_ip.py                         # exactly one running instance -> update it; several -> pick
python update_vastai_ip.py 47991049                # explicit instance ID
python update_vastai_ip.py --wait                  # update only after the new /v1/models answers properly
python update_vastai_ip.py --wait --timeout 600    # longer polling window (default 300s)
python update_vastai_ip.py --help
```

- Updates only the `Vastai` provider's `baseURL` (IP swapped, port/path kept); other
  providers and all file formatting are untouched.
- `--wait` polls `<new-baseURL>/models` every 5s and considers the endpoint ready only on
  a `200` with an OpenAI-style model list (`"object": "list"` + non-empty `data`). On
  timeout the file is left unchanged.
- Writes a backup to `opencode.json.bak` before editing.

## Daily cycle

**Morning — bring the session online:**

1. Start your instance (vast.ai web UI, or the Vast.ai API/CLI).
2. `python <path-to-scripts>\update_vastai_ip.py --wait`
3. Restart opencode.

**Bedtime — unattended work + auto-stop (optional):**

```
/endsession write a program that can solve for x in a quadratic equation
```

opencode completes the task, then stops the instance(s) serving opencode as its last
action. The session dies right after that tool call (its final wrap-up reply is lost —
that is expected). In the morning, restart the instance and run `update_vastai_ip.py`.

## Edit `C:\nvm4w\nodejs\opencode.ps1`

If you launch opencode through a PowerShell shim on your PATH, put this at the top
of the file so the instance IP is refreshed and verified before every start.
`NODE_TLS_REJECT_UNAUTHORIZED=0` makes Node accept the instance's self-signed TLS
certificate (alternative to `network.ca_cert`); `pause` keeps the console open so you
can check the update result.

```pwsh
#!/usr/bin/env pwsh
$env:NODE_TLS_REJECT_UNAUTHORIZED = "0"
python C:\Users\holyc\.config\opencode\scripts\update_vastai_ip.py --wait
pause
```

## Notes

- `--stop_opencode_session` stops **all** Vast.ai instances that any opencode session on
  this machine is currently talking to, not just one.
- If you improve the scripts in this repo, re-copy them to `~/.config/opencode/scripts/`
  — the `/endsession` command uses that copy.
- `test_connection.py` is a minimal SDK smoke test; replace `XXXX` with a real key
  (better: read `VASTAI_API_KEY` from the environment).
