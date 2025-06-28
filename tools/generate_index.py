#!/usr/bin/env python3
"""
Utility module for generating index.html files with artifact listings.
This can be used for publishing artifacts with organized platform-specific directories
and auto-generated index files with links to manifests and reconstruction files.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


def get_file_info(file_path: Path) -> Dict[str, Any]:
    """
    Get information about a file including size and type.

    Args:
        file_path: Path to the file

    Returns:
        Dictionary with file information
    """
    if not file_path.exists():
        return {}

    stat = file_path.stat()
    file_type = "Unknown"

    if file_path.suffix == ".xz" and file_path.name.endswith(".tar.xz"):
        file_type = "Complete Archive"
    elif ".tar.xz.part" in file_path.name:
        file_type = "Split Archive Part"
    elif file_path.name.endswith("-reconstruct.sh"):
        file_type = "Reconstruction Script"
    elif file_path.name.endswith("-manifest.txt"):
        file_type = "Manifest File"
    elif file_path.suffix == ".json":
        file_type = "JSON Manifest"
    elif file_path.suffix == ".wasm":
        file_type = "WebAssembly Module"
    elif file_path.suffix == ".js":
        file_type = "JavaScript Module"
    elif file_path.suffix == ".html":
        file_type = "HTML File"
    elif file_path.suffix == ".css":
        file_type = "CSS Stylesheet"

    return {
        "name": file_path.name,
        "size": stat.st_size,
        "size_mb": stat.st_size / (1024 * 1024),
        "type": file_type,
        "path": str(
            file_path.relative_to(file_path.parent.parent)
            if file_path.parent.parent in file_path.parents
            else file_path.name
        ),
    }


def generate_platform_index_html(
    output_dir: Path,
    platforms: Dict[str, Dict[str, Any]],
    title: str = "FastLED WASM Compiler - Artifacts",
    subtitle: str = "Platform-specific build artifacts",
    base_url: Optional[str] = None,
) -> Path:
    """
    Generate an index.html file for platform-organized artifacts.

    Args:
        output_dir: Directory where the index.html will be created
        platforms: Dictionary mapping platform names to their info and files
        title: Page title
        subtitle: Page subtitle
        base_url: Base URL for downloads (optional)

    Returns:
        Path to the generated index.html file
    """
    index_path = output_dir / "index.html"
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    # Platform icons mapping
    platform_icons = {
        "ubuntu": "🐧",
        "linux": "🐧",
        "macos": "🍎",
        "macos-x86_64": "🍎",
        "macos-arm64": "🍎",
        "windows": "🪟",
        "wasm": "🌐",
        "web": "🌐",
    }

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            line-height: 1.6;
            color: #333;
            background: #f5f5f5;
        }}
        .header {{
            text-align: center;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 2rem;
            border-radius: 10px;
            margin-bottom: 2rem;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        .header h1 {{
            margin: 0;
            font-size: 2.5rem;
        }}
        .header p {{
            margin: 0.5rem 0 0 0;
            opacity: 0.9;
        }}
        .platforms {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }}
        .platform-card {{
            background: white;
            border-radius: 10px;
            padding: 1.5rem;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            border: 1px solid #e1e5e9;
        }}
        .platform-card h2 {{
            color: #2c3e50;
            margin-top: 0;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}
        .platform-icon {{
            font-size: 1.5rem;
        }}
        .file-list {{
            list-style: none;
            padding: 0;
            margin: 1rem 0;
        }}
        .file-list li {{
            background: #f8f9fa;
            border: 1px solid #e9ecef;
            border-radius: 5px;
            margin: 0.5rem 0;
            overflow: hidden;
        }}
        .file-link {{
            display: block;
            padding: 0.75rem 1rem;
            text-decoration: none;
            color: #495057;
            transition: background-color 0.2s;
        }}
        .file-link:hover {{
            background-color: #e9ecef;
            color: #2c3e50;
        }}
        .file-type {{
            font-size: 0.8rem;
            color: #6c757d;
            font-weight: normal;
        }}
        .file-size {{
            font-size: 0.8rem;
            color: #6c757d;
            float: right;
        }}
        .instructions {{
            background: white;
            border-radius: 10px;
            padding: 1.5rem;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            border-left: 4px solid #28a745;
        }}
        .instructions h2 {{
            color: #28a745;
            margin-top: 0;
        }}
        .instructions code {{
            background: #f8f9fa;
            padding: 2px 4px;
            border-radius: 3px;
            font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
        }}
        .instructions pre {{
            background: #f8f9fa;
            padding: 1rem;
            border-radius: 5px;
            overflow-x: auto;
            border: 1px solid #e9ecef;
        }}
        .footer {{
            text-align: center;
            margin-top: 2rem;
            padding-top: 1rem;
            border-top: 1px solid #e1e5e9;
            color: #6c757d;
        }}
        .timestamp {{
            font-size: 0.9rem;
            color: #6c757d;
        }}
        .warning {{
            color: #dc3545;
            font-weight: bold;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🚀 {title}</h1>
        <p>{subtitle}</p>
        <div class="timestamp">Generated: {timestamp}</div>
    </div>

    <div class="platforms">
"""

    # Add platform sections
    for platform_name, platform_info in platforms.items():
        display_name = platform_info.get("display_name", platform_name.title())
        files = platform_info.get("files", [])
        description = platform_info.get("description", "")

        # Get platform icon
        icon = platform_icons.get(platform_name.lower(), "💻")
        for key in platform_icons:
            if key in platform_name.lower():
                icon = platform_icons[key]
                break

        html_content += f"""
        <div class="platform-card">
            <h2><span class="platform-icon">{icon}</span> {display_name}</h2>
            {f'<p>{description}</p>' if description else ''}
            <ul class="file-list">
"""

        for file_info in files:
            file_name = file_info["name"]
            file_type = file_info.get("type", "")
            file_size_mb = file_info.get("size_mb", 0)

            # Build the download URL
            if base_url:
                download_url = f"{base_url.rstrip('/')}/{platform_name}/{file_name}"
            else:
                download_url = f"./{platform_name}/{file_name}"

            # Format file size
            if file_size_mb >= 1:
                size_str = f"{file_size_mb:.1f}MB"
            elif file_size_mb >= 0.1:
                size_str = f"{file_size_mb:.2f}MB"
            else:
                size_str = f"{file_info.get('size', 0)}B"

            # Check for large files
            size_warning = ""
            if file_size_mb > 95:
                size_warning = '<span class="warning"> (Large file!)</span>'

            html_content += f"""
                <li>
                    <a href="{download_url}" class="file-link">
                        {file_name} 
                        <span class="file-type">({file_type})</span>
                        <span class="file-size">{size_str}{size_warning}</span>
                    </a>
                </li>
"""

        html_content += """
            </ul>
        </div>
"""

    # Add instructions and footer
    html_content += f"""
    </div>

    <div class="instructions">
        <h2>📋 Usage Instructions</h2>
        <h3>For Complete Archives (.tar.xz files):</h3>
        <pre><code># Download the archive for your platform
wget {base_url or 'https://your-site.com'}/[platform]/[filename]

# Extract the archive
tar -xJf [filename]

# Setup environment (if applicable)
cd emsdk
source ./emsdk_env.sh</code></pre>

        <h3>For Split Archives (part files):</h3>
        <p>When archives exceed size limits, they are split into multiple parts:</p>
        <pre><code># Download all part files and the reconstruction script
wget {base_url or 'https://your-site.com'}/[platform]/[filename]*.part*
wget {base_url or 'https://your-site.com'}/[platform]/[filename]*-reconstruct.sh
wget {base_url or 'https://your-site.com'}/[platform]/[filename]*-manifest.txt

# Make reconstruction script executable and run it
chmod +x *-reconstruct.sh
./*-reconstruct.sh

# Extract the reconstructed archive
tar -xJf [filename]</code></pre>

        <h3>For WebAssembly Artifacts:</h3>
        <pre><code># Include in your HTML
&lt;script src="[platform]/index.js"&gt;&lt;/script&gt;

# Or load as module
import Module from './[platform]/fastled.js';</code></pre>
    </div>

    <div class="footer">
        <p>Generated by <a href="https://github.com/zackees/fastled-wasm-compiler" target="_blank">FastLED WASM Compiler</a></p>
        <p>For more information, visit the <a href="https://github.com/zackees/fastled-wasm-compiler" target="_blank">GitHub repository</a></p>
    </div>
</body>
</html>
"""

    # Write the file
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    return index_path


