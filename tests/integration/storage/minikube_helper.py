import subprocess
import time
import os

class MinikubeHelper:
    @staticmethod
    def start_minikube():
        """Start Minikube with required configurations"""
        cmd = [
            "minikube",
            "start",
            "--memory=4096",
            "--cpus=2",
            "--disk-size=20GB",
            "--driver=docker",
            "--feature-gates=VolumeExpansion=true"
        ]
        subprocess.run(cmd, check=True)
        
        # Enable CSI driver addon
        subprocess.run(["minikube", "addons", "enable", "csi-hostpath-driver"], check=True)
    
    @staticmethod
    def stop_minikube():
        """Stop Minikube cluster"""
        subprocess.run(["minikube", "stop"], check=True)
    
    @staticmethod
    def delete_minikube():
        """Delete Minikube cluster"""
        subprocess.run(["minikube", "delete"], check=True)
    
    @staticmethod
    def load_images():
        """Load required images into Minikube"""
        # Set docker env to Minikube's docker daemon
        subprocess.run(["eval $(minikube docker-env)"], shell=True, check=True)
        
        # Build and load DFS images
        subprocess.run([
            "docker",
            "build",
            "-t",
            "dfs-node:latest",
            "-f",
            "../../Dockerfile",
            "../.."
        ], check=True)
    
    @staticmethod
    def apply_manifests():
        """Apply Kubernetes manifests"""
        manifests = [
            "../../kubernetes/base/storage-class.yaml",
            "../../kubernetes/base/service.yaml",
            "../../kubernetes/base/statefulset.yaml"
        ]
        
        for manifest in manifests:
            subprocess.run(["kubectl", "apply", "-f", manifest], check=True)
    
    @staticmethod
    def wait_for_pods(namespace, label_selector, timeout=300):
        """Wait for pods to be ready"""
        cmd = [
            "kubectl",
            "wait",
            "--namespace",
            namespace,
            "--for=condition=ready",
            "pod",
            "-l",
            label_selector,
            f"--timeout={timeout}s"
        ]
        subprocess.run(cmd, check=True)
    
    @staticmethod
    def setup_test_environment():
        """Setup complete test environment"""
        MinikubeHelper.start_minikube()
        MinikubeHelper.load_images()
        
        # Create namespace
        subprocess.run([
            "kubectl",
            "create",
            "namespace",
            "distributed-fs"
        ], check=True)
        
        MinikubeHelper.apply_manifests()
        MinikubeHelper.wait_for_pods("distributed-fs", "app=dfs-node")
    
    @staticmethod
    def cleanup_test_environment():
        """Cleanup test environment"""
        MinikubeHelper.delete_minikube()
    
    @staticmethod
    def get_minikube_ip():
        """Get Minikube IP address"""
        result = subprocess.run(
            ["minikube", "ip"],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()

    @staticmethod
    def get_service_url(service_name, namespace="distributed-fs"):
        """Get service URL"""
        cmd = [
            "minikube",
            "service",
            "--url",
            service_name,
            "-n",
            namespace
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout.strip()
