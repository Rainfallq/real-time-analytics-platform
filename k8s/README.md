# Kubernetes deployment

Tested target: any Kubernetes cluster with an NGINX ingress controller (k3s, minikube, Docker Desktop).

    # 1. build the image and make it available to the cluster
    docker build -f infrastructure/docker/Dockerfile -t rtap-app:latest .
    #    minikube: minikube image load rtap-app:latest     kind: kind load docker-image rtap-app:latest
    #    k3s:      docker save rtap-app:latest | sudo k3s ctr images import -

    # 2. namespace and secret (see secret.example.yaml for the command)
    kubectl apply -f k8s/namespace.yaml
    kubectl -n rtap create secret generic rtap-secret --from-literal=SECRET_KEY=... \
      --from-literal=POSTGRES_PASSWORD=... \
      --from-literal=DATABASE_URL='postgresql+asyncpg://rtap_user:<password>@postgres:5432/analytics'

    # 3. everything else
    kubectl apply -k k8s
    kubectl -n rtap get pods -w

    # 4. check
    kubectl -n rtap port-forward svc/rtap-api 8000:80      # http://localhost:8000/docs
    kubectl -n rtap port-forward svc/prometheus 9090:9090  # Status > Rules, Alerts
    kubectl -n rtap port-forward svc/grafana 3000:3000     # dashboard "RTAP overview"

The migration Job and the topic Job must finish before the API becomes ready.
Files in k8s/monitoring are copies of infrastructure/monitoring (keep them in sync).
The Grafana admin password is taken from POSTGRES_PASSWORD of the secret: change this for anything but a demo.
