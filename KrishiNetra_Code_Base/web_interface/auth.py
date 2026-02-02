# web_interface/auth.py

import logging
from functools import wraps
from flask import request, Response
import sys
import os

# This allows importing the config file from the project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import config

logger = logging.getLogger(__name__)

# --- Authentication credentials ---
USERNAME = "KrishiNetra"
PASSWORD = config.WEB_INTERFACE_PASSWORD

def _check_auth(username, password):
    """
    This function is called to check if a username and password combination is valid.
    """
    return username == USERNAME and password == PASSWORD

def _authenticate():
    """
    Sends a 401 Unauthorized response that prompts the user's browser
    to display a login popup.
    """
    return Response(
        f"Could not verify your access for that URL.\n"
        f"You have to login with proper credentials for {config.PROJECT_NAME}.", 401,
        {'WWW-Authenticate': 'Basic realm="Login Required"'})

def requires_auth(f):
    """
    A decorator function that can be applied to any Flask route to
    enforce authentication. If the user is not authenticated, it will
    trigger the login prompt.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not _check_auth(auth.username, auth.password):
            logger.warning(f"Failed authentication attempt from IP: {request.remote_addr}")
            return _authenticate()
        
        return f(*args, **kwargs)
    
    return decorated