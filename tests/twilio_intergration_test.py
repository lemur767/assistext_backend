# tests/test_twilio_integration.py
import pytest
from app import create_app
from app.extensions import db
from app.models.user import User
from app.models.profile import Profile
from app.services.twilio_service import TwilioService
from unittest.mock import patch, MagicMock

@pytest.fixture
def app():
    app = create_app('testing')
    
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def auth_headers():
    # Mock JWT token for testing
    return {'Authorization': 'Bearer test-token'}

@pytest.fixture
def mock_jwt_required():
    with patch('flask_jwt_extended.jwt_required') as mock:
        mock.return_value = lambda f: f
        yield mock

@pytest.fixture
def mock_get_jwt_identity():
    with patch('flask_jwt_extended.get_jwt_identity') as mock:
        mock.return_value = 1  # User ID 1
        yield mock

@pytest.fixture
def user():
    user = User(
        username='testuser',
        email='test@example.com',
        id=1
    )
    user.set_password('password')
    db.session.add(user)
    db.session.commit()
    return user

def test_create_subaccount(app, client, auth_headers, mock_jwt_required, mock_get_jwt_identity, user):
    # Mock Twilio API calls
    with patch('app.services.twilio_service.Client') as mock_client:
        # Mock account creation
        mock_account = MagicMock()
        mock_account.sid = 'AC123'
        mock_account.auth_token = 'auth123'
        mock_client.return_value.api.accounts.create.return_value = mock_account
        
        # Mock API key creation
        mock_api_key = MagicMock()
        mock_api_key.sid = 'SK123'
        mock_api_key.secret = 'secret123'
        mock_client.return_value.new_keys.create.return_value = mock_api_key
        
        # Test API endpoint
        response = client.post(
            '/api/twilio/account/subaccount', 
            headers=auth_headers
        )
        
        assert response.status_code == 201
        data = response.get_json()
        assert data['account_sid'] == 'AC123'
        assert data['api_key_sid'] == 'SK123'
        
        # Verify database was updated
        with app.app_context():
            updated_user = User.query.get(1)
            assert updated_user.twilio_account_sid == 'AC123'
            assert updated_user.twilio_account_type == 'subaccount'
            assert updated_user.twilio_parent_account == True

def test_connect_external_account(app, client, auth_headers, mock_jwt_required, mock_get_jwt_identity, user):
    # Mock Twilio API calls
    with patch('app.services.twilio_service.Client') as mock_client:
        # Mock account verification
        mock_account = MagicMock()
        mock_account.friendly_name = 'Test Account'
        mock_client.return_value.api.accounts.return_value.fetch.return_value = mock_account
        
        # Mock API key creation
        mock_api_key = MagicMock()
        mock_api_key.sid = 'SK123'
        mock_api_key.secret = 'secret123'
        mock_client.return_value.new_keys.create.return_value = mock_api_key
        
        # Test API endpoint
        response = client.post(
            '/api/twilio/account/external', 
            json={
                'account_sid': 'AC123',
                'auth_token': 'auth123'
            },
            headers=auth_headers
        )
        
        assert response.status_code == 201
        data = response.get_json()
        assert data['account_sid'] == 'AC123'
        assert data['api_key_sid'] == 'SK123'
        
        # Verify database was updated
        with app.app_context():
            updated_user = User.query.get(1)
            assert updated_user.twilio_account_sid == 'AC123'
            assert updated_user.twilio_account_type == 'external'
            assert updated_user.twilio_parent_account == False

def test_webhook_signature_validation(app, client):
    # Setup test data
    with app.app_context():
        # Create user with Twilio account
        user = User(
            username='webhookuser',
            email='webhook@example.com'
        )
        user.set_password('password')
        user.twilio_account_sid = 'AC123'
        user.twilio_account_type = 'subaccount'
        user.twilio_parent_account = True
        db.session.add(user)
        
        # Create profile
        profile = Profile(
            user_id=user.id,
            name='Test Profile',
            phone_number='+14155552671'
        )
        db.session.add(profile)
        db.session.commit()
    
    # Mock validation function
    with patch('app.utils.twilio_helpers.validate_twilio_signature') as mock_validate:
        # Test with valid signature
        mock_validate.return_value = True
        
        response = client.post(
            '/api/webhooks/sms',
            data={
                'Body': 'Test message',
                'From': '+14155551234',
                'To': '+14155552671',
                'AccountSid': 'AC123'
            }
        )
        
        assert response.status_code == 204
        
        # Test with invalid signature
        mock_validate.return_value = False
        
        response = client.post(
            '/api/webhooks/sms',
            data={
                'Body': 'Test message',
                'From': '+14155551234',
                'To': '+14155552671',
                'AccountSid': 'AC123'
            }
        )
        
        assert response.status_code == 403