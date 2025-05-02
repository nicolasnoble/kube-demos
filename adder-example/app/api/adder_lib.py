#!/usr/bin/env python3
"""
Adder Library

A reusable library that provides adder functionality which can be used in
various contexts, not just within Flask services.
"""

class AdderException(Exception):
    """Exception raised for errors in the adder operations."""
    pass

def validate_numbers(a, b):
    """
    Validate that inputs are valid numbers.
    
    Args:
        a: First input to validate
        b: Second input to validate
        
    Returns:
        tuple: A tuple of (float(a), float(b))
        
    Raises:
        AdderException: If inputs are not valid numbers
    """
    try:
        return float(a), float(b)
    except (ValueError, TypeError):
        raise AdderException("Inputs must be valid numbers")

def add(a, b):
    """
    Add two numbers together.
    
    Args:
        a: First number to add
        b: Second number to add
        
    Returns:
        float: The result of adding a and b
        
    Raises:
        AdderException: If inputs are not valid numbers
    """
    a_float, b_float = validate_numbers(a, b)
    return a_float + b_float