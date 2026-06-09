# Reference: openshift-deployment (BC Gov Private Cloud)

> Heavy detail for workload manifests on BC Gov's OpenShift clusters. The agent
> loads this on demand from [SKILL.md](../SKILL.md). Anything not about a
> Deployment, StatefulSet, DaemonSet, Job, CronJob, HPA/VPA, PDB, probes,
> resources/QoS, lifecycle, or the platform's workload-admission rules belongs
> in a sibling `openshift-*` skill (see SKILL.md *Don't Use When*).

## 1. Namespace shape that constrains your manifests

Every license-plate namespace ships with three ResourceQuota objects and a default LimitRange. Your manifests live inside their math.

| Quota object | What it caps | Counts toward |
| --- | --- | --- |
| `compute-long-running-quota` | CPU / memory for long-lived pods (`Deployment`, `StatefulSet`, `DaemonSet`) | Sum of `requests` and `limits` across all such pods in the namespace. |
| `compute-time-bound-quota` | CPU / memory for terminating pods (`Job`, `CronJob`-spawned jobs, builds, deployers) | Sum of `requests` and `limits` across active terminating pods. Old completed pods count until pruned by the Job's history limits. |
| `compute-best-effort-quota` | Pods with `requests == limits == 0` (BestEffort QoS) | Pod count cap. |

Default `LimitRange` (applied per container if you omit values):

| Field | Default |
| --- | --- |
| `defaultRequest.cpu` | `50m` |
| `defaultRequest.memory` | `256Mi` |
| `default` (limit) memory | namespace memory quota or 16 GiB, whichever is lower |
| `default` (limit) CPU | **none** (no CPU limit defaulted) |
| `max` (limit) memory | typically 16 GiB; halved on namespaces with ≥ 32 GiB request |
| `max` (limit) CPU | **none** |

Implications:
- If you don't set `requests.memory`, the LimitRange will, but the value is generic. Setting it explicitly to your actual working set is the only way the scheduler can place you sensibly.
- If you don't set `limits.cpu`, you have no CPU limit. That's fine for `Guaranteed` QoS only if you also don't set `requests.cpu` — but then the LimitRange sets a 50m request. The intentional `Guaranteed` recipe is **set all four** (`requests.cpu`, `requests.memory`, `limits.cpu`, `limits.memory`) with `requests == limits`.

## 2. Controller decision matrix

| Workload shape | Use |
| --- | --- |
| Stateless HTTP/gRPC API, replaceable replicas, behind a Service | `Deployment` |
| Stateful, ordered, stable network ID, per-pod PVC (databases, brokers, leader-elected) | `StatefulSet` |
| Exactly one pod per node (log shipper, node agent, CSI sidecar) | `DaemonSet` |
| Run-to-completion batch (one-shot, parallel fan-out) | `Job` |
| Scheduled batch (subject to admission rules in §6) | `CronJob` |
| Legacy OpenShift `DeploymentConfig` | Avoid for new work — no advantage over `Deployment`; same automation treatment. |

## 3. Worked manifest templates

### 3.1 Production `Deployment` with HPA + PDB

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
  namespace: abc123-prod
  labels: { app: api }
spec:
  replicas: 3
  selector: { matchLabels: { app: api } }
  strategy:
    type: RollingUpdate
    # Deployment rollout strategy — distinct from PodDisruptionBudget.
    # Surge-only, zero-downtime rollout is fine here; the "never set
    # maxUnavailable: 0" rule applies only to the PDB below.
    rollingUpdate: { maxSurge: 1, maxUnavailable: 0 }
  template:
    metadata:
      labels: { app: api }
    spec:
      terminationGracePeriodSeconds: 30
      affinity:
        podAntiAffinity:
          # Mandatory: spread replicas across nodes so a single node failure
          # or drain cannot take the whole workload down (regardless of PDB).
          requiredDuringSchedulingIgnoredDuringExecution:
            - labelSelector:
                matchLabels: { app: api }
              topologyKey: kubernetes.io/hostname
      # On Gold / GoldDR, also spread across zones so a zone outage
      # doesn't take every replica.
      topologySpreadConstraints:
        - maxSkew: 1
          topologyKey: topology.kubernetes.io/zone
          whenUnsatisfiable: ScheduleAnyway
          labelSelector:
            matchLabels: { app: api }
      containers:
        - name: api
          image: artifacts.developer.gov.bc.ca/bcgov-docker-local/api:1.4.2
          ports: [{ containerPort: 8080, name: http }]
          resources:
            requests: { cpu: "500m", memory: "512Mi" }
            limits:   { cpu: "500m", memory: "512Mi" }   # Guaranteed QoS
          startupProbe:
            httpGet: { path: /livez, port: http }
            failureThreshold: 30
            periodSeconds: 5            # 150 s boot budget
          readinessProbe:
            httpGet: { path: /readyz, port: http }
            periodSeconds: 5
            failureThreshold: 3
          livenessProbe:
            httpGet: { path: /livez, port: http }
            periodSeconds: 10
            failureThreshold: 3
          lifecycle:
            preStop:
              exec: { command: ["/bin/sleep", "10"] }   # let endpoint propagate
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata: { name: api-pdb, namespace: abc123-prod }
spec:
  maxUnavailable: 1
  selector: { matchLabels: { app: api } }
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata: { name: api-hpa, namespace: abc123-prod }
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api
  minReplicas: 3
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target: { type: Utilization, averageUtilization: 70 }
  # Mandatory: explicit rampup (scaleUp) and rampdown (scaleDown).
  # Defaults are conservative and cause user-visible incidents on this platform.
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 30      # react quickly to traffic spikes
      policies:
        - type: Percent
          value: 100                      # at most double replicas per minute
          periodSeconds: 60
        - type: Pods
          value: 4                        # ...but never add more than 4 pods/min
          periodSeconds: 60
      selectPolicy: Max
    scaleDown:
      stabilizationWindowSeconds: 300     # wait 5 min before scaling down
      policies:
        - type: Percent
          value: 50                       # at most halve replicas per minute
          periodSeconds: 60
      selectPolicy: Max
```

### 3.2 `StatefulSet` for a 3-pod HA database

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata: { name: pg, namespace: abc123-prod }
spec:
  serviceName: pg-headless
  replicas: 3
  podManagementPolicy: OrderedReady     # default; use Parallel only if you understand the implications
  selector: { matchLabels: { app: pg } }
  template:
    metadata: { labels: { app: pg } }
    spec:
      terminationGracePeriodSeconds: 300
      affinity:
        podAntiAffinity:
          # Mandatory for multi-replica stateful workloads: never colocate.
          requiredDuringSchedulingIgnoredDuringExecution:
            - labelSelector:
                matchLabels: { app: pg }
              topologyKey: kubernetes.io/hostname
      topologySpreadConstraints:
        - maxSkew: 1
          topologyKey: topology.kubernetes.io/zone
          whenUnsatisfiable: ScheduleAnyway
          labelSelector:
            matchLabels: { app: pg }
      containers:
        - name: pg
          image: artifacts.developer.gov.bc.ca/bcgov-docker-local/patroni-postgres:16.4-3.0
          ports:
            - { containerPort: 5432, name: pg }
          resources:
            requests: { cpu: "1",   memory: "2Gi" }
            limits:   { cpu: "1",   memory: "2Gi" }
          readinessProbe:
            exec: { command: ["/usr/local/bin/pg-isready.sh"] }
            initialDelaySeconds: 15
            periodSeconds: 10
          livenessProbe:
            exec: { command: ["/usr/local/bin/pg-alive.sh"] }
            initialDelaySeconds: 60
            periodSeconds: 30
          volumeMounts:
            - { name: data, mountPath: /var/lib/postgresql/data }
  volumeClaimTemplates:
    - metadata: { name: data }
      spec:
        accessModes: [ "ReadWriteOnce" ]
        storageClassName: netapp-block-standard
        resources: { requests: { storage: "10Gi" } }
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata: { name: pg-pdb, namespace: abc123-prod }
spec:
  minAvailable: 2
  selector: { matchLabels: { app: pg } }
```

### 3.3 `CronJob` (PVC-mounting, ≥ 1 h cadence)

```yaml
apiVersion: batch/v1
kind: CronJob
metadata: { name: nightly-cleanup, namespace: abc123-prod }
spec:
  schedule: "0 2 * * *"                   # 02:00 daily
  timeZone: "America/Vancouver"           # never CRON_TZ= in schedule
  concurrencyPolicy: Forbid               # never overlap
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 1
  startingDeadlineSeconds: 300
  jobTemplate:
    spec:
      activeDeadlineSeconds: 3600         # bound stuck runs
      backoffLimit: 2
      ttlSecondsAfterFinished: 604800     # GC pods after 7 days
      template:
        spec:
          restartPolicy: OnFailure
          terminationGracePeriodSeconds: 60
          containers:
            - name: cleanup
              image: artifacts.developer.gov.bc.ca/bcgov-docker-local/cleanup:1.0.0
              resources:
                requests: { cpu: "100m", memory: "128Mi" }
                limits:   { cpu: "500m", memory: "256Mi" }
              volumeMounts:
                - { name: data, mountPath: /data }
          volumes:
            - name: data
              persistentVolumeClaim: { claimName: app-data }
```

### 3.4 `DaemonSet` skeleton

```yaml
apiVersion: apps/v1
kind: DaemonSet
metadata: { name: log-shipper, namespace: abc123-prod }
spec:
  selector: { matchLabels: { app: log-shipper } }
  template:
    metadata: { labels: { app: log-shipper } }
    spec:
      tolerations:
        - operator: Exists                # run on every node, incl. tainted
      containers:
        - name: shipper
          image: artifacts.developer.gov.bc.ca/bcgov-docker-local/log-shipper:2.1.0
          resources:
            requests: { cpu: "50m",  memory: "64Mi" }
            limits:   { cpu: "200m", memory: "128Mi" }
```

## 4. Probes — sane defaults and gotchas

| Probe | Purpose | Failure action | Typical settings |
| --- | --- | --- | --- |
| `readinessProbe` | Pod is ready to serve traffic | Removed from Service endpoints | `periodSeconds: 5`, `failureThreshold: 3` |
| `livenessProbe` | Pod is alive | Container restarted | `periodSeconds: 10`, `failureThreshold: 3`, `initialDelaySeconds` enough for boot **or** use a startupProbe |
| `startupProbe` | Slow-boot apps | Disables liveness/readiness until it passes once | `periodSeconds: 5`, `failureThreshold: 30` (150 s budget; raise `periodSeconds` to 10 for the 5-minute budget the slow-Java-boot example uses) |

Gotchas:
- A readiness probe that calls a downstream (DB, queue) cascades outages.
- A liveness probe that fails on transient errors traps the pod in `CrashLoopBackOff`.
- `exec` probes spawn a process every interval — keep the command trivial.
- For HTTP probes, the path should be unauthenticated and skip middleware that depends on downstreams.
- TCP-socket probes only test that the listener is open; that's "process up", not "app healthy".
- gRPC probes (`grpc:` field) are available on modern clusters; fall back to `exec: grpc_health_probe` for older builds.

## 5. SIGTERM, `terminationGracePeriodSeconds`, and `preStop`

Shutdown sequence:
1. Controller deletes the pod → API server sets `deletionTimestamp`.
2. kubelet sends `SIGTERM` to PID 1.
3. kubelet runs `lifecycle.preStop` (blocking) if defined.
4. kubelet waits up to `terminationGracePeriodSeconds`.
5. kubelet sends `SIGKILL`.

Recommendations:
- `terminationGracePeriodSeconds: 30` for stateless HTTP services.
- `terminationGracePeriodSeconds: 60–600` for stateful (uploads, large batches, DB).
- The Platform Operations team caps at 600 s on node drains; anything still running is `SIGKILL`'d.
- `preStop: { exec: { command: ["/bin/sleep", "10"] } }` is a common pattern to let the Service's endpoint removal propagate before the listener closes (eliminates a small window of connection refused).
- App responsibilities on `SIGTERM`: stop accepting new connections, fail readiness probe, finish in-flight requests, flush buffers, close downstream connections, exit 0.
- Containers using `tini`/`dumb-init` forward signals to the child by default — verify with `kill -TERM 1` in the container and watch the app log.

## 6. Kyverno admission policies that affect workload pods

| Policy | Rejects |
| --- | --- |
| `no-fast-cronjob` | `CronJob` with `schedule` more frequent than every 5 minutes. |
| `no-fast-cronjob-with-pvc` | `CronJob` mounting a PVC with `schedule` more frequent than every 1 hour. |
| `no-unsupported-timezone` | `CronJob` whose `schedule` contains `CRON_TZ=`. Use `spec.timeZone` instead. |
| `dataclass-label-required` *(Emerald only)* | Pods missing `DataClass: Low \| Medium \| High` label are auto-labelled `DataClass: Invalid`, then NSX-T blocks all traffic to/from them. |

Workaround for high-frequency cron with a PVC: convert to a long-running `Deployment` with [`go-crond`](https://github.com/webdevops/go-crond) (or any in-pod scheduler).

## 7. Defunct PIDs and PID-1 init containers

If PID 1 (your app) doesn't reap children, `<defunct>` processes accumulate. The platform sends an alert email to the Product Owner + Tech Lead.

Dockerfile recipes:

```dockerfile
# tini (small, single-purpose)
RUN microdnf install -y tini && microdnf clean all
ENTRYPOINT ["tini", "--", "/app/server"]
```

```dockerfile
# dumb-init (alternative, identical behaviour for this use)
RUN apk add --no-cache dumb-init
ENTRYPOINT ["dumb-init", "--", "/app/server"]
```

```dockerfile
# s6-overlay (for multi-process containers — rare but supported)
ARG S6_OVERLAY_VERSION=3.1.6.2
ADD https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-noarch.tar.xz /tmp
RUN tar -C / -Jxpf /tmp/s6-overlay-noarch.tar.xz
ENTRYPOINT ["/init"]
```

Quick band-aid when the alert fires: `oc -n <ns> delete pod <name>`. The underlying bug returns until PID 1 is fixed.

## 8. HPA and VPA decision matrix

| Need | Use |
| --- | --- |
| Scale on CPU or memory utilization | `HorizontalPodAutoscaler` (`autoscaling/v2`) on `Resource` metric |
| Rightsizing recommendations for a workload with drifting footprint | `VerticalPodAutoscaler` in `updateMode: "Off"` (recommendations only — read with `oc describe vpa`) |
| Both CPU autoscaling and memory rightsizing | HPA on CPU + VPA `Off` (never `Auto` on the same metric) |

Rules of thumb:
- `HorizontalPodAutoscaler` is mandatory for any long-running workload, not optional.
- `minReplicas ≥ 2` in production (single replica = outage on node drain).
- `maxReplicas` bounded by `compute-long-running-quota` — math out the worst case (`maxReplicas × requests.cpu` ≤ quota CPU).
- Always pair HPA with a PDB so scale-down can't violate the budget during a drain.
- Always set `spec.behavior.scaleUp` (rampup) and `spec.behavior.scaleDown` (rampdown) explicitly — see §3.1 for the baseline (`scaleUp.stabilizationWindowSeconds: 30` + `Percent: 100 / periodSeconds: 60`; `scaleDown.stabilizationWindowSeconds: 300` + `Percent: 50 / periodSeconds: 60`). Tune from observed traffic, but never ship defaults.
- Always set `podAntiAffinity` on `topologyKey: kubernetes.io/hostname` so HPA-added replicas don't pile onto the same node and erase the resilience benefit.

## 9. Workload error cheat sheet

| Status | Likely cause | First check |
| --- | --- | --- |
| `Pending` (`FailedScheduling`) | No node has enough free request capacity for this pod | Lower requests, scale horizontally, or check for stuck terminating pods consuming reserved capacity |
| `Pending` (`Unschedulable`) | Taints/affinity rule excluded all nodes | `oc describe pod` → Events; adjust nodeSelector / tolerations |
| `ImagePullBackOff` | Wrong image path or missing `imagePullSecrets` | This is an `openshift-images` concern — see that skill |
| `CreateContainerConfigError` | Referenced ConfigMap / Secret doesn't exist | `oc get configmap`, `oc get secret`; verify name and namespace |
| `CrashLoopBackOff` | App exits non-zero on start | `oc logs <pod> --previous` shows the prior run's stdout/stderr |
| `OOMKilled` | Working set exceeded `limits.memory` | Bump limit (after measuring) or fix the leak; check Sysdig P99 |
| `Evicted` (reason `MemoryPressure` / `DiskPressure`) | Node ran out, pod was `BestEffort` or `Burstable` over request | Move to `Guaranteed` QoS; investigate node-level pressure |
| `Evicted` (reason `TerminationGracePeriodExceeded`) | App didn't exit within grace period | Fix SIGTERM handling, then revisit grace period |
| `Pending` `BackoffLimitExceeded` (Job) | Job retried `backoffLimit` times | `oc describe job` → events; look at the failed pod's logs |
| `Active` Job stuck forever | No `activeDeadlineSeconds` set, app hung | Add `activeDeadlineSeconds`; investigate the hang |
| `DeadlineExceeded` (CronJob) | Job didn't start within `startingDeadlineSeconds` | Cluster was under load, or the CronJob was suspended; bump the deadline if appropriate |

## 10. Useful `oc` recipes for workload triage

```bash
# What's pending and why
oc get pods --field-selector=status.phase=Pending
oc describe pod <name>

# What pods are crashlooping and how many restarts
oc get pods --sort-by=.status.containerStatuses[0].restartCount

# Previous container logs (the run that crashed)
oc logs <pod> --previous

# Live resource use vs requests (requires metrics server, available platform-wide)
oc adm top pod
oc adm top pod --containers

# Roll out a new image / restart
oc set image deployment/<name> <container>=<new-image>
oc rollout restart deployment/<name>
oc rollout status deployment/<name>
oc rollout undo deployment/<name>

# Show all PDBs and current disruptions allowed
oc get pdb
oc get pdb <name> -o jsonpath='{.status.disruptionsAllowed}'

# CronJob debugging — show recent runs
oc get jobs -l job-name --sort-by=.metadata.creationTimestamp
oc get cronjob <name> -o yaml | grep -E 'lastScheduleTime|lastSuccessfulTime'
```

## 11. Source-of-truth links

- Platform Developer Docs site: <https://developer.gov.bc.ca/docs/default/component/platform-developer-docs>
- Source repo (PRs in flight): <https://github.com/bcgov/platform-developer-docs>
- Platform Product Registry (contacts, quotas): <https://registry.developer.gov.bc.ca/>
- BCDevOps/backup-container: <https://github.com/BCDevOps/backup-container>
- Kubernetes upstream docs: <https://kubernetes.io/docs/>
- Red Hat OpenShift Container Platform docs: <https://docs.openshift.com/>
- tini: <https://github.com/krallin/tini> · dumb-init: <https://github.com/Yelp/dumb-init> · s6-overlay: <https://github.com/just-containers/s6-overlay>
