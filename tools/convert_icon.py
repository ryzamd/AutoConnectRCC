import os
import sys
from PIL import Image

def convert_icon(input_path, output_dir):
    """
    Converts a PNG image to .ico (Windows) and .icns (macOS) formats.
    """
    if not os.path.exists(input_path):
        print(f"Error: Input file '{input_path}' not found.")
        return

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    img = Image.open(input_path)
    base_name = os.path.splitext(os.path.basename(input_path))[0]

    # Generate ICO for Windows
    ico_path = os.path.join(output_dir, f"{base_name}.ico")
    img.save(ico_path, format='ICO', sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
    print(f"Generated: {ico_path}")

    # Generate ICNS for macOS
    # Note: Creating a proper ICNS usually requires specific sizes and 'icns' library or macOS tools (iconutil).
    # Since we are on Windows/Cross-platform, we will try to save as ICNS if Pillow supports it,
    # otherwise we might need a different approach or warn the user.
    # macOS PyInstaller often accepts .icns. Pillow can save ICNS in recent versions.
    try:
        icns_path = os.path.join(output_dir, f"{base_name}.icns")
        img.save(icns_path, format='ICNS', sizes=[(512, 512, 2), (512, 512, 1), (256, 256, 2), (256, 256, 1), (128, 128, 2), (128, 128, 1), (32, 32, 2), (32, 32, 1), (16, 16, 2), (16, 16, 1)])
        print(f"Generated: {icns_path}")
    except Exception as e:
        print(f"Warning: Could not separate ICNS file. {e}")
        print("For macOS, you might need to generate .icns on a Mac using 'iconutil' if this fails.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python convert_icon.py <path_to_png>")
        # Default fallback for project structure
        default_input = os.path.join("src", "rcc", "assets", "logo.png")
        if os.path.exists(default_input):
             convert_icon(default_input, os.path.dirname(default_input))
        else:
             print(f"Please place your logo at: {default_input}")
    else:
        convert_icon(sys.argv[1], os.path.dirname(sys.argv[1]))
