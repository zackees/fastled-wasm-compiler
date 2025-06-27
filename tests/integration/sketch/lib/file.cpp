#include "file.h"

// Implementation of TestClass
TestClass::TestClass() : value(42) {
    // Constructor implementation
}

void TestClass::doSomething() {
    value *= 2;
}

int TestClass::getValue() const {
    return value;
}

// Function implementation
void testFunction() {
    // Simple test function
}