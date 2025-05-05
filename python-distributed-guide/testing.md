# Testing

## Do:

✅ **Write unit tests for all components**

```python
import unittest
from unittest.mock import patch

class ServiceTest(unittest.TestCase):
    def test_process_data(self):
        # Test with valid input
        result = process_data({"id": 1, "value": "test"})
        self.assertEqual(result["processed_value"], "TEST")
        
        # Test with invalid input
        with self.assertRaises(ValueError):
            process_data({"id": 1, "value": None})
```

✅ **Mock external dependencies in tests**

```python
@patch('requests.post')
def test_call_external_service(mock_post):
    # Configure the mock
    mock_response = Mock()
    mock_response.json.return_value = {'result': 'success'}
    mock_response.status_code = 200
    mock_post.return_value = mock_response
    
    # Test the function
    result = call_external_service({'data': 'test'})
    
    # Assert the expected behavior
    mock_post.assert_called_once_with(
        'http://external-service/api',
        json={'data': 'test'},
        timeout=5
    )
    self.assertEqual(result, {'result': 'success'})
```

✅ **Mock remote microservices effectively**

Mocking remote microservices is crucial in distributed systems testing for several reasons:

1. **Deterministic tests**: Remote services may return different results based on their state, making tests unpredictable.
2. **Test isolation**: Tests shouldn't fail because an unrelated service is down or unreachable.
3. **Speed**: Network calls are slow and introduce latency in your test suite.
4. **Boundary control**: Mocking allows testing edge cases and error conditions that might be difficult to reproduce with real services.
5. **Avoiding resource consumption**: Tests shouldn't create real data or consume production resources.

```python
from unittest.mock import patch, MagicMock

class OrderServiceTest(unittest.TestCase):
    @patch('services.inventory_client.InventoryClient')
    @patch('services.payment_client.PaymentClient')
    def test_place_order(self, mock_payment_client, mock_inventory_client):
        # Set up mocks for remote services
        inventory_instance = MagicMock()
        inventory_instance.check_availability.return_value = True
        mock_inventory_client.return_value = inventory_instance
        
        payment_instance = MagicMock()
        payment_instance.process_payment.return_value = {
            'transaction_id': '12345',
            'status': 'completed'
        }
        mock_payment_client.return_value = payment_instance
        
        # Execute the function under test
        order_service = OrderService()
        result = order_service.place_order({
            'customer_id': 'cust-123',
            'items': [{'product_id': 'prod-456', 'quantity': 1}],
            'payment': {'method': 'credit_card', 'card_token': 'tok_visa'}
        })
        
        # Verify interactions with remote services
        inventory_instance.check_availability.assert_called_once()
        payment_instance.process_payment.assert_called_once()
        
        # Verify the result
        self.assertEqual(result['status'], 'success')
        
        # Test failure scenarios by changing mock behavior
        inventory_instance.check_availability.return_value = False
        with self.assertRaises(OutOfStockError):
            order_service.place_order({
                'customer_id': 'cust-123',
                'items': [{'product_id': 'prod-456', 'quantity': 1}],
                'payment': {'method': 'credit_card', 'card_token': 'tok_visa'}
            })
```

Using `MagicMock` provides several advantages over standard `Mock`:

- **Auto-creation of attributes**: Any attribute accessed on a `MagicMock` instantly creates a new mock.
- **Return value chaining**: Allows for easy configuration of complex return values and chained methods.
- **Spec-based mocking**: Can restrict available attributes to match the actual object being mocked.
- **Built-in assertions**: Methods like `assert_called_with()` make verification more concise.

✅ **Implement integration tests**

```python
def test_end_to_end_flow():
    # Start all required services
    with start_test_services():
        # Create test data
        test_id = create_test_record({"name": "Test Item"})
        
        # Perform the operation being tested
        result = client.post(
            "/api/process", 
            json={"id": test_id}
        )
        
        # Verify the result
        self.assertEqual(result.status_code, 200)
        
        # Verify the side effects
        processed_record = get_record(test_id)
        self.assertEqual(processed_record["status"], "processed")
```

## Don't:

❌ **Don't rely solely on manual testing**

```python
# Bad: Manual verification without automated tests
def process_order(order):
    # Complex business logic without tests
    if order.status == "pending" and order.payment_verified:
        # Update inventory
        for item in order.items:
            update_inventory(item)
        
        # Update order status
        order.status = "processing"
        order.save()
        
        # Notify customer
        send_notification(order.customer_email, "Order Processing")
```

❌ **Don't make tests dependent on external services**

```python
# Bad: Test that depends on external API
def test_process_payment():
    # This test will fail if the payment gateway is down
    result = process_payment({
        "card_number": "4111111111111111",
        "exp_date": "12/25",
        "cvv": "123",
        "amount": 100.00
    })
    
    self.assertEqual(result["status"], "success")
```

❌ **Don't ignore flaky tests**

```python
# Bad: Ignoring test failures
@unittest.skip("This test is flaky, fix later")
def test_concurrent_updates():
    # Test concurrent updates to shared resource
    pass
```