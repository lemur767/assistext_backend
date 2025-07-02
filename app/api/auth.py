from flask import request, jsonify, current_app
from flask_restful import Resource
from flask_jwt_extended import create_access_token, create_refresh_token
from app import db
from app.models.user import User
from app.models.profile import Profile
from marshmallow import Schema, fields, validate, ValidationError
import logging
import uuid
from signalwire.rest import Client as SignalWireClient


logger = logging.getLogger(__name__)

class UserRegistrationSchema(Schema):
    """Schema for user registration validation"""
    username = fields.Str(required=True, validate=validate.Length(min=3, max=80))
    email = fields.Email(required=True)
    password = fields.Str(required=True, validate=validate.Length(min=8))
    confirm_password = fields.Str(required=True)
    first_name = fields.Str(required=True, validate=validate.Length(min=1, max=50))
    last_name = fields.Str(required=True, validate=validate.Length(min=1, max=50))
    personal_phone = fields.Str(allow_none=True, validate=validate.Length(max=20))

class RegistrationAPI(Resource):
    """Handle user registration endpoint"""
    
    def post(self):
        try:
            schema = UserRegistrationSchema()
            data = schema.load(request.json)
            
            # Validate passwords match
            if data['password'] != data['confirm_password']:
                return {'error': 'Passwords do not match'}, 400
            
            # Check if user exists
            existing_user = User.query.filter(
                (User.username == data['username']) | 
                (User.email == data['email'])
            ).first()
            
            if existing_user:
                return {'error': 'User already exists'}, 409
            
            # Create user
            user = User(
                username=data['username'],
                email=data['email'],
                first_name=data['first_name'],
                last_name=data['last_name'],
                personal_phone=data.get('personal_phone')
            )
            user.set_password(data['password'])
            
            db.session.add(user)
            db.session.commit()
            
            # Generate tokens
            access_token = create_access_token(identity=user.id)
            refresh_token = create_refresh_token(identity=user.id)
            
            return {
                'success': True,
                'message': 'User registered successfully',
                'user': user.to_dict(),
                'access_token': access_token,
                'refresh_token': refresh_token
            }, 201
            
        except ValidationError as e:
            return {'error': 'Validation failed', 'details': e.messages}, 400
        except Exception as e:
            db.session.rollback()
            logger.error(f"Registration error: {str(e)}")
            return {'error': 'Registration failed'}, 500

class PhoneNumberSearchAPI(Resource):
      
   def search_phone_numbers(self, city: str, country: str = 'CA', limit: int = 10):
   
    
    if not city:
        return {
            'success': False,
            'error': 'City parameter is required',
            'available_numbers': []
        }, 400
    
    try:
        client = self._get_signalwire_client()
        if not client:
            return {
                'success': False,
                'error': 'SignalWire service unavailable. Please try again later or contact support.',
                'available_numbers': []
            }, 503
        
        city = city.lower().strip()
        
        if country.upper() == 'CA':
            # Map cities to area codes for Canadian numbers
            city_area_codes = {
                'toronto': ['416', '647', '437'],
                'ottawa': ['613', '343'], 
                'vancouver': ['604', '778', '236'],
                'montreal': ['514', '438'],
                'calgary': ['403', '587', '825'],
                'edmonton': ['780', '587', '825'],
                'mississauga': ['905', '289', '365'],
                'hamilton': ['905', '289'],
                'london': ['519', '226', '548'],
                'winnipeg': ['204', '431'],
                'quebec_city': ['418', '581'],
                'halifax': ['902', '782'],
                'saskatoon': ['306', '639'],
                'regina': ['306', '639']
            }
            area_codes_to_search = city_area_codes.get(city, ['416'])  # Default to Toronto
        
        all_available_numbers = []
        
       
        province = self._get_province_for_city(city)
        
      
        for code in area_codes_to_search:
            try:
                logger.info(f"Searching area code {code} in country {country} with region {province}")
                
                
                search_params = {
                    'area_code': code,
                    'sms_enabled': True,
                    'limit': limit
                }
                
             
                if country.upper() == 'CA':
                    search_params['in_region'] = province
                    search_params['in_locality'] = city.title()
                
                
                available_numbers = client.available_phone_numbers(country).local.list(**search_params)
                
                # Format the response
                for number in available_numbers:
                    formatted_number = self._format_phone_number(number.phone_number)
                    
                    number_data = {
                        'phone_number': number.phone_number,
                        'formatted_number': formatted_number,
                        'locality': getattr(number, 'locality', city.title()),
                        'region': getattr(number, 'region', province),
                        'area_code': code,
                        'capabilities': {
                            'sms': getattr(number, 'sms_enabled', True),
                            'mms': getattr(number, 'mms_enabled', True), 
                            'voice': getattr(number, 'voice_enabled', True)
                        },
                        'setup_cost': '$1.00',
                        'monthly_cost': '$1.00',
                        'country': country,
                        'is_toll_free': number.phone_number.startswith('+1800') or number.phone_number.startswith('+1888'),
                        'friendly_name': f"{formatted_number} - {getattr(number, 'locality', city.title())}"
                    }
                    
                    all_available_numbers.append(number_data)
                    
                    # Stop if we have enough numbers
                    if len(all_available_numbers) >= limit:
                        break
                
            except Exception as area_error:
                logger.warning(f"Failed to search area code {code}: {str(area_error)}")
                continue
            
            # Break if we have enough numbers
            if len(all_available_numbers) >= limit:
                break
        
        if not all_available_numbers:
            logger.warning(f"No available numbers found for city={city}, area_codes={area_codes_to_search}")
            return {
                'success': True,
                'city': city.title(),
                'available_numbers': [],
                'count': 0,
                'message': f'No available numbers found for {city.title()}. Please try a different city or contact support.'
            }, 200
        
        logger.info(f"Found {len(all_available_numbers)} available numbers for {city}")
        
        return {
            'success': True,
            'city': city.title(),
            'available_numbers': all_available_numbers,
            'count': len(all_available_numbers),
            'searched_area_codes': area_codes_to_search
        }, 200
        
    except Exception as e:
        logger.error(f"SignalWire phone search error: {str(e)}")
        return {
            'error': 'Phone number search failed',
            'details': str(e),
            'success': False
        }, 500


