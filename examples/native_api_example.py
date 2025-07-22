#!/usr/bin/env python3
"""
Example of using the FastLED WASM Compiler Native API programmatically.

This example demonstrates how to:
1. Create a native compiler instance
2. Compile a sketch to WASM
3. Dump headers to a zip file programmatically

Usage:
    python examples/native_api_example.py
"""

import tempfile
from pathlib import Path

from fastled_wasm_compiler import CompilerNative


def main():
    """Example of using the native compiler API."""
    print("🚀 FastLED WASM Compiler Native API Example")

    # Create a native compiler instance
    compiler = CompilerNative()

    # Ensure EMSDK is installed
    print("📦 Ensuring EMSDK is available...")
    compiler.ensure_emsdk()

    # Get compilation environment info
    env = compiler.get_compilation_env()
    print(f"📋 Compilation environment has {len(env)} variables")

    # Get tool paths
    tools = compiler.get_tool_paths()
    print(f"🔧 Available tools: {', '.join(tools.keys())}")

    # Example 1: Compile a sketch (if sketch directory exists)
    sketch_dir = Path("Blink")
    if sketch_dir.exists():
        print(f"🔨 Compiling sketch: {sketch_dir}")
        try:
            output_wasm = compiler.compile_sketch(sketch_dir, "quick")
            print(f"✅ Compiled to: {output_wasm}")
        except Exception as e:
            print(f"❌ Compilation failed: {e}")
    else:
        print(f"⚠️  Sketch directory {sketch_dir} not found, skipping compilation")

    # Example 2: Dump headers to zip programmatically using the API
    print("\n📦 Demonstrating programmatic header dumping...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create zip file path
        headers_zip = Path(temp_dir) / "fastled_headers.zip"
        
        try:
            print(f"🔄 Dumping headers to: {headers_zip}")
            # Use the API method instead of direct function call
            manifest = compiler.dump_headers(headers_zip, include_source=True)
            
            total_files = manifest["metadata"]["total_files"]
            print(f"✅ Successfully created zip with {total_files} files")
            print(f"📁 Zip file size: {headers_zip.stat().st_size // 1024}KB")
            
            # Show what's included
            categories = [k for k in manifest.keys() if k != "metadata"]
            print(f"📋 Categories included: {', '.join(categories)}")
            
        except Exception as e:
            print(f"❌ Header dump failed: {e}")

    print("\n🎉 Example complete!")


if __name__ == "__main__":
    main() 