# To-Do App on Kubernetes - Runbook

Tip: save every terminal output with `| tee logs/<name>.txt`, and take a screenshot at each [SCREENSHOT] mark.

## 0. Prerequisites
Docker Desktop (or Docker Engine), kubectl, minikube.

    mkdir -p logs

## Task 1 - Cluster, deploy 3 replicas + Service

    minikube start --driver=docker --nodes=1
    minikube addons enable metrics-server
    kubectl get nodes | tee logs/01-nodes.txt

Build images INSIDE minikube's Docker daemon (no registry needed):

    eval $(minikube docker-env)            # Windows PowerShell: & minikube -p minikube docker-env --shell powershell | Invoke-Expression
    docker build -t todo-app:v1 --build-arg APP_VERSION=v1 app/
    docker build -t todo-app:v2 --build-arg APP_VERSION=v2 app/
    docker build -t todo-app:v3-crash --build-arg APP_VERSION=v3-crash app/

Deploy:

    kubectl apply -f k8s/deployment.yaml -f k8s/service.yaml -f k8s/pdb.yaml
    kubectl rollout status deployment/todo-app
    kubectl get deploy,rs,pods,svc,endpoints -o wide | tee logs/02-deployed.txt   # [SCREENSHOT]

Open the app (keep this URL):

    minikube service todo-svc --url
    # Docker driver on Win/Mac: keep that terminal open, use the printed 127.0.0.1 URL

Refresh the page several times: the "Served by pod" name changes = load balancing across 3 pods.

## Task 2 - Rolling update, failed update, rollback

Terminal B (watch live):   kubectl get pods -w
Terminal C (availability):

    URL=<your service url>
    while true; do curl -s -o /dev/null -w "%{http_code} " $URL/healthz; sleep 0.5; done

### 2a. Good update v1 -> v2

    kubectl annotate deployment/todo-app kubernetes.io/change-cause="upgrade to v2" --overwrite
    kubectl set image deployment/todo-app todo=todo-app:v2
    kubectl rollout status deployment/todo-app | tee logs/03-rollout-v2.txt
    kubectl rollout history deployment/todo-app | tee logs/03-history.txt          # [SCREENSHOT] pods -w + curl all 200

### 2b. Deliberately failed update (a): image that doesn't exist

    kubectl annotate deployment/todo-app kubernetes.io/change-cause="bad image tag" --overwrite
    kubectl set image deployment/todo-app todo=todo-app:v9-missing
    kubectl rollout status deployment/todo-app --timeout=70s      # times out
    kubectl get pods | tee logs/04-failed-pods.txt                # ErrImagePull / ImagePullBackOff
    kubectl describe deployment todo-app | tee logs/04-describe-deploy.txt
    kubectl describe pod <the-failing-pod> | tee logs/04-describe-pod.txt
    kubectl get events --sort-by=.lastTimestamp | tee logs/04-events.txt   # [SCREENSHOT]

Expected: 3 old v2 pods stay Running/Ready (maxUnavailable: 0), 1 new pod stuck; curl keeps returning 200.
After 60s the Deployment shows condition Progressing=False, reason ProgressDeadlineExceeded.

### 2c. Rollback

    kubectl rollout undo deployment/todo-app
    kubectl rollout status deployment/todo-app
    kubectl get deploy todo-app -o jsonpath='{.spec.template.spec.containers[0].image}'; echo   # todo-app:v2
    kubectl rollout history deployment/todo-app | tee logs/05-rollback.txt

### 2d. (Optional, 2nd failure type) crashing release

    kubectl set image deployment/todo-app todo=todo-app:v3-crash
    kubectl get pods                       # CrashLoopBackOff, RESTARTS climbing
    kubectl logs <bad-pod> --previous      # "FATAL: simulated startup failure"
    kubectl rollout undo deployment/todo-app

## Task 3 - Delete a pod and watch recovery

    kubectl get pods -w                    # Terminal B
    kubectl delete pod <one-pod-name>      # Terminal A
    kubectl get events --sort-by=.lastTimestamp | tee logs/06-delete-events.txt
    kubectl describe rs -l app=todo-app | tee logs/06-describe-rs.txt             # [SCREENSHOT]

Expected: old pod -> Terminating, a new pod is created immediately by the ReplicaSet,
ContainerCreating -> Running -> Ready within seconds. curl stays 200 (the other 2 pods serve).

Optional - simulate a real crash (liveness restart):

    kubectl exec <pod> -- kill 1           # container exits; kubelet restarts it, RESTARTS=1
    kubectl describe pod <pod> | tee logs/06-crash-describe.txt

Optional - observe what 1 replica would have meant:

    kubectl scale deploy/todo-app --replicas=1
    kubectl delete pod -l app=todo-app     # curl shows connection errors during recovery
    kubectl scale deploy/todo-app --replicas=3

## Task 4 - Observability

    kubectl get pods -o wide | tee logs/07-pods.txt
    kubectl top pods | tee logs/07-top-pods.txt        # needs metrics-server (~1 min after enabling)
    kubectl top nodes
    kubectl get pods -o custom-columns=NAME:.metadata.name,READY:.status.containerStatuses[0].ready,RESTARTS:.status.containerStatuses[0].restartCount
    kubectl logs deploy/todo-app --tail=20
    kubectl logs -l app=todo-app --prefix --tail=5 | tee logs/07-logs.txt
    kubectl describe pod <pod> | tee logs/07-describe.txt

Generate a little load to see CPU move:

    for i in $(seq 1 2000); do curl -s $URL > /dev/null; done
    kubectl top pods

Optional Prometheus + Grafana:

    helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
    helm install mon prometheus-community/kube-prometheus-stack -n monitoring --create-namespace
    kubectl -n monitoring port-forward svc/mon-grafana 3000:80    # admin / prom-operator

## Cleanup

    kubectl delete -f k8s/
    minikube delete
