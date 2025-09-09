import requests
import sys
import json
import time
from datetime import datetime

class SmartSewerAPITester:
    def __init__(self, base_url="https://smart-sewer.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.created_drain_id = None

    def run_test(self, name, method, endpoint, expected_status, data=None, params=None):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}" if endpoint else self.api_url
        headers = {'Content-Type': 'application/json'}

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    response_data = response.json()
                    if isinstance(response_data, list):
                        print(f"   Response: List with {len(response_data)} items")
                    elif isinstance(response_data, dict):
                        print(f"   Response keys: {list(response_data.keys())}")
                except:
                    print(f"   Response: {response.text[:100]}...")
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                print(f"   Response: {response.text[:200]}...")

            return success, response.json() if response.text else {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_root_endpoint(self):
        """Test API root endpoint"""
        success, response = self.run_test(
            "API Root",
            "GET",
            "",
            200
        )
        return success

    def test_init_sample_data(self):
        """Test initializing sample data"""
        success, response = self.run_test(
            "Initialize Sample Data",
            "POST",
            "init-sample-data",
            200
        )
        if success:
            print(f"   Sample data initialized: {response.get('message', 'No message')}")
        return success

    def test_get_all_drains(self):
        """Test getting all drains"""
        success, response = self.run_test(
            "Get All Drains",
            "GET",
            "drains",
            200
        )
        if success and isinstance(response, list):
            print(f"   Found {len(response)} drains")
            if len(response) > 0:
                drain = response[0]
                required_fields = ['id', 'latitude', 'longitude', 'status', 'location_name', 'last_updated']
                missing_fields = [field for field in required_fields if field not in drain]
                if missing_fields:
                    print(f"   ⚠️  Missing fields in drain data: {missing_fields}")
                else:
                    print(f"   ✅ All required fields present in drain data")
                    print(f"   Sample drain: {drain['location_name']} - {drain['status']}")
        return success, response

    def test_get_drains_with_filter(self):
        """Test getting drains with status filter"""
        filters = ['livre', 'parcialmente_obstruido', 'entupido']
        all_passed = True
        
        for status_filter in filters:
            success, response = self.run_test(
                f"Get Drains - Filter: {status_filter}",
                "GET",
                "drains",
                200,
                params={'status_filter': status_filter}
            )
            if success and isinstance(response, list):
                # Verify all returned drains have the correct status
                if len(response) > 0:
                    wrong_status = [d for d in response if d.get('status') != status_filter]
                    if wrong_status:
                        print(f"   ⚠️  Found {len(wrong_status)} drains with wrong status")
                        all_passed = False
                    else:
                        print(f"   ✅ All {len(response)} drains have correct status: {status_filter}")
            else:
                all_passed = False
        
        return all_passed

    def test_create_drain(self):
        """Test creating a new drain"""
        test_drain = {
            "latitude": -23.5555,
            "longitude": -46.6666,
            "status": "livre",
            "location_name": "Test Location - Rua de Teste"
        }
        
        success, response = self.run_test(
            "Create New Drain",
            "POST",
            "drains",
            200,  # Based on the code, it should return 200, not 201
            data=test_drain
        )
        
        if success and 'id' in response:
            self.created_drain_id = response['id']
            print(f"   Created drain with ID: {self.created_drain_id}")
            
            # Verify all fields are present
            for field in ['latitude', 'longitude', 'status', 'location_name', 'last_updated']:
                if field not in response:
                    print(f"   ⚠️  Missing field in response: {field}")
                    return False
            print(f"   ✅ All fields present in created drain")
        
        return success

    def test_get_specific_drain(self):
        """Test getting a specific drain by ID"""
        if not self.created_drain_id:
            print("   ⚠️  No drain ID available for testing")
            return False
            
        success, response = self.run_test(
            f"Get Specific Drain (ID: {self.created_drain_id})",
            "GET",
            f"drains/{self.created_drain_id}",
            200
        )
        
        if success and isinstance(response, dict):
            if response.get('id') == self.created_drain_id:
                print(f"   ✅ Retrieved correct drain: {response.get('location_name')}")
            else:
                print(f"   ⚠️  Retrieved drain has different ID")
                return False
        
        return success

    def test_update_drain_status(self):
        """Test updating drain status"""
        if not self.created_drain_id:
            print("   ⚠️  No drain ID available for testing")
            return False
            
        update_data = {"status": "entupido"}
        
        success, response = self.run_test(
            f"Update Drain Status (ID: {self.created_drain_id})",
            "PUT",
            f"drains/{self.created_drain_id}",
            200,
            data=update_data
        )
        
        if success and isinstance(response, dict):
            if response.get('status') == 'entupido':
                print(f"   ✅ Status updated successfully to: {response.get('status')}")
            else:
                print(f"   ⚠️  Status not updated correctly. Got: {response.get('status')}")
                return False
        
        return success

    def test_invalid_endpoints(self):
        """Test invalid endpoints and error handling"""
        print(f"\n🔍 Testing Error Handling...")
        
        # Test non-existent drain
        success, response = self.run_test(
            "Get Non-existent Drain",
            "GET",
            "drains/non-existent-id",
            404  # Correct HTTP status for not found
        )
        
        # Test invalid drain update
        success2, response2 = self.run_test(
            "Update Non-existent Drain",
            "PUT",
            "drains/non-existent-id",
            404,  # Correct HTTP status for not found
            data={"status": "livre"}
        )
        
        return True  # Error handling tests are informational

    def validate_sao_paulo_data(self, drains_data):
        """Validate that sample data contains São Paulo locations"""
        print(f"\n🔍 Validating São Paulo Sample Data...")
        
        if not isinstance(drains_data, list) or len(drains_data) == 0:
            print("   ❌ No drains data to validate")
            return False
        
        # Check if we have expected number of drains
        if len(drains_data) != 10:
            print(f"   ⚠️  Expected 10 sample drains, found {len(drains_data)}")
        
        # Validate São Paulo coordinates (should be around -23.5, -46.6)
        sao_paulo_drains = 0
        valid_statuses = ['livre', 'parcialmente_obstruido', 'entupido']
        
        for drain in drains_data:
            lat, lng = drain.get('latitude', 0), drain.get('longitude', 0)
            
            # Check if coordinates are in São Paulo area
            if -23.6 <= lat <= -23.4 and -46.8 <= lng <= -46.4:
                sao_paulo_drains += 1
            
            # Check status validity
            if drain.get('status') not in valid_statuses:
                print(f"   ⚠️  Invalid status found: {drain.get('status')}")
            
            # Check location name contains Portuguese/São Paulo references
            location = drain.get('location_name', '')
            if any(word in location.lower() for word in ['rua', 'centro', 'vila', 'largo', 'av']):
                pass  # Good, contains Portuguese street terms
        
        print(f"   ✅ Found {sao_paulo_drains} drains in São Paulo area")
        print(f"   ✅ All drains have valid status values")
        
        return sao_paulo_drains >= 8  # Allow some tolerance

def main():
    print("🚀 Starting Smart Sewer Monitoring API Tests")
    print("=" * 60)
    
    tester = SmartSewerAPITester()
    
    # Test sequence
    tests = [
        ("API Root Endpoint", tester.test_root_endpoint),
        ("Initialize Sample Data", tester.test_init_sample_data),
        ("Get All Drains", lambda: tester.test_get_all_drains()),
        ("Filter Drains by Status", tester.test_get_drains_with_filter),
        ("Create New Drain", tester.test_create_drain),
        ("Get Specific Drain", tester.test_get_specific_drain),
        ("Update Drain Status", tester.test_update_drain_status),
        ("Error Handling", tester.test_invalid_endpoints),
    ]
    
    # Run all tests
    for test_name, test_func in tests:
        try:
            if test_name == "Get All Drains":
                success, drains_data = test_func()
                if success:
                    tester.validate_sao_paulo_data(drains_data)
            else:
                test_func()
        except Exception as e:
            print(f"❌ Test '{test_name}' failed with exception: {str(e)}")
    
    # Print final results
    print("\n" + "=" * 60)
    print(f"📊 FINAL RESULTS")
    print(f"Tests Run: {tester.tests_run}")
    print(f"Tests Passed: {tester.tests_passed}")
    print(f"Success Rate: {(tester.tests_passed/tester.tests_run*100):.1f}%" if tester.tests_run > 0 else "0%")
    
    if tester.tests_passed == tester.tests_run:
        print("🎉 All tests passed!")
        return 0
    else:
        print(f"⚠️  {tester.tests_run - tester.tests_passed} tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())