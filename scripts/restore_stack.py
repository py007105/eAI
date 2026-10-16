"""Debug helper: recreate one managed container from an image, printing the Docker error if any.

    python scripts/restore_stack.py inventory eai/inventory:v1
"""
import sys

import docker

svc, image = sys.argv[1], sys.argv[2]
d = docker.from_env()
cs = d.containers.list(all=True, filters={"label": f"com.docker.compose.service={svc}"})
print("existing containers:", [(c.name, c.status) for c in cs])
net = "eai_eai"
vol = f"eai_{svc}-data:/data"
host_cfg = d.api.create_host_config(binds=[vol] if svc != "web" else None, mem_limit="256m",
                                    port_bindings={"8000/tcp": 8080} if svc == "web" else None)
net_cfg = d.api.create_networking_config({net: d.api.create_endpoint_config(aliases=[svc])})
labels = {"com.docker.compose.project": "eai", "com.docker.compose.service": svc, "eai.managed": "true",
          "eai.role": "app", "com.docker.compose.oneoff": "False"}
new = d.api.create_container(image, name=f"eai-{svc}-1", environment=["OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4318",
                             "CHAOS_TOKEN=evaluator-only"], labels=labels, host_config=host_cfg,
                             networking_config=net_cfg, ports=["8000/tcp"] if svc == "web" else None)
d.api.start(new["Id"])
print("started", new["Id"][:12])
