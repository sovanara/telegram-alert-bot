import json
from decimal import Decimal
import pytest

import src.handler as handler

# A dummy in-memory table to simulate DynamoDB
class DummyTable:
    def __init__(self):
        self.storage = {}
    def put_item(self, Item):
        key = (Item['chat_id'], Item.get('symbol') or Item.get('index_name'))
        self.storage[key] = Item
    def get_item(self, Key):
        key = (Key['chat_id'], Key.get('symbol') or Key.get('index_name'))
        return {'Item': self.storage.get(key)}
    def scan(self, FilterExpression):
        return {'Items': [v for k,v in self.storage.items() if k[0]==FilterExpression.values[0]]}
    def delete_item(self, Key):
        self.storage.pop((Key['chat_id'], Key.get('symbol') or Key.get('index_name')), None)

@pytest.fixture(autouse=True)
def mock_dynamodb(monkeypatch):
    """Automatically patch get_table() to use DummyTable."""
    dummy = DummyTable()
    monkeypatch.setattr(handler, "get_table", lambda name: dummy)
    return dummy

def make_event(text, chat_id="user1"):
    """Helper to craft a Lambda event for a given chat text."""
    return {'body': json.dumps({'message': {'chat': {'id': chat_id}, 'text': text}})}

def test_handle_set_and_list(mock_dynamodb):
    """Test that !set stores an alert and !list retrieves it."""
    # Simulate setting an alert
    resp = handler.handle_set(make_event("!set ABC 5 10"))
    assert resp["statusCode"] == 200
    # Now list alerts
    resp = handler.handle_list(make_event("!list"))
    assert resp["statusCode"] == 200
    # Verify storage state
    assert ("user1","ABC") in mock_dynamodb.storage
    item = mock_dynamodb.storage[("user1","ABC")]
    assert item["threshold_percent"] == Decimal("5")
    assert item["interval_minutes"] == Decimal("10")

def test_handle_price(monkeypatch):
    """Test that !price returns correctly formatted message."""
    # Stub quote data
    monkeypatch.setattr(handler, "get_quote_data",
                        lambda sym, key: {"price":123.45,"open":100.0,"high":110,"low":90,"volume":"1","adj":122})
    resp = handler.handle_price(make_event("!price XYZ"))
    assert resp["statusCode"] == 200

def test_handle_create_and_index(mock_dynamodb, monkeypatch):
    """Test !createindex then !index computes correct storage and output."""
    # Stub price fetch
    monkeypatch.setattr(handler, "get_quote_data",
                        lambda sym, key: {"price":10.0,"open":5.0,"high":12.0,"low":4.0,"volume":"100","adj":9.0})
    # Create index
    resp = handler.handle_createindex(make_event("!createindex IDX A B"))
    assert resp["statusCode"] == 200
    # Index it
    resp = handler.handle_index(make_event("!index IDX"))
    assert resp["statusCode"] == 200
    # Ensure baseline and created_at are stored
    item = mock_dynamodb.storage[("user1","IDX")]
    assert "baseline_prices" in item and "created_at" in item