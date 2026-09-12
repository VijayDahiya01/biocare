# BioCore — Kubernetes manifests

Stateless app tier (api, worker, frontend) + ingress + autoscaling. Apply in order:

```bash
kubectl apply -f 00-namespace-config.yaml   # namespace, ConfigMap, Secret template
# create the REAL secret (don't use the committed template values):
kubectl -n biocore create secret generic biocore-secrets \
  --from-literal=DATABASE_URL='postgresql+psycopg://biocore:***@postgres:5432/biocore' \
  --from-literal=REDIS_URL='redis://redis:6379/0' \
  --from-literal=RABBITMQ_URL='amqp://biocore:***@rabbitmq:5672//' \
  --from-literal=SESSION_SECRET='***' --from-literal=CSRF_SECRET='***' \
  --from-literal=MINIO_KEY='***' --from-literal=MINIO_SECRET='***' \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl apply -f 10-api.yaml -f 20-worker.yaml -f 30-frontend.yaml -f 40-ingress.yaml
```

## Data stores (not in these manifests)
Postgres, Redis, Milvus, MinIO, RabbitMQ, and ZepIris are **stateful** and should
run as managed services (India-region) or as separate StatefulSets/operators with
their own backups and PVCs. Point the Secret/ConfigMap at their in-cluster service
names (`postgres`, `redis`, `milvus`, `minio`, `rabbitmq`, `zepiris-main`).

## Notes
- Images: build & push `biocore-api` and `biocore-frontend` (see `../../backend/Dockerfile`,
  `../../frontend/Dockerfile`); the **worker reuses the api image** with a different command.
- `RABBITMQ_URL` set ⇒ webhooks/notifications run async via the worker; unset ⇒ the
  api delivers inline (no worker needed).
- Prometheus scrapes `api:8080/metrics`; deploy kube-prometheus-stack and add a
  ServiceMonitor for the `api` service.
- Data localisation (DPDP): pin all nodes/storage to an India region.