# Additional endpoint for number validation
class PhoneNumberValidationAPI(Resource):
    
    def post(self):
        try:
            data = request.json
            phone_number = data.get('phone_number')
            
            if not phone_number:
                return {'error': 'Phone number is required'}, 400
            
            client = get_signalwire_client()
            if not client:
                return {'error': 'SignalWire service unavailable'}, 503
            
            # Check if number is still available
            try:
                # Try to find this specific number
                country = 'CA' if phone_number.startswith('+1') else 'US'
                available_numbers = client.available_phone_numbers(country).list(
                    phone_number=phone_number,
                    limit=1
                )
                
                if available_numbers:
                    number = available_numbers[0]
                    return {
                        'is_available': True,
                        'phone_number': number.phone_number,
                        'formatted_number': self._format_phone_number(number.phone_number),
                        'locality': getattr(number, 'locality', 'Unknown'),
                        'region': getattr(number, 'region', 'Unknown'),
                        'capabilities': {
                            'sms': getattr(number, 'sms_enabled', True),
                            'mms': getattr(number, 'mms_enabled', True),
                            'voice': getattr(number, 'voice_enabled', True)
                        }
                    }, 200
                else:
                    return {
                        'is_available': False,
                        'message': 'Number is no longer available'
                    }, 200
                    
            except Exception as e:
                logger.error(f"Error validating number {phone_number}: {str(e)}")
                return {
                    'is_available': False,
                    'error': 'Failed to validate number',
                    'details': str(e)
                }, 500
                
        except Exception as e:
            logger.error(f"Phone validation error: {str(e)}")
            return {'error': 'Phone number validation failed'}, 500
    
    def _format_phone_number(self, phone_number: str) -> str:
        """Format phone number for display"""
        if phone_number.startswith('+1'):
            phone_number = phone_number[2:]
        elif phone_number.startswith('1'):
            phone_number = phone_number[1:]
        
        if len(phone_number) == 10:
            return f"({phone_number[:3]}) {phone_number[3:6]}-{phone_number[6:]}"
        
        return phone_number

class CompleteSignupAPI(Resource):
    """Handle complete signup with profile creation"""
    
    def post(self):
        try:
            data = request.json
            
            # Create user
            user = User(
                username=data['username'],
                email=data['email'],
                first_name=data['firstName'],
                last_name=data['lastName'],
                personal_phone=data.get('personalPhone'),
                timezone=data.get('timezone', 'America/Toronto')
            )
            user.set_password(data['password'])
            
            db.session.add(user)
            db.session.flush()
            
            # Create profile
            profile = Profile(
                user_id=user.id,
                name=data['profileName'],
                description=data.get('profileDescription'),
                phone_number=data['selectedPhoneNumber'],
                preferred_city=data.get('preferredCity', 'toronto')
            )
            
            db.session.add(profile)
            db.session.commit()
            
            # Generate tokens
            access_token = create_access_token(identity=user.id)
            refresh_token = create_refresh_token(identity=user.id)
            
            return {
                'success': True,
                'message': 'Account created successfully',
                'user': user.to_dict(),
                'profile': profile.to_dict(),
                'access_token': access_token,
                'refresh_token': refresh_token
            }, 201
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Complete signup error: {str(e)}")
            return {'error': 'Registration failed'}, 500

def register_auth_routes(api, limiter):
    """Register authentication routes with rate limiting"""
    
    # Apply rate limiting
    RegistrationAPI.decorators = [limiter.limit("5 per minute")]
    PhoneNumberSearchAPI.decorators = [limiter.limit("10 per minute")]
    CompleteSignupAPI.decorators = [limiter.limit("3 per minute")]
    
    # Register routes
    api.add_resource(RegistrationAPI, '/api/auth/register')
    api.add_resource(PhoneNumberSearchAPI, '/api/signup/search-numbers')
    api.add_resource(CompleteSignupAPI, '/api/signup/complete-signup')
