# Import FastAPI so we can build our web app
from fastapi import FastAPI

# Import the engine and Base from our database file
from database import engine, Base
# Import models so Python knows about our tables
import models

# Create all the tables in the database if they don't exist yet
Base.metadata.create_all(bind=engine)

# Create the app and give it a name
app = FastAPI(title="M-nyumba")
# When someone visits the home address "/", run the function below
@app.get("/")
def home():
    # Send back a simple message to prove the server works
    return {"message": "M-nyumba is running"}