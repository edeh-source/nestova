import requests
import logging
from django.conf import settings
from .models import VerificationLog
from fuzzywuzzy import fuzz
from datetime import datetime
import time

logger = logging.getLogger(__name__)

class VerificationService:
    """
    Handles interactions with Persona API for identity verification in Nigeria.
    Supports NIN, BVN, and CAC verification with confidence scoring and auto-approval capabilities.
    """

    def __init__(self, provider='persona'):
        self.provider = provider
        # Get API key from settings
        self.api_key = getattr(settings, 'PERSONA_API_KEY', None)
        self.template_id = getattr(settings, 'PERSONA_TEMPLATE_ID', '')
        self.base_url = "https://withpersona.com/api/v1"
        
        # Confidence thresholds
        self.auto_verify_threshold = getattr(settings, 'AUTO_VERIFY_CONFIDENCE_THRESHOLD', 85)
        self.manual_review_threshold = getattr(settings, 'REQUIRE_MANUAL_REVIEW_BELOW', 70)
        self.auto_reject_threshold = getattr(settings, 'AUTO_REJECT_BELOW', 50)

    def _get_headers(self):
        """Get authorization headers for Persona API"""
        if not self.api_key:
            raise ValueError("Persona API key not configured")
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Persona-Version": "2023-01-05"
        }

    def _log_attempt(self, user, v_type, request_data, response_data, status, is_match=False, error=None):
        """Internal helper to log verification attempts"""
        return VerificationLog.objects.create(
            user=user,
            verification_type=v_type,
            api_provider=self.provider,
            request_data=request_data,
            response_data=response_data,
            status=status,
            is_match=is_match,
            error_message=error
        )

    def _create_database_verification(self, verification_type, id_number, country_code='ng', additional_data=None):
        """
        Create a database verification via Persona API
        
        Args:
            verification_type: Type of verification (e.g., 'nin', 'bvn', 'cac')
            id_number: The ID number to verify
            country_code: Country code (default: 'ng' for Nigeria)
            additional_data: Additional data for verification (e.g., name, dob)
        
        Returns:
            tuple: (success: bool, response_data: dict)
        """
        if not self.api_key:
            logger.error("Persona API key not configured.")
            return False, {"error": "Verification system is temporarily unavailable."}

        endpoint = f"{self.base_url}/verifications/database"
        
        # Build request payload in JSON:API format
        payload = {
            "data": {
                "type": "verification/database",
                "attributes": {
                    "country-code": country_code,
                    "id-number": id_number,
                    "id-class": self._map_verification_type(verification_type)
                }
            }
        }
        
        # Add additional data if provided
        if additional_data:
            payload["data"]["attributes"].update(additional_data)

        try:
            headers = self._get_headers()
            response = requests.post(endpoint, json=payload, headers=headers, timeout=30)
            data = response.json()
            
            if response.status_code in [200, 201]:
                # Successful verification
                return True, data
            else:
                # Error response
                error_msg = self._extract_error_message(data)
                logger.error(f"Persona verification failed: {error_msg}")
                return False, {"error": error_msg, "raw_response": data}
                
        except requests.exceptions.Timeout:
            error_msg = "Verification request timed out"
            logger.exception(error_msg)
            return False, {"error": error_msg}
        except requests.exceptions.RequestException as e:
            error_msg = f"Network error during verification: {str(e)}"
            logger.exception(error_msg)
            return False, {"error": error_msg}
        except Exception as e:
            error_msg = f"Unexpected error during verification: {str(e)}"
            logger.exception(error_msg)
            return False, {"error": error_msg}

    def _map_verification_type(self, v_type):
        """Map our verification types to Persona's id-class values"""
        mapping = {
            'nin': 'ng_nin',  # Nigerian National Identity Number
            'bvn': 'ng_bvn',  # Nigerian Bank Verification Number
            'cac': 'ng_cac',  # Nigerian Corporate Affairs Commission
        }
        return mapping.get(v_type.lower(), v_type)

    def _extract_error_message(self, response_data):
        """Extract error message from Persona API response"""
        if isinstance(response_data, dict):
            # Check for JSON:API error format
            if 'errors' in response_data and isinstance(response_data['errors'], list):
                if len(response_data['errors']) > 0:
                    error = response_data['errors'][0]
                    return error.get('title', error.get('detail', 'Verification failed'))
            # Check for simple error format
            if 'error' in response_data:
                return response_data['error']
            if 'message' in response_data:
                return response_data['message']
        return 'Verification failed'

    def _extract_verification_data(self, response_data):
        """
        Extract verification data from Persona API response
        
        Returns:
            dict: Normalized verification data
        """
        try:
            if 'data' in response_data:
                data = response_data['data']
                attributes = data.get('attributes', {})
                
                # Extract relevant fields
                extracted = {
                    'status': attributes.get('status'),
                    'first_name': attributes.get('name-first') or attributes.get('first-name'),
                    'last_name': attributes.get('name-last') or attributes.get('last-name'),
                    'middle_name': attributes.get('name-middle') or attributes.get('middle-name'),
                    'date_of_birth': attributes.get('birthdate') or attributes.get('date-of-birth'),
                    'phone': attributes.get('phone-number'),
                    'email': attributes.get('email-address'),
                    'address': attributes.get('address-street-1'),
                    'verification_id': data.get('id'),
                    'checks': attributes.get('checks', {}),
                    'raw_attributes': attributes  # Keep raw data for debugging
                }
                
                return extracted
            return {}
        except Exception as e:
            logger.exception(f"Error extracting verification data: {e}")
            return {}

    def verify_bvn(self, user, bvn):
        """Verify BVN (Bank Verification Number)"""
        params = {"bvn": bvn}
        
        try:
            success, result = self._create_database_verification('bvn', bvn)
            
            if success:
                # Extract and normalize data
                extracted_data = self._extract_verification_data(result)
                
                # Check verification status
                status = extracted_data.get('status', '').lower()
                is_match = status in ['passed', 'verified', 'success']
                
                self._log_attempt(user, 'bvn', params, result, 'success' if is_match else 'failed', is_match=is_match)
                
                return True, extracted_data
            else:
                error_msg = result.get('error', 'Verification failed')
                self._log_attempt(user, 'bvn', params, result, 'failed', error=error_msg)
                return False, error_msg

        except Exception as e:
            logger.exception("Error during BVN verification")
            self._log_attempt(user, 'bvn', params, {}, 'failed', error=str(e))
            return False, str(e)

    def verify_nin(self, user, nin):
        """Verify NIN (National Identity Number)"""
        params = {"nin": nin}
        
        try:
            success, result = self._create_database_verification('nin', nin)
            
            if success:
                # Extract and normalize data
                extracted_data = self._extract_verification_data(result)
                
                # Check verification status
                status = extracted_data.get('status', '').lower()
                is_match = status in ['passed', 'verified', 'success']
                
                self._log_attempt(user, 'nin', params, result, 'success' if is_match else 'failed', is_match=is_match)
                
                return True, extracted_data
            else:
                error_msg = result.get('error', 'Verification failed')
                self._log_attempt(user, 'nin', params, result, 'failed', error=error_msg)
                return False, error_msg

        except Exception as e:
            logger.exception("Error during NIN verification")
            self._log_attempt(user, 'nin', params, {}, 'failed', error=str(e))
            return False, str(e)

    def verify_cac(self, user, rc_number, company_name=None):
        """Verify CAC (Corporate Affairs Commission) Registration"""
        params = {"rc_number": rc_number}
        if company_name:
            params['company_name'] = company_name
        
        try:
            # Add company name to additional data if provided
            additional_data = {}
            if company_name:
                additional_data['company-name'] = company_name
            
            success, result = self._create_database_verification('cac', rc_number, additional_data=additional_data)
            
            if success:
                # Extract and normalize data
                extracted_data = self._extract_verification_data(result)
                
                # Check verification status
                status = extracted_data.get('status', '').lower()
                is_match = status in ['passed', 'verified', 'success']
                
                # Add company name from response if available
                if 'company_name' not in extracted_data:
                    extracted_data['company_name'] = extracted_data.get('raw_attributes', {}).get('company-name')
                
                self._log_attempt(user, 'cac', params, result, 'success' if is_match else 'failed', is_match=is_match)
                
                return True, extracted_data
            else:
                error_msg = result.get('error', 'Verification failed')
                self._log_attempt(user, 'cac', params, result, 'failed', error=error_msg)
                return False, error_msg

        except Exception as e:
            logger.exception("Error during CAC verification")
            self._log_attempt(user, 'cac', params, {}, 'failed', error=str(e))
            return False, str(e)

    def calculate_confidence_score(self, api_data, user, user_profile=None):
        """
        Calculate confidence score based on data matching between API response and user data.
        Returns: Dictionary with overall score (0-100) and breakdown
        """
        scores = []
        breakdown = {}
        
        # Name matching (First Name)
        if 'first_name' in api_data or 'firstname' in api_data:
            api_first_name = api_data.get('first_name') or api_data.get('firstname', '')
            user_first_name = user.first_name or ''
            
            if api_first_name and user_first_name:
                name_score = self._fuzzy_match_name(api_first_name, user_first_name)
                scores.append(name_score)
                breakdown['first_name_match'] = name_score
        
        # Name matching (Last Name)
        if 'last_name' in api_data or 'lastname' in api_data or 'surname' in api_data:
            api_last_name = api_data.get('last_name') or api_data.get('lastname') or api_data.get('surname', '')
            user_last_name = user.last_name or ''
            
            if api_last_name and user_last_name:
                surname_score = self._fuzzy_match_name(api_last_name, user_last_name)
                scores.append(surname_score)
                breakdown['last_name_match'] = surname_score
        
        # Phone matching
        if 'phone' in api_data or 'phone_number' in api_data or 'mobile' in api_data:
            api_phone = str(api_data.get('phone') or api_data.get('phone_number') or api_data.get('mobile', '')).replace('+234', '0').replace(' ', '')
            
            # Try to get phone from user profile
            user_phone = ''
            if user_profile and hasattr(user_profile, 'phone'):
                user_phone = str(user_profile.phone).replace('+234', '0').replace(' ', '')
            elif hasattr(user, 'customer_profile'):
                try:
                    user_phone = str(user.customer_profile.phone).replace('+234', '0').replace(' ', '')
                except:
                    pass
            
            if api_phone and user_phone:
                # Exact match for phone numbers
                phone_score = 100 if api_phone[-10:] == user_phone[-10:] else 0
                scores.append(phone_score)
                breakdown['phone_match'] = phone_score
        
        # Date of birth matching
        if 'date_of_birth' in api_data or 'dob' in api_data or 'birthdate' in api_data:
            api_dob = api_data.get('date_of_birth') or api_data.get('dob') or api_data.get('birthdate')
            
            user_dob = None
            if user_profile and hasattr(user_profile, 'date_of_birth'):
                user_dob = user_profile.date_of_birth
            elif hasattr(user, 'customer_profile'):
                try:
                    user_dob = user.customer_profile.date_of_birth
                except:
                    pass
            
            if api_dob and user_dob:
                # Parse API DOB if it's a string
                if isinstance(api_dob, str):
                    try:
                        api_dob = datetime.strptime(api_dob, '%Y-%m-%d').date()
                    except:
                        try:
                            api_dob = datetime.strptime(api_dob, '%d-%m-%Y').date()
                        except:
                            api_dob = None
                
                if api_dob:
                    dob_score = 100 if api_dob == user_dob else 0
                    scores.append(dob_score)
                    breakdown['dob_match'] = dob_score
        
        # Email matching
        if 'email' in api_data:
            api_email = api_data.get('email', '').lower()
            user_email = user.email.lower()
            
            if api_email and user_email:
                email_score = 100 if api_email == user_email else 0
                scores.append(email_score)
                breakdown['email_match'] = email_score
        
        # Calculate overall confidence
        overall_confidence = sum(scores) / len(scores) if scores else 0
        
        return {
            'overall_confidence': round(overall_confidence, 2),
            'breakdown': breakdown,
            'checks_performed': len(scores),
            'recommendation': self._get_recommendation(overall_confidence)
        }
    
    def _fuzzy_match_name(self, name1, name2):
        """
        Fuzzy match two names using multiple algorithms.
        Returns: 0-100 score
        """
        if not name1 or not name2:
            return 0
        
        name1 = name1.lower().strip()
        name2 = name2.lower().strip()
        
        # Use multiple fuzzy matching algorithms and take the best score
        ratio_score = fuzz.ratio(name1, name2)
        partial_score = fuzz.partial_ratio(name1, name2)
        token_sort_score = fuzz.token_sort_ratio(name1, name2)
        
        # Return the highest score (most lenient)
        return max(ratio_score, partial_score, token_sort_score)
    
    def _get_recommendation(self, confidence):
        """Get verification recommendation based on confidence score"""
        if confidence >= self.auto_verify_threshold:
            return 'auto_approve'
        elif confidence >= self.manual_review_threshold:
            return 'manual_review'
        else:
            return 'auto_reject'
    
    def verify_phone(self, user, phone_number):
        """Verify phone number via API lookup"""
        params = {"phone_number": phone_number}
        
        try:
            # Persona may have phone verification - using database verification approach
            success, result = self._create_database_verification('phone', phone_number)
            
            if success:
                extracted_data = self._extract_verification_data(result)
                status = extracted_data.get('status', '').lower()
                is_match = status in ['passed', 'verified', 'success']
                
                self._log_attempt(user, 'phone', params, result, 'success' if is_match else 'failed', is_match=is_match)
                return True, extracted_data
            else:
                error_msg = result.get('error', 'Phone verification failed')
                self._log_attempt(user, 'phone', params, result, 'failed', error=error_msg)
                return False, error_msg
        
        except Exception as e:
            self._log_attempt(user, 'phone', params, {}, 'failed', error=str(e))
            return False, str(e)
    
    def verify_email(self, user, email):
        """Verify email address"""
        params = {"email": email}
        
        try:
            # Persona may have email verification - using database verification approach
            success, result = self._create_database_verification('email', email)
            
            if success:
                extracted_data = self._extract_verification_data(result)
                status = extracted_data.get('status', '').lower()
                is_match = status in ['passed', 'verified', 'success']
                
                self._log_attempt(user, 'email', params, result, 'success' if is_match else 'failed', is_match=is_match)
                return True, extracted_data
            else:
                error_msg = result.get('error', 'Email verification failed')
                self._log_attempt(user, 'email', params, result, 'failed', error=error_msg)
                return False, error_msg
        
        except Exception as e:
            self._log_attempt(user, 'email', params, {}, 'failed', error=str(e))
            return False, str(e)
    
    def verify_bank_account(self, user, account_number, bank_code):
        """Verify bank account details"""
        params = {
            "account_number": account_number,
            "bank_code": bank_code
        }
        
        try:
            # Create verification with additional bank data
            additional_data = {
                'bank-code': bank_code
            }
            
            success, result = self._create_database_verification('bank_account', account_number, additional_data=additional_data)
            
            if success:
                extracted_data = self._extract_verification_data(result)
                status = extracted_data.get('status', '').lower()
                is_match = status in ['passed', 'verified', 'success']
                
                self._log_attempt(user, 'bank_account', params, result, 'success' if is_match else 'failed', is_match=is_match)
                return True, extracted_data
            else:
                error_msg = result.get('error', 'Bank account verification failed')
                self._log_attempt(user, 'bank_account', params, result, 'failed', error=error_msg)
                return False, error_msg
        
        except Exception as e:
            self._log_attempt(user, 'bank_account', params, {}, 'failed', error=str(e))
            return False, str(e)
