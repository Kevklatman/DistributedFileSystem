"""
Easy Test Builder - Write tests in plain English!

Example usage:

from test_builder import TestBuilder

# Create a test suite
suite = TestBuilder("Storage Policy Tests")

# Add test cases in plain English
suite.test("When uploading a financial document, it should use strong consistency") \
    .given("a financial document 'quarterly_report.pdf'") \
    .when("the document is uploaded to the financial folder") \
    .then("the storage policy should use strong consistency") \
    .and_then("there should be at least 3 replicas") \
    .build()

# Run the tests
suite.run()
"""

import inspect
import pytest
import asyncio
from typing import Any, Callable, List, Optional
from dataclasses import dataclass, field
from pathlib import Path
import sys

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

@dataclass
class TestStep:
    """Represents a step in the test case"""
    description: str
    action: Optional[Callable] = None
    expected: Any = None

@dataclass
class TestCase:
    """Represents a single test case"""
    name: str
    given_steps: List[TestStep] = field(default_factory=list)
    when_steps: List[TestStep] = field(default_factory=list)
    then_steps: List[TestStep] = field(default_factory=list)
    async_test: bool = False

class TestCaseBuilder:
    """Builder for creating test cases in plain English"""
    
    def __init__(self, name: str, suite: 'TestBuilder'):
        self.test_case = TestCase(name)
        self.suite = suite
        self._current_step_type = None

    def given(self, description: str, setup_action: Callable = None) -> 'TestCaseBuilder':
        """Define the test setup/preconditions"""
        self.test_case.given_steps.append(TestStep(description, setup_action))
        self._current_step_type = 'given'
        return self

    def and_given(self, description: str, setup_action: Callable = None) -> 'TestCaseBuilder':
        """Add additional setup/preconditions"""
        return self.given(description, setup_action)

    def when(self, description: str, action: Callable = None) -> 'TestCaseBuilder':
        """Define the action being tested"""
        self.test_case.when_steps.append(TestStep(description, action))
        self._current_step_type = 'when'
        return self

    def and_when(self, description: str, action: Callable = None) -> 'TestCaseBuilder':
        """Add additional actions"""
        return self.when(description, action)

    def then(self, description: str, expected: Any = None) -> 'TestCaseBuilder':
        """Define the expected outcome"""
        self.test_case.then_steps.append(TestStep(description, expected=expected))
        self._current_step_type = 'then'
        return self

    def and_then(self, description: str, expected: Any = None) -> 'TestCaseBuilder':
        """Add additional expectations"""
        return self.then(description, expected)

    def is_async(self) -> 'TestCaseBuilder':
        """Mark the test as async"""
        self.test_case.async_test = True
        return self

    def build(self) -> None:
        """Build and add the test case to the suite"""
        self.suite.add_test_case(self.test_case)
        return self.suite

class TestBuilder:
    """Main class for building test suites in plain English"""
    
    def __init__(self, name: str):
        self.name = name
        self.test_cases: List[TestCase] = []

    def test(self, name: str) -> TestCaseBuilder:
        """Create a new test case"""
        return TestCaseBuilder(name, self)

    def add_test_case(self, test_case: TestCase) -> None:
        """Add a test case to the suite"""
        self.test_cases.append(test_case)

    def _generate_test_function(self, test_case: TestCase) -> Callable:
        """Generate a pytest function for a test case"""
        
        async def async_test_func():
            # Run setup steps
            context = None
            for step in test_case.given_steps:
                if step.action:
                    context = await step.action()

            # Run test actions
            results = None
            for step in test_case.when_steps:
                if step.action:
                    if context is not None:
                        results = await step.action(context)
                    else:
                        results = await step.action()

            # Check expectations
            for step in test_case.then_steps:
                if step.expected:
                    assert step.expected(results), f"Failed: {step.description}"

        def test_func():
            # Run setup steps
            context = None
            for step in test_case.given_steps:
                if step.action:
                    context = step.action()

            # Run test actions
            results = None
            for step in test_case.when_steps:
                if step.action:
                    if context is not None:
                        results = step.action(context)
                    else:
                        results = step.action()

            # Check expectations
            for step in test_case.then_steps:
                if step.expected:
                    assert step.expected(results), f"Failed: {step.description}"

        # Use the appropriate test function based on whether it's async
        func = async_test_func if test_case.async_test else test_func
        
        # Add the test name and documentation
        func.__name__ = f"test_{test_case.name.lower().replace(' ', '_')}"
        func.__doc__ = f"""
        {test_case.name}
        
        Given:
        {chr(10).join(f'- {step.description}' for step in test_case.given_steps)}
        
        When:
        {chr(10).join(f'- {step.description}' for step in test_case.when_steps)}
        
        Then:
        {chr(10).join(f'- {step.description}' for step in test_case.then_steps)}
        """
        
        return func

    def run(self) -> None:
        """Run all test cases in the suite"""
        # Create a new module for the tests
        import types
        mod = types.ModuleType(self.name)
        
        # Add test functions to the module
        for test_case in self.test_cases:
            test_func = self._generate_test_function(test_case)
            if test_case.async_test:
                test_func = pytest.mark.asyncio(test_func)
            setattr(mod, test_func.__name__, test_func)
            
            # Run the test function directly
            test_func()
