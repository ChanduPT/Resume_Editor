"""
Quick test to verify registration endpoint works
"""
import requests
import json

BASE_URL = "http://localhost:8000"

def test_registration():
    print("Testing registration endpoint...")
    
    # Test data
    test_user = {
        "user_id": "testuser123",
        "password": "TestPassword123"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/auth/register",
            json=test_user,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"\nStatus Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            print("\n✅ Registration successful!")
            return True
        elif response.status_code == 400:
            print("\n⚠️  User might already exist or validation error")
            return False
        else:
            print(f"\n❌ Registration failed with status {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("\n❌ Cannot connect to server. Is it running on port 8000?")
        return False
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        return False

if __name__ == "__main__":
    test_registration()
