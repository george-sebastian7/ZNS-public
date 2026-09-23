import os
import sys

def main():
    if not os.environ.get("GEMINI_API_KEY"):
        print("ERROR: GEMINI_API_KEY environment variable is not set.")
        sys.exit(1)

    from web_api import app
    app.run(host="0.0.0.0", port=8080, debug=True)

if __name__ == "__main__":
    main()
