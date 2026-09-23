import os
import sys

def main():
    has_gemini = bool(os.environ.get("GEMINI_API_KEY"))
    has_claude = bool(os.environ.get("CLAUDE_API_KEY"))

    if not has_gemini and not has_claude:
        print("ERROR: Set at least one of GEMINI_API_KEY or CLAUDE_API_KEY.")
        sys.exit(1)

    from web_api import app
    app.run(host="0.0.0.0", port=8080, debug=True)

if __name__ == "__main__":
    main()