def scan_platform_directory(platform_dir: Path) -> List[Dict[str, Any]]:
    """
    Scan a platform directory and return file information.

    Args:
        platform_dir: Path to the platform directory

    Returns:
        List of file information dictionaries
    """
    files = []
    if not platform_dir.exists():
        return files

    for file_path in sorted(platform_dir.iterdir()):
        if file_path.is_file():
            files.append(get_file_info(file_path))

    return files


def generate_manifest_json(
    output_dir: Path,
    platforms: Dict[str, Dict[str, Any]],
    metadata: Optional[Dict[str, Any]] = None,
) -> Path:
    """
    Generate a JSON manifest file listing all platforms and their files.

    Args:
        output_dir: Directory where the manifest.json will be created
        platforms: Dictionary mapping platform names to their info and files
        metadata: Additional metadata to include

    Returns:
        Path to the generated manifest.json file
    """
    manifest_path = output_dir / "manifest.json"

    manifest_data = {
        "generated": datetime.utcnow().isoformat() + "Z",
        "version": "1.0",
        "platforms": {},
    }

    if metadata:
        manifest_data["metadata"] = metadata

    for platform_name, platform_info in platforms.items():
        manifest_data["platforms"][platform_name] = {
            "display_name": platform_info.get("display_name", platform_name.title()),
            "description": platform_info.get("description", ""),
            "files": platform_info.get("files", []),
        }

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2, sort_keys=True)

    return manifest_path


if __name__ == "__main__":
    # Example usage
    import sys

    if len(sys.argv) < 2:
        print("Usage: python generate_index.py <output_directory> [base_url]")
        sys.exit(1)

    output_path = Path(sys.argv[1])
    base_url = sys.argv[2] if len(sys.argv) > 2 else None

    # Scan for platform directories
    platforms = {}
    for platform_dir in output_path.iterdir():
        if platform_dir.is_dir() and not platform_dir.name.startswith("."):
            files = scan_platform_directory(platform_dir)
            if files:
                platforms[platform_dir.name] = {
                    "display_name": platform_dir.name.title(),
                    "files": files,
                }

    if platforms:
        # Generate index.html
        index_path = generate_platform_index_html(
            output_path, platforms, base_url=base_url
        )
        print(f"Generated index: {index_path}")

        # Generate manifest.json
        manifest_path = generate_manifest_json(output_path, platforms)
        print(f"Generated manifest: {manifest_path}")
    else:
        print("No platform directories found")
