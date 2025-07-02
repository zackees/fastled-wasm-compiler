#!/usr/bin/env python3
"""
Example demonstrating the FastLED WASM Compiler Native API

This example shows how to use the native compilation functions
exposed in the fastled_wasm_compiler package.
"""

from pathlib import Path
from fastled_wasm_compiler import (
    NativeCompiler,
    compile_sketch_native,
    NativeCliArgs,
    cli_native_main,
    EmsdkManager,
    get_emsdk_manager
)


def example_simple_compilation():
    """Example: Simple sketch compilation using convenience function."""
    print("=== Simple Compilation Example ===")
    
    sketch_dir = Path("./my_sketch")  # Your sketch directory
    
    # Simple compilation using convenience function
    try:
        js_file = compile_sketch_native(
            sketch_dir=sketch_dir,
            build_mode="debug",  # or "quick" or "release"
            output_dir=None,  # defaults to sketch_dir/fastled_js
            emsdk_install_dir=None  # use default location
        )
        print(f"✅ Compilation successful: {js_file}")
    except Exception as e:
        print(f"❌ Compilation failed: {e}")


def example_advanced_compilation():
    """Example: Advanced compilation using NativeCompiler class."""
    print("\n=== Advanced Compilation Example ===")
    
    # Create compiler instance with custom EMSDK location
    compiler = NativeCompiler(emsdk_install_dir=Path("./custom_emsdk"))
    
    sketch_dir = Path("./my_sketch")
    output_dir = Path("./output")
    
    try:
        # Compile with custom settings
        js_file = compiler.compile_sketch(
            sketch_dir=sketch_dir,
            build_mode="release",
            output_dir=output_dir
        )
        print(f"✅ Advanced compilation successful: {js_file}")
    except Exception as e:
        print(f"❌ Advanced compilation failed: {e}")


def example_emsdk_management():
    """Example: EMSDK management operations."""
    print("\n=== EMSDK Management Example ===")
    
    # Get EMSDK manager
    manager = get_emsdk_manager()
    
    # Check installation status
    if manager.is_installed():
        print("✅ EMSDK is already installed")
        
        # Show environment variables
        env_vars = manager.get_env_vars()
        print(f"EMSDK path: {env_vars.get('EMSDK')}")
        
        # Show tool paths
        tool_paths = manager.get_tool_paths()
        print(f"emcc path: {tool_paths['emcc']}")
        
    else:
        print("❌ EMSDK not installed")
        
        # Install EMSDK
        try:
            print("Installing EMSDK...")
            manager.install()
            print("✅ EMSDK installation complete")
        except Exception as e:
            print(f"❌ EMSDK installation failed: {e}")


def example_cli_args():
    """Example: Working with CLI arguments programmatically."""
    print("\n=== CLI Arguments Example ===")
    
    # Create CLI args manually
    args = NativeCliArgs(
        sketch_dir=Path("./my_sketch"),
        build_mode="debug",
        output_dir=Path("./output"),
        emsdk_dir=None,
        install_emsdk=False,
        keep_files=True,
        profile=False,
        strict=False
    )
    
    print(f"Sketch directory: {args.sketch_dir}")
    print(f"Build mode: {args.build_mode}")
    print(f"Output directory: {args.output_dir}")
    print(f"Keep files: {args.keep_files}")


def example_cli_main():
    """Example: Using the CLI main function programmatically."""
    print("\n=== CLI Main Function Example ===")
    
    # Note: This would use sys.argv for argument parsing
    # For demonstration, we'll just show how to call it
    print("To use cli_native_main(), you would typically call it from a script:")
    print("  from fastled_wasm_compiler import cli_native_main")
    print("  exit_code = cli_native_main()")
    print("  # This uses sys.argv for argument parsing")


def main():
    """Run all examples."""
    print("FastLED WASM Compiler Native API Examples")
    print("=" * 50)
    
    # Note: These examples assume you have a sketch directory
    # In practice, you would replace './my_sketch' with your actual sketch path
    
    example_simple_compilation()
    example_advanced_compilation()
    example_emsdk_management()
    example_cli_args()
    example_cli_main()
    
    print("\n" + "=" * 50)
    print("Examples complete!")
    print("\nNote: These examples assume you have a sketch directory.")
    print("Replace './my_sketch' with your actual sketch path.")


if __name__ == "__main__":
    main() 