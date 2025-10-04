from pathlib import Path


def transform_to_cpp(src_dir: Path) -> None:
    print("Transforming files to cpp...")
    ino_files = list(src_dir.glob("*.ino"))

    if ino_files:
        ino_file = ino_files[0]
        print(f"Found .ino file: {ino_file}")
        main_cpp = src_dir / "main.cpp"
        if main_cpp.exists():
            print("main.cpp already exists, renaming to main2.hpp")
            main_cpp.rename(src_dir / "main2.hpp")

        new_cpp_file = ino_file.with_suffix(".ino.cpp")
        # Remove existing .ino.cpp file if it exists (prevents stale cache issues)
        if new_cpp_file.exists():
            print(f"Removing existing {new_cpp_file.name} to prevent stale cache")
            new_cpp_file.unlink()
        print(f"Renaming {ino_file} to {new_cpp_file.name}")
        ino_file.rename(new_cpp_file)

        if (src_dir / "main2.hpp").exists():
            print(f"Including main2.hpp in {new_cpp_file.name}")
            with open(new_cpp_file, "a") as f:
                f.write('#include "main2.hpp"\n')
