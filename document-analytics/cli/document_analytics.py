#!/usr/bin/env python3
"""Document Analytics CLI.

This CLI tool lets users process Markdown documents and analyze them by topic.
It can run in local mode or distribute work to Kubernetes services.
"""

import os
import sys
import glob
import json
import time
import requests
import argparse
import zmq
from typing import List, Dict, Any, Optional

# Add the parent directory to sys.path to import the library
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from doc_analytics_lib import process_document


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Document Analytics CLI')
    
    # Document selection
    parser.add_argument('--documents', type=str, action='append', required=True, 
                        help='Document file or glob pattern (can be specified multiple times)')
    
    # Topic selection
    parser.add_argument('--topic', action='append', dest='topics',
                        help='Topic to analyze (can be specified multiple times)')
    
    # Service configuration
    parser.add_argument('--local', action='store_true',
                        help='Run in local mode without services')
    parser.add_argument('--service-url', type=str, default='http://localhost:8080',
                        help='URL of the document analytics service')
    parser.add_argument('--num-processors', type=int, default=2,
                        help='Number of document processors to use')
    
    # Kubernetes options
    parser.add_argument('--k8s', action='store_true',
                        help='Use with Kubernetes (will rewrite paths)')
    parser.add_argument('--configmap-path', type=str, default='/documents',
                        help='Path where the document ConfigMap is mounted in K8s pods')
    
    # Output options
    parser.add_argument('--json', action='store_true',
                        help='Output results as JSON')

    # Debug options
    parser.add_argument('--debug', action='store_true',
                        help='Enable debug mode to fetch pod logs before cleanup')
    
    return parser.parse_args()


def aggregate_results(results_dict):
    """
    Aggregate results from multiple documents into a single result set.
    
    Args:
        results_dict: Dictionary of topic results from multiple documents
        
    Returns:
        Aggregated results by topic
    """
    aggregated = {}
    
    for doc_results in results_dict.values():
        for topic, metrics in doc_results.items():
            if topic not in aggregated:
                aggregated[topic] = {
                    "topic": topic,
                    "line_count": 0,
                    "word_count": 0,
                    "char_count": 0,
                    "doc_count": 0
                }
            
            aggregated[topic]["line_count"] += metrics["line_count"]
            aggregated[topic]["word_count"] += metrics["word_count"]
            aggregated[topic]["char_count"] += metrics["char_count"]
            aggregated[topic]["doc_count"] += 1
    
    return aggregated


def process_locally(documents: List[str], topics: Optional[List[str]] = None) -> Dict[str, Dict[str, Any]]:
    """Process documents locally without using services.
    
    Args:
        documents: List of document paths
        topics: Optional list of topics to filter
        
    Returns:
        Results by topic
    """
    print(f"Processing {len(documents)} documents locally...")
    
    # Store results by document
    all_results = {}
    
    for doc_path in documents:
        print(f"Processing document: {doc_path}")
        
        try:
            # Process document using the library function
            doc_results = process_document(doc_path, topics)
            all_results[doc_path] = doc_results
        except Exception as e:
            print(f"Error processing document {doc_path}: {str(e)}")
    
    # Aggregate results across all documents
    return aggregate_results(all_results)


def rewrite_paths_for_k8s(documents: List[str], configmap_path: str) -> List[str]:
    """
    Rewrite local file paths to match paths in the Kubernetes ConfigMap.
    
    Args:
        documents: List of local document paths
        configmap_path: Path where the ConfigMap is mounted in the K8s pods
        
    Returns:
        List of rewritten paths that will work inside the Kubernetes pods
    """
    rewritten_paths = []
    
    for doc_path in documents:
        # Get just the filename without the directory path
        filename = os.path.basename(doc_path)
        # Join with the ConfigMap mount path
        k8s_path = os.path.join(configmap_path, filename)
        rewritten_paths.append(k8s_path)
        print(f"Rewrote path: {doc_path} -> {k8s_path}")
    
    return rewritten_paths


