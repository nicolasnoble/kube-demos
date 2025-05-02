#!/usr/bin/env python3
"""
Adder Service CLI Client

A command-line interface for interacting with the adder service API
running on a Kubernetes cluster or using the adder library directly.
"""

import sys
import os
import click
import requests
import json
from urllib.parse import urljoin

# Import the adder_lib package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from adder_lib import add as adder_lib_add, AdderException


class AdderServiceClient:
    """Client for interacting with the adder service API."""
    
    def __init__(self, base_url):
        """
        Initialize the client with the base URL of the adder service.
        
        Args:
            base_url (str): The base URL of the adder service API
        """
        self.base_url = base_url
        # Ensure the base URL ends with a slash
        if not self.base_url.endswith('/'):
            self.base_url += '/'
    
    def check_health(self):
        """
        Check if the adder service is healthy.
        
        Returns:
            bool: True if the service is healthy, False otherwise
        """
        try:
            url = urljoin(self.base_url, 'health')
            response = requests.get(url, timeout=5)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False
    
    def add(self, a, b):
        """
        Add two numbers using the adder service API.
        
        Args:
            a (float): First number
            b (float): Second number
            
        Returns:
            float or None: The result of adding a and b, or None if the request failed
            
        Raises:
            ValueError: If the API returns an error
        """
        try:
            url = urljoin(self.base_url, 'add')
            payload = {'a': a, 'b': b}
            headers = {'Content-Type': 'application/json'}
            
            response = requests.post(url, data=json.dumps(payload), headers=headers, timeout=5)
            
            if response.status_code == 200:
                return response.json()['result']
            else:
                error = response.json().get('error', 'Unknown error')
                raise ValueError(f"API Error: {error}")
                
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Failed to connect to adder service: {e}")


@click.group()
def cli():
    """Command-line interface for the Kubernetes adder service."""
    pass


@cli.command()
@click.option('--url', '-u', required=True, help='Base URL of the adder service API')
def health(url):
    """Check if the adder service is healthy."""
    client = AdderServiceClient(url)
    try:
        if client.check_health():
            click.echo(click.style("✅ Adder service is healthy", fg="green"))
        else:
            click.echo(click.style("❌ Adder service is not healthy", fg="red"))
            sys.exit(1)
    except Exception as e:
        click.echo(click.style(f"❌ Error checking service health: {e}", fg="red"))
        sys.exit(1)


@cli.command()
@click.option('--url', '-u', required=False, help='Base URL of the adder service API')
@click.option('--a', '-a', required=True, type=float, help='First number to add')
@click.option('--b', '-b', required=True, type=float, help='Second number to add')
@click.option('--local', '-l', is_flag=True, help='Use local adder library instead of API')
def add(url, a, b, local):
    """Add two numbers using either the adder service API or the local adder library."""
    if local:
        # Use the adder library directly
        try:
            result = adder_lib_add(a, b)
            click.echo(click.style(f"Result (local): {result}", fg="green"))
        except AdderException as e:
            click.echo(click.style(f"❌ {e}", fg="red"))
            sys.exit(1)
        except Exception as e:
            click.echo(click.style(f"❌ Unexpected error: {e}", fg="red"))
            sys.exit(1)
    else:
        # Use the API
        if not url:
            click.echo(click.style("❌ URL is required when not using local mode", fg="red"))
            sys.exit(1)
            
        client = AdderServiceClient(url)
        try:
            # First check if the service is healthy
            if not client.check_health():
                click.echo(click.style("❌ Adder service is not healthy", fg="red"))
                sys.exit(1)
                
            # Make the request to add numbers
            result = client.add(a, b)
            click.echo(click.style(f"Result (API): {result}", fg="green"))
        except ValueError as e:
            click.echo(click.style(f"❌ {e}", fg="red"))
            sys.exit(1)
        except ConnectionError as e:
            click.echo(click.style(f"❌ {e}", fg="red"))
            sys.exit(1)
        except Exception as e:
            click.echo(click.style(f"❌ Unexpected error: {e}", fg="red"))
            sys.exit(1)


if __name__ == '__main__':
    cli()