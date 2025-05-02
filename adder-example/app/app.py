#!/usr/bin/env python3
"""
Main entry point for the adder service application.
This file is used to start the Flask application in containerized environments.
"""

import os
from api.adder_service import app

if __name__ == "__main__":
    # Get port from environment variable or use default
    port = int(os.environ.get("PORT", 5000))
    
    # Run the app - in production use gunicorn or similar
    app.run(host="0.0.0.0", port=port)