def process_with_services(documents: List[str], topics: List[str], service_url: str, 
                          num_processors: int, use_k8s: bool = False, 
                          configmap_path: str = '/documents',
                          debug: bool = False) -> Dict[str, Dict[str, Any]]:
    """Process documents using the document analytics services.
    
    Args:
        documents: List of document paths
        topics: List of topics to analyze
        service_url: URL of the document analytics service
        num_processors: Number of document processors to use
        use_k8s: Whether to rewrite paths for Kubernetes
        configmap_path: Path where the ConfigMap is mounted in K8s pods
        debug: Whether to fetch pod logs before cleanup
        
    Returns:
        Results by topic
    """
    print(f"Processing {len(documents)} documents using services...")
    
    # Make absolute paths
    abs_documents = [os.path.abspath(doc) for doc in documents]
    
    # Rewrite paths for Kubernetes if needed
    if use_k8s:
        print("Rewriting paths for Kubernetes...")
        doc_paths = rewrite_paths_for_k8s(abs_documents, configmap_path)
    else:
        doc_paths = abs_documents
    
    # Start the services
    print("Starting services...")
    response = requests.post(f"{service_url}/start", json={
        "documents": doc_paths,
        "topics": topics,
        "num_processors": num_processors
    })
    
    if response.status_code != 200:
        print(f"Error starting services: {response.text}")
        return {}
    
    # Check if the deployment is starting
    start_data = response.json()
    if start_data.get("status") not in ["accepted", "in_progress"]:
        print(f"Error starting services: {start_data.get('message', 'Unknown error')}")
        return {}
    
    print("Services deployment started. Waiting for resources to be ready...")
    
    # Poll for deployment status until completed or error
    max_retries = 60  # 10 minutes max
    for retry in range(max_retries):
        # Get deployment status
        status_response = requests.get(f"{service_url}/status")
        
        if status_response.status_code != 200:
            print(f"Error checking deployment status: {status_response.text}")
            return {}
        
        status_data = status_response.json()
        deployment_status = status_data.get("deployment_status", {})
        status = deployment_status.get("status", "unknown")
        
        # Print progress
        completed = len(deployment_status.get("completed_steps", []))
        total = completed + len(deployment_status.get("pending_steps", []))
        print(f"Deployment progress: {completed}/{total} steps completed. Status: {status}")
        
        # Check if deployment is complete or failed
        if status == "completed":
            print("All services deployed successfully!")
            break
        elif status == "error":
            print(f"Deployment failed: {deployment_status.get('message', 'Unknown error')}")
            return {}
        
        # Wait before polling again
        if retry < max_retries - 1:
            print("Waiting for resources to be ready...")
            time.sleep(10)  # Check every 10 seconds
    else:
        print("Timed out waiting for deployment to complete")
        return {}
    
    # Wait a bit for all services to be fully operational
    print("Processing documents, please wait...")
    time.sleep(5)
    
    # Poll for results every 5 seconds
    max_retries = 30
    results = {}
    for retry in range(max_retries):
        # Get results
        print(f"Fetching results (attempt {retry+1}/{max_retries})...")
        response = requests.get(f"{service_url}/results")
        
        if response.status_code != 200:
            print(f"Error getting results: {response.text}")
            return {}
        
        results_data = response.json()
        
        # Check if we have results for all topics
        if all(topic in results_data["results"] for topic in topics):
            print("All results received successfully.")
            results = results_data["results"]
            break
        
        # Wait and retry
        if retry < max_retries - 1:
            time.sleep(5)
    
    if not results:
        print("Timed out waiting for results")
    
    # In debug mode, fetch pod logs before cleanup
    if debug:
        pod_logs = fetch_pod_logs(service_url)
        if pod_logs:
            print("\n===================== POD LOGS ======================\n")
            for pod_name, log_content in pod_logs.items():
                print(f"\n--- {pod_name} Logs ---\n")
                print(log_content)
                print("\n" + "-" * 50)
            print("\n=====================================================\n")
    
    # Clean up after processing is complete
    cleanup_services(service_url)
    
    return results


def cleanup_services(service_url: str) -> bool:
    """Clean up all document analytics services after processing.
    
    Args:
        service_url: URL of the document analytics service
        
    Returns:
        True if cleanup was successful, False otherwise
    """
    print("Cleaning up services...")
    try:
        response = requests.post(f"{service_url}/cleanup")
        if response.status_code == 200:
            print("All services cleaned up successfully.")
            return True
        else:
            print(f"Error cleaning up services: {response.text}")
            return False
    except Exception as e:
        print(f"Exception during service cleanup: {str(e)}")
        return False


def fetch_pod_logs(service_url: str) -> Dict[str, str]:
    """Fetch logs from all document analytics pods before cleanup.
    
    Args:
        service_url: URL of the document analytics service
        
    Returns:
        Dictionary mapping pod names to their logs
    """
    print("Fetching pod logs for debugging...")
    try:
        response = requests.get(f"{service_url}/logs")
        if response.status_code == 200:
            logs_data = response.json()
            print(f"Successfully fetched logs from {len(logs_data.get('logs', {}))} pods")
            return logs_data.get("logs", {})
        else:
            print(f"Error fetching logs: {response.text}")
            return {}
    except Exception as e:
        print(f"Exception when fetching logs: {str(e)}")
        return {}


def print_results(results: Dict[str, Dict[str, Any]], as_json: bool = False) -> None:
    """Print results to the console.
    
    Args:
        results: Results by topic
        as_json: Whether to print as JSON
    """
    if as_json:
        print(json.dumps(results, indent=2))
        return
    
    print("\n=========== DOCUMENT ANALYTICS RESULTS ===========")
    
    # Sort topics alphabetically but put "(No Topic)" last
    sorted_topics = sorted(results.keys(), key=lambda x: (x == "(No Topic)", x))
    
    for topic in sorted_topics:
        metrics = results[topic]
        
        print(f"\n--- Topic: {topic} ---")
        print(f"Documents:  {metrics['doc_count']}")
        print(f"Lines:      {metrics['line_count']}")
        print(f"Words:      {metrics['word_count']}")
        print(f"Characters: {metrics['char_count']}")
    
    print("\n=================================================")


def main():
    """Main entry point."""
    args = parse_args()
    
    # Expand document glob pattern
    document_paths = []
    for pattern in args.documents:
        document_paths.extend(glob.glob(pattern, recursive=True))
    if not document_paths:
        print(f"No documents found matching patterns: {args.documents}")
        return 1
    
    # Ensure we have at least one topic
    topics = args.topics or []
    
    # Process documents
    if args.local:
        results = process_locally(document_paths, topics)
    else:
        results = process_with_services(
            document_paths, 
            topics, 
            args.service_url, 
            args.num_processors,
            use_k8s=args.k8s,
            configmap_path=args.configmap_path,
            debug=args.debug
        )
    
    # Print results
    if results:
        print_results(results, args.json)
        return 0
    else:
        print("No results obtained")
        return 1


if __name__ == "__main__":
    sys.exit(main())