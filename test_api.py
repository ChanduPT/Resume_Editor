#!/usr/bin/env python3
"""
Test script for Resume Editor API
"""
import requests
import json
import time
from base64 import b64encode

# Configuration
BASE_URL = "http://localhost:8000"  # Change to your Render URL when deployed
USERNAME = "testuser"
PASSWORD = "testpass123"

def basic_auth_header(username, password):
    """Create Basic Auth header"""
    credentials = f"{username}:{password}".encode('utf-8')
    encoded = b64encode(credentials).decode('utf-8')
    return {"Authorization": f"Basic {encoded}"}

def test_health():
    """Test health endpoint"""
    print("\n1. Testing health endpoint...")
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    return response.status_code == 200

def test_register():
    """Test user registration"""
    print("\n2. Testing user registration...")
    data = {
        "user_id": USERNAME,
        "password": PASSWORD
    }
    response = requests.post(f"{BASE_URL}/api/auth/register", json=data)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    return response.status_code in [200, 400]  # 400 if user exists

def test_login():
    """Test user login"""
    print("\n3. Testing login...")
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        headers=basic_auth_header(USERNAME, PASSWORD)
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    return response.status_code == 200

def test_generate_resume():
    """Test resume generation"""
    print("\n4. Testing resume generation...")
    
    # Sample resume data
    resume_data = {
        "mode": "complete_jd",
        "company_name": "TestCorp",
        "job_title": "Software Engineer",
        "jd": "We are looking for a Python developer with FastAPI experience...",
        "resume_data": {
            "name": "John Doe",
            "contact": "john@example.com | 123-456-7890",
            "summary": "Experienced software engineer with 5 years in Python development.",
            "technical_skills": {
                "Languages": ["Python", "JavaScript"],
                "Frameworks": ["Django", "React"]
            },
            "experience": [
                {
                    "company": "TechCo",
                    "title": "Software Engineer",
                    "dates": "Jan 2020 - Present",
                    "bullets": [
                        "Developed web applications using Python and Django",
                        "Collaborated with cross-functional teams"
                    ]
                }
            ],
            "education": [
                {
                    "school": "University of Tech",
                    "degree": "BS Computer Science",
                    "dates": "2015 - 2019"
                }
            ]
        },
        "job_description_data": {
            "company_name": "TestCorp",
            "job_title": "Software Engineer"
        }
    }
    
    response = requests.post(
        f"{BASE_URL}/api/generate_resume_json",
        headers=basic_auth_header(USERNAME, PASSWORD),
        json=resume_data
    )
    print(f"Status: {response.status_code}")
    result = response.json()
    print(f"Response: {json.dumps(result, indent=2)}")
    
    if response.status_code == 200:
        return result.get("request_id")
    return None

def test_job_status(request_id):
    """Test job status endpoint"""
    print(f"\n5. Testing job status (request_id: {request_id})...")
    
    max_attempts = 30
    for i in range(max_attempts):
        response = requests.get(
            f"{BASE_URL}/api/jobs/{request_id}/status",
            headers=basic_auth_header(USERNAME, PASSWORD)
        )
        status_data = response.json()
        print(f"Attempt {i+1}: Status={status_data.get('status')}, Progress={status_data.get('progress')}%")
        
        if status_data.get('status') == 'completed':
            print("✅ Job completed!")
            return True
        elif status_data.get('status') == 'failed':
            print(f"❌ Job failed: {status_data.get('error_message')}")
            return False
        
        time.sleep(2)
    
    print("⏱️ Timeout waiting for completion")
    return False

def test_get_result(request_id):
    """Test getting resume result"""
    print(f"\n6. Testing get result (request_id: {request_id})...")
    
    response = requests.get(
        f"{BASE_URL}/api/jobs/{request_id}/result",
        headers=basic_auth_header(USERNAME, PASSWORD)
    )
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"Company: {result.get('company_name')}")
        print(f"Job Title: {result.get('job_title')}")
        print(f"Completed At: {result.get('completed_at')}")
        return True
    else:
        print(f"Error: {response.json()}")
    return False

def test_job_history():
    """Test job history endpoint"""
    print("\n7. Testing job history...")
    
    response = requests.get(
        f"{BASE_URL}/api/user/jobs?limit=5",
        headers=basic_auth_header(USERNAME, PASSWORD)
    )
    print(f"Status: {response.status_code}")
    result = response.json()
    print(f"Total jobs: {result.get('count')}")
    for job in result.get('jobs', [])[:3]:
        print(f"  - {job.get('company_name')} | {job.get('status')} | {job.get('created_at')}")
    return response.status_code == 200

def main():
    """Run all tests"""
    print("="*60)
    print("Resume Editor API Test Suite")
    print("="*60)
    
    tests_passed = 0
    tests_total = 0
    
    # Test 1: Health
    tests_total += 1
    if test_health():
        tests_passed += 1
    
    # Test 2: Register
    tests_total += 1
    if test_register():
        tests_passed += 1
    
    # Test 3: Login
    tests_total += 1
    if test_login():
        tests_passed += 1
    
    # Test 4: Generate Resume
    tests_total += 1
    request_id = test_generate_resume()
    if request_id:
        tests_passed += 1
        
        # Test 5: Job Status
        tests_total += 1
        if test_job_status(request_id):
            tests_passed += 1
            
            # Test 6: Get Result
            tests_total += 1
            if test_get_result(request_id):
                tests_passed += 1
    
    # Test 7: Job History
    tests_total += 1
    if test_job_history():
        tests_passed += 1
    
    print("\n" + "="*60)
    print(f"Tests Passed: {tests_passed}/{tests_total}")
    print("="*60)
    
    if tests_passed == tests_total:
        print("✅ All tests passed!")
    else:
        print(f"⚠️ {tests_total - tests_passed} test(s) failed")

if __name__ == "__main__":
    main()
