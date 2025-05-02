#!/usr/bin/env python3
"""
Adder Service API

A simple Flask API that exposes an endpoint to add two numbers together.
This is designed to be deployed as a Kubernetes service.
"""

from flask import Flask, request, jsonify
import logging
import sys
import os

# Import the adder_lib package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from adder_lib import add, AdderException

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Flask application
app = Flask(__name__)

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for Kubernetes liveness and readiness probes."""
    return jsonify({'status': 'healthy'}), 200

@app.route('/add', methods=['POST'])
def add_numbers():
    """
    Add two numbers together.
    
    Expected JSON payload:
    {
        "a": number,
        "b": number
    }
    
    Returns:
    {
        "result": number,
        "error": string (optional)
    }
    """
    try:
        # Get JSON data from request
        data = request.get_json(silent=True)  # silent=True prevents BadRequest exception on empty body
        
        # Validate input
        if not data:
            return jsonify({'error': 'No input provided'}), 400
            
        if 'a' not in data or 'b' not in data:
            return jsonify({'error': 'Both "a" and "b" parameters are required'}), 400
            
        # Use the adder_lib to perform the calculation
        try:
            result = add(data['a'], data['b'])
            
            # Log the operation
            logger.info(f"Addition performed: {data['a']} + {data['b']} = {result}")
            
            # Return result
            return jsonify({'result': result}), 200
            
        except AdderException as ae:
            return jsonify({'error': str(ae)}), 400
        
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        return jsonify({'error': f'Server error: {str(e)}'}), 500

if __name__ == '__main__':
    # For local development only
    app.run(host='0.0.0.0', port=5000, debug=True)