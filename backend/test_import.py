try:
    from app.main import app
    print("Import successful!")
    print(f"App: {app}")
except Exception as e:
    print(f"Import failed: {e}")
    import traceback
    traceback.print_exc()
