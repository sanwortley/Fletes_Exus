
import sys
import os

# Agregar el directorio actual al path para que Passenger encuentre el backend
sys.path.insert(0, os.path.dirname(__file__))

# Importar la aplicación de FastAPI
from backend.backend import app

# Passenger espera que el objeto se llame 'application'
application = app
