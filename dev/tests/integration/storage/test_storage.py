import pytest
import kubernetes
from kubernetes import client, config
import time
import os
from kubernetes.stream import stream


@pytest.fixture
def k8s_client():
    config.load_kube_config()
    return client.CoreV1Api()


@pytest.fixture
def storage_class():
    return {
        "name": "dfs-hybrid-storage",
        "provisioner": "dfs.csi.k8s.io",
    }


@pytest.fixture
def test_namespace(k8s_client):
    namespace = "dfs-test"
    ns = client.V1Namespace(metadata=client.V1ObjectMeta(name=namespace))
    k8s_client.create_namespace(ns)
    yield namespace
    k8s_client.delete_namespace(namespace)


def test_storage_class_creation(k8s_client, storage_class):
    """Test storage class creation and validation"""
    api = client.StorageV1Api()

    # Create storage class
    sc = client.V1StorageClass(
        metadata=client.V1ObjectMeta(name=storage_class["name"]),
        provisioner=storage_class["provisioner"],
    )
    api.create_storage_class(sc)

    # Verify storage class exists
    sc_list = api.list_storage_class()
    assert any(item.metadata.name == storage_class["name"] for item in sc_list.items)


def test_pvc_provisioning(k8s_client, test_namespace, storage_class):
    """Test PVC provisioning and binding"""
    # Create PVC
    pvc = client.V1PersistentVolumeClaim(
        metadata=client.V1ObjectMeta(name="test-pvc"),
        spec=client.V1PersistentVolumeClaimSpec(
            access_modes=["ReadWriteOnce"],
            resources=client.V1ResourceRequirements(requests={"storage": "1Gi"}),
            storage_class_name=storage_class["name"],
        ),
    )

    k8s_client.create_namespaced_persistent_volume_claim(
        namespace=test_namespace, body=pvc
    )

    # Wait for PVC to be bound
    timeout = 60
    start_time = time.time()
    while time.time() - start_time < timeout:
        pvc_status = k8s_client.read_namespaced_persistent_volume_claim_status(
            name="test-pvc", namespace=test_namespace
        )
        if pvc_status.status.phase == "Bound":
            break
        time.sleep(2)

    assert pvc_status.status.phase == "Bound"


def test_pod_volume_mount(k8s_client, test_namespace, storage_class):
    """Test mounting volume in pod and writing data"""
    # Create PVC
    pvc = client.V1PersistentVolumeClaim(
        metadata=client.V1ObjectMeta(name="test-mount-pvc"),
        spec=client.V1PersistentVolumeClaimSpec(
            access_modes=["ReadWriteOnce"],
            resources=client.V1ResourceRequirements(requests={"storage": "1Gi"}),
            storage_class_name=storage_class["name"],
        ),
    )

    k8s_client.create_namespaced_persistent_volume_claim(
        namespace=test_namespace, body=pvc
    )

    # Create pod with volume mount
    pod = client.V1Pod(
        metadata=client.V1ObjectMeta(name="test-pod"),
        spec=client.V1PodSpec(
            containers=[
                client.V1Container(
                    name="test-container",
                    image="busybox",
                    command=[
                        "sh",
                        "-c",
                        "echo 'test data' > /data/test.txt && sleep 3600",
                    ],
                    volume_mounts=[
                        client.V1VolumeMount(name="test-volume", mount_path="/data")
                    ],
                )
            ],
            volumes=[
                client.V1Volume(
                    name="test-volume",
                    persistent_volume_claim=client.V1PersistentVolumeClaimVolumeSource(
                        claim_name="test-mount-pvc"
                    ),
                )
            ],
        ),
    )

    k8s_client.create_namespaced_pod(namespace=test_namespace, body=pod)

    # Wait for pod to be running
    timeout = 60
    start_time = time.time()
    while time.time() - start_time < timeout:
        pod_status = k8s_client.read_namespaced_pod_status(
            name="test-pod", namespace=test_namespace
        )
        if pod_status.status.phase == "Running":
            break
        time.sleep(2)

    assert pod_status.status.phase == "Running"

    # Verify data was written
    exec_command = ["cat", "/data/test.txt"]

    result = stream(
        k8s_client.connect_get_namespaced_pod_exec,
        "test-pod",
        test_namespace,
        command=exec_command,
        stderr=True,
        stdin=False,
        stdout=True,
        tty=False,
    )

    assert "test data" in result


def test_volume_expansion(k8s_client, test_namespace, storage_class):
    """Test volume expansion capability"""
    # Create PVC
    pvc = client.V1PersistentVolumeClaim(
        metadata=client.V1ObjectMeta(name="test-expand-pvc"),
        spec=client.V1PersistentVolumeClaimSpec(
            access_modes=["ReadWriteOnce"],
            resources=client.V1ResourceRequirements(requests={"storage": "1Gi"}),
            storage_class_name=storage_class["name"],
        ),
    )

    k8s_client.create_namespaced_persistent_volume_claim(
        namespace=test_namespace, body=pvc
    )

    # Wait for PVC to be bound
    timeout = 60
    start_time = time.time()
    while time.time() - start_time < timeout:
        pvc_status = k8s_client.read_namespaced_persistent_volume_claim_status(
            name="test-expand-pvc", namespace=test_namespace
        )
        if pvc_status.status.phase == "Bound":
            break
        time.sleep(2)

    # Expand volume
    patch = {"spec": {"resources": {"requests": {"storage": "2Gi"}}}}

    k8s_client.patch_namespaced_persistent_volume_claim(
        name="test-expand-pvc", namespace=test_namespace, body=patch
    )

    # Verify expansion
    timeout = 60
    start_time = time.time()
    while time.time() - start_time < timeout:
        pvc_status = k8s_client.read_namespaced_persistent_volume_claim_status(
            name="test-expand-pvc", namespace=test_namespace
        )
        if pvc_status.spec.resources.requests["storage"] == "2Gi":
            break
        time.sleep(2)

    assert pvc_status.spec.resources.requests["storage"] == "2Gi"
