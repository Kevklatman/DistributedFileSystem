import os
import sys

# Add the src directory to Python path
src_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src')
sys.path.append(src_path)

from src.api.app import app

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
