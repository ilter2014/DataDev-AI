# DataDev AI — 500k model and distributed training

## Current model

- v4 remains unchanged.
- v5 uses a 138-dimensional embedding, 6 attention heads and 2 transformer layers.
- The actual parameter count is computed with `sum(p.numel() for p in model.parameters())`; it is about 497k with the current vocabulary. The exact count changes if the character vocabulary changes.
- Checkpoint: `datadev_gpt_v5_model.pt`.
- The first local smoke-test run was 10 steps only. Its falling validation loss is a basic wiring check, not proof of useful language ability.

## Security first

The coordinator uses separate admin and worker bearer tokens. Set both as environment variables; never save them in source files or GitHub. The worker does not execute arbitrary shell commands. It only trains a fixed model on the shard assigned by the coordinator and returns weights.

**Do not expose the coordinator directly to the public internet over HTTP.** For remote PCs, use HTTPS through a reverse proxy (for example, a Tailscale HTTPS endpoint). Do not send bearer tokens over plain remote HTTP. The server binds to localhost by default.

## Start the coordinator (on the VDS)

Install Python 3.11+ and PyTorch CPU, then copy/clone this project folder to the VDS. Make sure `datadev_gpt_v5_model.pt` exists first.

In PowerShell, set two random secrets (each at least 32 characters) in the environment, then run:

```powershell
$env:DATADEV_CLUSTER_ADMIN_TOKEN = "PUT_A_RANDOM_ADMIN_SECRET_HERE"
$env:DATADEV_CLUSTER_WORKER_TOKEN = "PUT_A_DIFFERENT_RANDOM_WORKER_SECRET_HERE"
python -X utf8 datadev_cluster_server.py --host 127.0.0.1 --port 8765
```

Put an HTTPS reverse proxy in front of port 8765, or use a private encrypted network and configure the listener accordingly. Do not reuse the example test tokens.

## Start workers

On İlter's PC and Mert's PC, install the same project code and PyTorch CPU. Set the worker token and use the HTTPS coordinator URL:

```powershell
$env:DATADEV_CLUSTER_WORKER_TOKEN = "THE_WORKER_SECRET_FROM_THE_VDS"
python -X utf8 datadev_cluster_worker.py --server https://YOUR-COORDINATOR-DOMAIN --worker-id ilter-pc
```

Mert uses `--worker-id mert-pc`. On the VDS, a local worker can use `--server http://127.0.0.1:8765 --worker-id vds-worker` in another PowerShell window. Keep all worker IDs exactly as supplied when creating a round.

## Create and aggregate a training round

In a separate admin PowerShell window:

```powershell
$env:DATADEV_CLUSTER_ADMIN_TOKEN = "THE_ADMIN_SECRET_FROM_THE_VDS"
python -X utf8 datadev_cluster_admin.py --server https://YOUR-COORDINATOR-DOMAIN create-round --workers ilter-pc mert-pc vds-worker --steps 20
```

The command prints a `round_id`. Wait until all three workers have returned their updates, then run:

```powershell
python -X utf8 datadev_cluster_admin.py --server https://YOUR-COORDINATOR-DOMAIN status
python -X utf8 datadev_cluster_admin.py --server https://YOUR-COORDINATOR-DOMAIN aggregate --round-id YOUR_ROUND_ID
```

Aggregation is explicit: the server will refuse to merge a round until every task in that round is complete. It checks update tensor shapes, backs up the previous checkpoint, and compares validation loss before accepting a candidate; if validation loss gets worse beyond the safety margin, the active model is kept. Workers automatically download a newer central checkpoint on their next poll.

## Important limitations

This is a first distributed-training prototype using weighted FedAvg of CPU model updates. It is not a production-grade distributed training framework. Start with 10–20 steps per worker and evaluate validation loss before raising the step count. Keep the best known checkpoint separately. The VDS and Mert's PC have not been connected or deployed by this local setup yet; they must be configured using the steps above.
