#!/usr/bin/env python3
"""
Unit tests for the adder service API.
"""

import json
import unittest
from app.api.adder_service import app

class TestAdderService(unittest.TestCase):
    """Test cases for the adder service API."""
    
    def setUp(self):
        """Set up test client."""
        self.app = app.test_client()
        self.app.testing = True
    
    def test_health_endpoint(self):
        """Test health check endpoint."""
        response = self.app.get('/health')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'healthy')
    
    def test_add_valid_numbers(self):
        """Test adding two valid numbers."""
        payload = {'a': 5, 'b': 7}
        response = self.app.post('/add', 
                                json=payload,
                                content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['result'], 12)
    
    def test_add_negative_numbers(self):
        """Test adding negative numbers."""
        payload = {'a': -5, 'b': 3}
        response = self.app.post('/add', 
                                json=payload,
                                content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['result'], -2)
    
    def test_add_float_numbers(self):
        """Test adding floating point numbers."""
        payload = {'a': 2.5, 'b': 3.5}
        response = self.app.post('/add', 
                                json=payload,
                                content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['result'], 6.0)
    
    def test_missing_parameter(self):
        """Test error handling when a parameter is missing."""
        payload = {'a': 5}  # Missing 'b'
        response = self.app.post('/add', 
                                json=payload,
                                content_type='application/json')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)
    
    def test_invalid_parameter_type(self):
        """Test error handling when parameters are not valid numbers."""
        payload = {'a': 'string', 'b': 7}
        response = self.app.post('/add', 
                                json=payload,
                                content_type='application/json')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)
    
    def test_empty_request(self):
        """Test error handling when no data is provided."""
        response = self.app.post('/add', 
                                data='',
                                content_type='application/json')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)

if __name__ == '__main__':
    unittest.main()