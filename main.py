"""
main.py – Root-level entry point for Merlin.

Run from the project root:
    python main.py

This is equivalent to:
    uvicorn app.main:app --host 0.0.0.0 --port 8000
"""
from app.main import main

if __name__ == "__main__":
    main()
