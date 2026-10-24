import os

# Set before any test module imports app.main (which builds the default app): never touch a real DB file.
os.environ["VERIFAI_DATABASE_URL"] = "sqlite:///:memory:"