# Navigate to your project directory
cd path/to/your/project

# Create a virtual environment
python3 -m venv venv  # On macOS and Linux
python -m venv venv   # On Windows

# Activate the virtual environment:
source venv/bin/activate  # On macOS and Linux
.\venv\Scripts\activate   # On Windows

# Install the dependencies using pip and the requirements.txt file:
pip install -r requirements.txt

# Run flask app
flask run
