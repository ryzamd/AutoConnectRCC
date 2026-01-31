import sys
import os

# Add src to path so we can import rcc package
src_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src')
sys.path.insert(0, src_path)

from rcc.main import main

if __name__ == '__main__':
    sys.exit(main())
