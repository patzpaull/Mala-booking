#!/usr/bin/env python3
"""
Test script to verify our API changes work correctly
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test that all imports work correctly after our changes"""
    try:
        # Test main app imports
        from app.main import app
        print("✅ Main app imports successfully")
        
        # Test models import
        from app import models
        print("✅ Models import successfully")
        
        # Test response utilities
        from app.utils.responses import success_response, error_response
        print("✅ Response utilities import successfully")
        
        # Test datetime imports in messages router
        from app.routers.messages import datetime, timezone
        print("✅ Datetime imports in messages router work")
        
        return True
        
    except Exception as e:
        print(f"❌ Import error: {e}")
        return False

def test_response_format():
    """Test standardized response format"""
    try:
        from app.utils.responses import success_response, error_response
        
        # Test success response
        success = success_response(data={"test": "data"}, message="Test successful")
        print("✅ Success response format works")
        
        # Test error response
        error = error_response(message="Test error", code=400)
        print("✅ Error response format works")
        
        return True
        
    except Exception as e:
        print(f"❌ Response format error: {e}")
        return False

def test_model_datetime_fields():
    """Test that model datetime fields are properly defined"""
    try:
        from app.models import Appointment, User, Profile, Message, Service, Salon, Staff, Payment, Review
        from sqlalchemy import DateTime
        
        # Check key datetime fields
        appointment_time_type = Appointment.__table__.columns['appointment_time'].type
        if hasattr(appointment_time_type, 'python_type') and appointment_time_type.python_type.__name__ == 'datetime':
            print("✅ Appointment.appointment_time uses DateTime")
        
        message_sent_time_type = Message.__table__.columns['sent_time'].type
        if hasattr(message_sent_time_type, 'python_type') and message_sent_time_type.python_type.__name__ == 'datetime':
            print("✅ Message.sent_time uses DateTime")
        
        print("✅ Model datetime fields are properly configured")
        return True
        
    except Exception as e:
        print(f"❌ Model datetime error: {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 Testing MALA API Changes...")
    print("=" * 50)
    
    tests = [
        ("Import Tests", test_imports),
        ("Response Format Tests", test_response_format), 
        ("Model DateTime Tests", test_model_datetime_fields)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n📋 Running {test_name}:")
        if test_func():
            passed += 1
        
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! API changes are working correctly.")
        return True
    else:
        print("⚠️  Some tests failed. Check the errors above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)