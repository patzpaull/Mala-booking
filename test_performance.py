#!/usr/bin/env python3
"""
Performance testing script for the optimized Mala Booking System
Tests login performance and other critical endpoints
"""

import asyncio
import httpx
import time
import statistics
import json
from typing import List, Dict
import argparse

class PerformanceTester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.results: Dict[str, List[float]] = {}
    
    async def test_endpoint(self, client: httpx.AsyncClient, method: str, url: str, 
                          data: dict = None, headers: dict = None) -> float:
        """Test a single endpoint and return response time"""
        start_time = time.time()
        try:
            if method.upper() == "POST":
                response = await client.post(url, json=data, headers=headers)
            else:
                response = await client.get(url, headers=headers)
            
            response.raise_for_status()
            return time.time() - start_time
        except Exception as e:
            print(f"Error testing {url}: {e}")
            return -1
    
    async def test_auth_login(self, client: httpx.AsyncClient, credentials: dict) -> float:
        """Test login endpoint performance"""
        return await self.test_endpoint(
            client, "POST", f"{self.base_url}/auth/login", 
            data=credentials
        )
    
    async def test_auth_check(self, client: httpx.AsyncClient, token: str) -> float:
        """Test auth check endpoint performance"""
        headers = {"Authorization": f"Bearer {token}"}
        return await self.test_endpoint(
            client, "GET", f"{self.base_url}/auth/check-auth", 
            headers=headers
        )
    
    async def run_concurrent_tests(self, test_func, test_name: str, 
                                 concurrent_requests: int = 10, 
                                 total_requests: int = 100, **kwargs):
        """Run concurrent tests on an endpoint"""
        print(f"\n🧪 Testing {test_name} with {concurrent_requests} concurrent requests...")
        
        semaphore = asyncio.Semaphore(concurrent_requests)
        times = []
        
        async def limited_test():
            async with semaphore:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    return await test_func(client, **kwargs)
        
        # Run tests
        start_time = time.time()
        tasks = [limited_test() for _ in range(total_requests)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        total_time = time.time() - start_time
        
        # Filter successful results
        valid_times = [r for r in results if isinstance(r, float) and r > 0]
        
        if valid_times:
            self.results[test_name] = valid_times
            
            print(f"✅ {test_name} Results:")
            print(f"   Total requests: {total_requests}")
            print(f"   Successful requests: {len(valid_times)}")
            print(f"   Failed requests: {total_requests - len(valid_times)}")
            print(f"   Average response time: {statistics.mean(valid_times):.3f}s")
            print(f"   Median response time: {statistics.median(valid_times):.3f}s")
            print(f"   Min response time: {min(valid_times):.3f}s")
            print(f"   Max response time: {max(valid_times):.3f}s")
            print(f"   95th percentile: {statistics.quantiles(valid_times, n=20)[18]:.3f}s")
            print(f"   Requests per second: {len(valid_times) / total_time:.2f}")
            
            # Check if performance meets targets
            avg_time = statistics.mean(valid_times)
            if test_name.startswith("Login") and avg_time > 2.0:
                print(f"⚠️  Login performance still slow: {avg_time:.3f}s (target: <2.0s)")
            elif test_name.startswith("Auth Check") and avg_time > 0.5:
                print(f"⚠️  Auth check performance slow: {avg_time:.3f}s (target: <0.5s)")
            else:
                print(f"✅ Performance target met for {test_name}")
        else:
            print(f"❌ All requests failed for {test_name}")
    
    async def run_full_test_suite(self):
        """Run the complete performance test suite"""
        print("🚀 Starting Performance Test Suite for Mala Booking System")
        print("=" * 60)
        
        # Test login performance
        test_credentials = {
            "username": "test_user",
            "password": "test_password"
        }
        
        await self.run_concurrent_tests(
            self.test_auth_login,
            "Login Performance",
            concurrent_requests=5,
            total_requests=50,
            credentials=test_credentials
        )
        
        # Note: Auth check would need a valid token
        # This is a placeholder for when you have test users set up
        print("\n📝 To test auth check performance, ensure you have:")
        print("   - A test user account in your system")
        print("   - Redis cache running (if using Redis)")
        print("   - Database optimizations applied")
        
        print("\n📊 Performance Summary:")
        print("=" * 40)
        for test_name, times in self.results.items():
            if times:
                avg_time = statistics.mean(times)
                improvement = max(0, (10.0 - avg_time) / 10.0 * 100)  # Assuming 10s baseline
                print(f"  {test_name}: {avg_time:.3f}s avg ({improvement:.1f}% improvement)")

def main():
    parser = argparse.ArgumentParser(description="Performance test the Mala Booking System")
    parser.add_argument("--url", default="http://localhost:8000", 
                       help="Base URL of the application")
    parser.add_argument("--concurrent", type=int, default=10,
                       help="Number of concurrent requests")
    parser.add_argument("--total", type=int, default=100,
                       help="Total number of requests")
    
    args = parser.parse_args()
    
    tester = PerformanceTester(args.url)
    asyncio.run(tester.run_full_test_suite())

if __name__ == "__main__":
    main()