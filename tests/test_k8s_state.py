from types import SimpleNamespace as NS
from unittest.mock import Mock

from eternalai.sources.k8s_state import KubernetesView


def test_state_reports_readiness_revision_and_oom():
    deployment = NS(metadata=NS(name="frontend", uid="uid", creation_timestamp=None,
                                annotations={"deployment.kubernetes.io/revision": "3"}),
                    spec=NS(replicas=1, selector=NS(match_labels={"app": "frontend"}),
                            template=NS(spec=NS(containers=[NS(image="shop/frontend:v3")]))),
                    status=NS(ready_replicas=0))
    pod = NS(status=NS(container_statuses=[NS(last_state=NS(terminated=NS(reason="OOMKilled")))]))
    apps, core = Mock(), Mock()
    apps.list_namespaced_deployment.return_value.items = [deployment]
    core.list_namespaced_pod.return_value.items = [pod]
    view = KubernetesView("shop", apps, core)
    state = view.poll()["frontend"]
    assert not state.running and state.oom_killed and state.release_seq == 3
    assert state.image_tag == "v3"
    core.list_namespaced_pod.assert_called_with("shop", label_selector="app=frontend")
    deployment.status.ready_replicas = 1
    assert view.poll()["frontend"].running
    assert view.events[-1]["kind"] == "readiness"
    assert view.logs("frontend") == []


def test_image_pull_failure_requires_previous_release():
    deployment = NS(metadata=NS(annotations={"deployment.kubernetes.io/revision": "2"}),
                    spec=NS(selector=NS(match_labels={"app": "catalog"})))
    pod = NS(status=NS(container_statuses=[NS(state=NS(waiting=NS(reason="ImagePullBackOff")))]))
    apps, core = Mock(), Mock()
    apps.read_namespaced_deployment.return_value = deployment
    core.list_namespaced_pod.return_value.items = [pod]
    view = KubernetesView("shop", apps, core)
    assert view.image_pull_failure("catalog")
    deployment.metadata.annotations["deployment.kubernetes.io/revision"] = "1"
    assert not view.image_pull_failure("catalog")
